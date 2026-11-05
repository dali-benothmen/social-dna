"""Quiescent canonical backups, verified restores and withdrawal reconciliation.

Callers hold the existing data-directory lock. Derived vector data/model weights
are omitted explicitly; managed artifacts and the SQLite checkpoint are verified.
"""

import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from socialdna import __version__
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.core.ids import new_id
from socialdna.core.time import utc_now
from socialdna.storage.locking import DataDirectoryLock

RECOVERY_MARKER = ".socialdna-recovery.json"


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _relative(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or Path(name).is_absolute():
        raise StorageIntegrityError("Backup path escapes its declared root")
    return path


def _integrity(connection: sqlite3.Connection) -> None:
    if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
        raise StorageIntegrityError("Backup SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise StorageIntegrityError("Backup SQLite foreign-key check failed")


def _lineage(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT revision,sha256,applied_at FROM migration_checksums "
        "WHERE revision='0001_foundation'"
    ).fetchone()
    if row is None:
        raise StorageIntegrityError("Backup source has no foundation lineage")
    return hash_config(list(row))


def create_backup(paths: DataPaths, destination: Path) -> dict[str, Any]:
    destination = destination.expanduser().resolve()
    if not paths.database.is_file() or destination.exists():
        raise ConfigurationError(
            "Backup requires an existing database and a new destination directory"
        )
    if destination == paths.root.resolve() or destination.is_relative_to(paths.artifacts.resolve()):
        raise ConfigurationError("Backup destination cannot be the library or its artifacts")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _connect(paths.database) as connection:
        _integrity(connection)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        lineage = _lineage(connection)
        artifacts = [dict(row) for row in connection.execute("SELECT * FROM artifact_objects")]
        dependencies = []
        if "media_assets" in tables:
            dependencies = [
                dict(row)
                for row in connection.execute(
                    "SELECT id, original_uri, sha256 FROM media_assets WHERE artifact_id IS NULL"
                )
            ]
        needed = paths.database.stat().st_size + sum(row["byte_size"] for row in artifacts)
        if shutil.disk_usage(destination.parent).free < needed * 2 + 1024 * 1024:
            raise StorageIntegrityError("Insufficient space for a verified pre-upgrade backup")
        destination.mkdir()
        # Incomplete destinations are retained for inspection on failure; no cleanup
        # routine can accidentally erase the original library or another backup.
        with closing(sqlite3.connect(destination / "socialdna.db")) as backup:
            connection.backup(backup)
        files = {"socialdna.db": hash_file(destination / "socialdna.db")}
        for row in artifacts:
            name = row["relative_path"]
            source = _relative(paths.root, name)
            if not source.is_relative_to(paths.artifacts.resolve()) or not source.is_file():
                raise StorageIntegrityError("Backup artifact is missing or outside managed storage")
            if source.stat().st_size != row["byte_size"] or hash_file(source) != row["sha256"]:
                raise StorageIntegrityError("Backup source artifact checksum mismatch")
            target = _relative(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files[name] = row["sha256"]
    manifest = {
        "schema_version": "1.0",
        "engine_version": __version__,
        "created_at": utc_now(),
        "source_root": str(paths.root.resolve()),
        "database_revision": revision,
        "library_lineage": lineage,
        "files": files,
        "external_media_dependencies": dependencies,
        "self_contained_for_media_reanalysis": not dependencies,
        "models": "not_included; prepared model manifests/runtimes remain external dependencies",
        "vectors": "omitted_rebuild_required; canonical SQLite and artifacts are authoritative",
        "retention": "Reconcile later withdrawal/erasure obligations before normal restore use.",
    }
    (destination / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    verify_backup(destination)
    return {"path": str(destination), "verified": True, "manifest": manifest}


def verify_backup(destination: Path) -> dict[str, Any]:
    try:
        manifest: dict[str, Any] = json.loads(
            (destination / "manifest.json").read_text(encoding="utf-8")
        )
        if manifest["schema_version"] != "1.0" or "socialdna.db" not in manifest["files"]:
            raise ValueError("Unknown backup manifest")
        for name, checksum in manifest["files"].items():
            if name != "socialdna.db" and not name.startswith("artifacts/objects/"):
                raise ValueError("Unexpected backup file")
            if hash_file(_relative(destination, name)) != checksum:
                raise ValueError("Backup file checksum mismatch")
        with _connect(destination / "socialdna.db") as connection:
            _integrity(connection)
            if _lineage(connection) != manifest["library_lineage"]:
                raise ValueError("Backup lineage mismatch")
            artifacts = connection.execute("SELECT relative_path,sha256 FROM artifact_objects")
            if any(manifest["files"].get(row[0]) != row[1] for row in artifacts):
                raise ValueError("Backup manifest omits canonical artifacts")
        return manifest
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        raise StorageIntegrityError(f"Backup verification failed: {exc}") from exc


def backup_library(settings: Settings, destination: Path) -> dict[str, Any]:
    paths = DataPaths(settings.data_dir)
    if not paths.database.is_file():
        raise ConfigurationError("No initialized library to back up")
    with DataDirectoryLock(paths.lock, timeout=settings.lock_timeout):
        assert_recovery_ready(paths)
        return create_backup(paths, destination)


def restore_library(
    backup: Path,
    destination: Path,
    *,
    withdrawals_from: Path | None = None,
) -> dict[str, Any]:
    backup, destination = backup.expanduser().resolve(), destination.expanduser().resolve()
    manifest = verify_backup(backup)
    if destination.exists():
        raise ConfigurationError(
            "Restore requires a new separate destination; existing data is never overwritten"
        )
    if destination.is_relative_to(backup) or backup.is_relative_to(destination):
        raise ConfigurationError("Restore and backup paths must be separate")
    obligations: list[dict[str, Any]] | None = None
    if withdrawals_from is not None:
        witness = DataPaths(withdrawals_from.expanduser().resolve())
        if not witness.database.is_file():
            raise ConfigurationError("The latest withdrawal authority must be an existing library")
        if (witness.root / "manifest.json").is_file():
            raise ConfigurationError(
                "A backup checkpoint cannot attest the latest withdrawal authority"
            )
        with DataDirectoryLock(witness.lock):
            assert_recovery_ready(witness)
            with _connect(witness.database) as connection:
                _integrity(connection)
                if _lineage(connection) != manifest["library_lineage"]:
                    raise ConfigurationError(
                        "Withdrawal authority is from a different library lineage"
                    )
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
                head = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                if head not in (
                    "0001_foundation",
                    "0002_timeline",
                    "0003_enrichment",
                    "0004_analytics",
                    "0005_evidence",
                    "0006_designs",
                    "0007_creative",
                ):
                    raise StorageIntegrityError("Withdrawal authority has an unsupported schema")
                obligations = (
                    [dict(row) for row in connection.execute("SELECT * FROM evidence_withdrawals")]
                    if "evidence_withdrawals" in tables
                    else []
                )
    destination.mkdir(parents=True)
    # Gate access before copying anything, including interrupted restores.
    marker: dict[str, Any] = {
        "status": "restricted",
        "reason": "Restore incomplete or latest withdrawal obligations unknown",
    }
    marker_path = destination / RECOVERY_MARKER
    marker_path.write_text(canonical_json(marker), encoding="utf-8")
    for name in manifest["files"]:
        target = _relative(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_relative(backup, name), target)
    with _connect(destination / "socialdna.db") as connection:
        _integrity(connection)
    marker.update(
        status="pending_reconciliation" if obligations is not None else "restricted",
        obligations=obligations,
        authority=str(withdrawals_from) if withdrawals_from else None,
    )
    marker_path.write_text(canonical_json(marker), encoding="utf-8")
    return {
        "path": str(destination),
        "verified": True,
        "status": "success" if obligations is not None else "partial",
        "recovery": marker["status"],
        "limitations": [
            "External media/model inputs are not included; derived indices require rebuild.",
            *(
                []
                if obligations is not None
                else ["Latest withdrawal authority unknown; normal library access is blocked."]
            ),
        ],
    }


def assert_recovery_ready(paths: DataPaths, *, allow_pending: bool = False) -> None:
    marker_path = paths.root / RECOVERY_MARKER
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            allowed = ("ready", "pending_reconciliation") if allow_pending else ("ready",)
            if marker["status"] not in allowed:
                raise ConfigurationError(
                    "Restored library is restricted: "
                    "establish the latest withdrawal obligations before use"
                )
        except (OSError, ValueError, KeyError) as exc:
            raise StorageIntegrityError("Invalid recovery marker; normal use is blocked") from exc


def reconcile_restore(paths: DataPaths, database: Any) -> None:
    marker_path = paths.root / RECOVERY_MARKER
    if not marker_path.exists():
        return
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker["status"] != "pending_reconciliation":
        return
    from sqlalchemy.dialects.sqlite import insert

    from socialdna.storage.schema import metadata

    with database.transaction() as connection:
        for row in marker["obligations"]:
            connection.execute(
                insert(metadata.tables["evidence_withdrawals"])
                .values(**row)
                .on_conflict_do_nothing()
            )
    marker["status"] = "ready"
    marker_path.write_text(canonical_json(marker), encoding="utf-8")


def prepare_upgrade(paths: DataPaths, database: Any) -> None:
    """Called under the writer lock before any installed migration is applied."""
    from alembic.script import ScriptDirectory

    from socialdna.storage.migration_runner import (
        current_revision,
        migration_config,
        validate_history,
    )

    scripts = ScriptDirectory.from_config(migration_config())
    with database.transaction() as connection:
        validate_history(connection, scripts)
        revision = current_revision(connection)
    head = scripts.get_current_head()
    if revision and revision != head:
        create_backup(paths, paths.root / "backups" / (f"pre-{head}-" + new_id()))
