from pathlib import Path

import pytest
from sqlalchemy import select

from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import StorageIntegrityError
from socialdna.storage.health import storage_verify
from socialdna.storage.repositories import Repository
from socialdna.storage.schema import metadata


def test_deduplication_references_and_checksum(settings: Settings, tmp_path: Path) -> None:
    source = tmp_path / "a file ; $(unsafe).txt"
    source.write_bytes(b"authorized source")
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            artifacts = application.artifacts
            first = artifacts.put_file(connection, source, kind="raw", mime_type="text/plain")
            second = artifacts.put_bytes(
                connection, source.read_bytes(), kind="raw", mime_type="text/plain"
            )
            assert first == second
            owner_id = Repository(connection).upsert_account("local", "owner")
            for _ in range(2):
                artifacts.add_reference(
                    connection, first, owner_type="account", owner_id=owner_id, role="source"
                )
            assert artifacts.reference_count(connection, first) == 1
            Repository(connection).record_source(
                source_kind="local",
                source_uri=source.as_uri(),
                permission_basis="owner_supplied",
                raw_artifact_id=first,
            )
            assert artifacts.reference_count(connection, first) == 2
            row = artifacts.get(connection, first)
            assert artifacts.verify(row)
            assert len(list(connection.execute(select(metadata.tables["artifact_objects"])))) == 1
        path = artifacts.path_for(row["relative_path"])
        path.write_bytes(b"tampered data")
        with application.database.transaction() as connection:
            with pytest.raises(StorageIntegrityError, match="corrupt"):
                artifacts.put_file(connection, source, kind="raw", mime_type="text/plain")
    checks = {check.name: check for check in storage_verify(settings)}
    assert checks["artifacts.integrity"].status == "error"
    assert checks["artifacts.integrity"].details["failed_ids"] == [first]


def test_artifact_escape_and_rollback_orphan(settings: Settings) -> None:
    with open_application(settings) as application:
        with pytest.raises(StorageIntegrityError, match="escapes"):
            application.artifacts.path_for("../../outside")
        with pytest.raises(RuntimeError), application.database.transaction() as connection:
            application.artifacts.put_bytes(
                connection, b"uncommitted", kind="raw", mime_type="application/octet-stream"
            )
            raise RuntimeError("interrupted canonical commit")
    checks = {check.name: check for check in storage_verify(settings)}
    assert checks["artifacts.unregistered"].status == "warning"
    assert len(checks["artifacts.unregistered"].details["objects"]) == 1


def test_artifact_symlink_escape(settings: Settings, tmp_path: Path) -> None:
    with open_application(settings) as application:
        try:
            (application.paths.artifacts / "outside").symlink_to(tmp_path, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"Symlink creation is unavailable on this test host: {exc}")
        with pytest.raises(StorageIntegrityError, match="escapes"):
            application.artifacts.path_for("artifacts/outside/secret")
