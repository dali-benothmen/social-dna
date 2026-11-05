import json
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_file
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.storage.artifacts import ArtifactStore
from socialdna.storage.backup import backup_library, restore_library, verify_backup
from socialdna.storage.database import Database
from socialdna.storage.evidence_repository import EvidenceRepository, backfill_evidence
from socialdna.storage.migration_runner import current_revision, migrate, migration_config
from socialdna.storage.schema import metadata


def released_library(settings: Settings, head: str) -> tuple[str, bytes]:
    paths = DataPaths(settings.data_dir)
    paths.create()
    database = Database(paths.database)
    evidence_id = stable_id("old-evidence", "opening")
    archived = b'{"historical_report":"keep exact original bytes"}'
    try:
        with database.transaction() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, head)
            scripts = ScriptDirectory.from_config(config)
            for revision in scripts.walk_revisions(base="base", head=head):
                connection.exec_driver_sql(
                    "INSERT INTO migration_checksums VALUES (?, ?, ?)",
                    (revision.revision, hash_file(Path(revision.path)), utc_now()),
                )
            connection.exec_driver_sql("INSERT INTO creators VALUES ('old-creator', 'Keep me')")
            connection.exec_driver_sql(
                "INSERT INTO source_records "
                "(id,source_kind,source_uri,permission_basis,retrieved_at) "
                "VALUES ('old-source','local','urn:owned:fixture','user_supplied',?)",
                (utc_now(),),
            )
            connection.exec_driver_sql(
                "INSERT INTO provenance_records (id,source_record_id,method,created_at) "
                "VALUES ('old-provenance','old-source','fixture',?)",
                (utc_now(),),
            )
            if head != "0001_foundation":
                connection.exec_driver_sql(
                    "INSERT INTO media_assets (id,media_type,duration_ms) "
                    "VALUES ('old-media','video',1000)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO analysis_runs "
                    "(id,target_type,target_id,depth,profile_version,config_hash,created_at) "
                    "VALUES ('old-run','media','old-media','quick','old','hash',?)",
                    (utc_now(),),
                )
                connection.exec_driver_sql(
                    "INSERT INTO analysis_tasks "
                    "(id,run_id,task_key,fingerprint,analyzer,analyzer_version) "
                    "VALUES ('old-task','old-run','scene','hash','scene','1')"
                )
                connection.exec_driver_sql(
                    "INSERT INTO scenes "
                    "(id,media_asset_id,task_id,ordinal,start_ms,end_ms,detector) "
                    "VALUES ('old-scene','old-media','old-task',0,0,1000,'fixture')"
                )
                connection.exec_driver_sql(
                    "INSERT INTO evidence_items "
                    "(id,media_asset_id,task_id,start_ms,end_ms,subject_type,"
                    "subject_id,provenance_id) "
                    "VALUES (?,'old-media','old-task',0,1000,'scene','old-scene','old-provenance')",
                    (evidence_id,),
                )
                artifact = ArtifactStore(paths).put_bytes(
                    connection, archived, kind="report", mime_type="application/json"
                )
                connection.exec_driver_sql(
                    "INSERT INTO reports VALUES ('old-report','old-run','json',?,'1.0',?)",
                    (artifact, utc_now()),
                )
    finally:
        database.close()
    return evidence_id, archived


@pytest.mark.parametrize(
    "head", ["0001_foundation", "0002_timeline", "0003_enrichment", "0004_analytics"]
)
def test_released_upgrade_keeps_ids_and_report_bytes_and_makes_verified_backup(
    settings: Settings,
    head: str,
    tmp_path: Path,
) -> None:
    evidence_id, archived = released_library(settings, head)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            assert current_revision(connection) == "0005_evidence"
            assert (
                connection.scalar(select(metadata.tables["creators"].c.display_name)) == "Keep me"
            )
            if head != "0001_foundation":
                resolved = EvidenceResolver(connection).resolve(evidence_id)
                assert resolved.ref.id == evidence_id
                assert resolved.locator.media.id == "old-media"
                assert resolved.available_at is None
                row = application.artifacts.get(
                    connection, connection.scalar(select(metadata.tables["reports"].c.artifact_id))
                )
                assert application.artifacts.path_for(row["relative_path"]).read_bytes() == archived
    backups = list((settings.data_dir / "backups").iterdir())
    assert len(backups) == 1 and verify_backup(backups[0])["database_revision"] == head
    with open_application(settings):
        pass
    assert len(list((settings.data_dir / "backups").iterdir())) == 1
    restored = tmp_path / "restored"
    assert restore_library(backups[0], restored, withdrawals_from=settings.data_dir)["verified"]
    with open_application(Settings(data_dir=restored)) as application:
        if head != "0001_foundation":
            with application.database.transaction() as connection:
                assert EvidenceResolver(connection).resolve(evidence_id).ref.id == evidence_id


def test_backfill_interruption_resumes_committed_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "backfill.db")
    try:
        migrate(database)
        with database.transaction() as connection:
            for identity in ("a", "b"):
                connection.execute(
                    metadata.tables["accounts"]
                    .insert()
                    .values(id=identity, platform="demo", external_id=identity)
                )
        original = EvidenceRepository.capture

        def interrupted(
            self: EvidenceRepository, kind: str, identity: str, *args: object, **kwargs: object
        ):
            if identity == "b":
                raise RuntimeError("injected interruption")
            return original(self, kind, identity, *args, **kwargs)

        monkeypatch.setattr(EvidenceRepository, "capture", interrupted)
        with pytest.raises(RuntimeError, match="injected"):
            backfill_evidence(database, batch_size=1)
        with database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["entity_revisions"])
                )
                == 1
            )
        monkeypatch.setattr(EvidenceRepository, "capture", original)
        backfill_evidence(database, batch_size=1)
        backfill_evidence(database, batch_size=1)
        with database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["entity_revisions"])
                )
                == 2
            )
    finally:
        database.close()


def test_downgrade_refuses_to_discard_registered_revisions(
    settings: Settings, account_export: Path
) -> None:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        with pytest.raises(RuntimeError, match="Refusing to discard"):
            with application.database.transaction() as connection:
                config = migration_config()
                config.attributes["connection"] = connection
                command.downgrade(config, "0004_analytics")
        with application.database.transaction() as connection:
            assert current_revision(connection) == "0005_evidence"
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["entity_revisions"])
                )
                > 0
            )


def test_restore_replays_later_withdrawals_and_keeps_absent_target_tombstones(
    settings: Settings,
    account_export: Path,
    tmp_path: Path,
) -> None:
    imported = import_dataset(settings, account_export, "json")
    checkpoint = tmp_path / "checkpoint"
    backup_library(settings, checkpoint)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Later revocation")
            # A post-checkpoint identity must not be resurrected by a later reimport.
            connection.execute(
                metadata.tables["source_records"]
                .insert()
                .values(
                    id="post-checkpoint-source",
                    source_kind="fixture",
                    source_uri="urn:new",
                    permission_basis="owned",
                    retrieved_at=utc_now(),
                )
            )
            withdraw(connection, source_id="post-checkpoint-source", reason="Also revoked")
    restored = tmp_path / "restored-active"
    restore_library(checkpoint, restored, withdrawals_from=settings.data_dir)
    with open_application(Settings(data_dir=restored)) as application:
        with application.database.transaction() as connection:
            snapshot = connection.scalar(
                select(metadata.tables["metric_observations"].c.id).limit(1)
            )
            assert not EvidenceResolver(connection).resolve("metric:" + snapshot).eligible
            journal = metadata.tables["evidence_withdrawals"]
            assert (
                connection.scalar(
                    select(journal.c.reason).where(journal.c.source_id == "post-checkpoint-source")
                )
                == "Also revoked"
            )
    assert verify_backup(checkpoint)["database_revision"] == "0005_evidence"


def test_restore_without_latest_authority_is_restricted_and_never_overwrites(
    settings: Settings,
    account_export: Path,
    tmp_path: Path,
) -> None:
    import_dataset(settings, account_export, "json")
    checkpoint = tmp_path / "checkpoint"
    backup_library(settings, checkpoint)
    restored = tmp_path / "restricted-restore"
    assert restore_library(checkpoint, restored)["status"] == "partial"
    with pytest.raises(ConfigurationError, match="restricted"):
        with open_application(Settings(data_dir=restored)):
            pass
    with pytest.raises(ConfigurationError, match="never overwritten"):
        restore_library(checkpoint, settings.data_dir)
    with pytest.raises(ConfigurationError, match="new destination"):
        backup_library(settings, checkpoint)
    unrelated = Settings(data_dir=tmp_path / "unrelated")
    with open_application(unrelated):
        pass
    with pytest.raises(ConfigurationError, match="lineage"):
        restore_library(
            checkpoint, tmp_path / "wrong-authority", withdrawals_from=unrelated.data_dir
        )


def test_corrupt_backup_and_artifact_escape_are_rejected(
    settings: Settings,
    account_export: Path,
    tmp_path: Path,
) -> None:
    import_dataset(settings, account_export, "json")
    checkpoint = tmp_path / "checkpoint"
    backup_library(settings, checkpoint)
    manifest = json.loads((checkpoint / "manifest.json").read_text())
    artifact = next(key for key in manifest["files"] if key.startswith("artifacts/"))
    (checkpoint / artifact).write_bytes(b"corrupt")
    with pytest.raises(StorageIntegrityError, match="checksum"):
        restore_library(checkpoint, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()
    manifest["files"]["../../escape"] = "invalid"
    (checkpoint / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(StorageIntegrityError):
        verify_backup(checkpoint)
