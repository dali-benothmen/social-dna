import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.enums import AvailabilityStatus
from socialdna.storage.repositories import Repository
from socialdna.storage.schema import metadata


def test_fresh_init_canonical_commit_restart_verify(tmp_path: Path) -> None:
    data = tmp_path / "library with spaces"
    command = [sys.executable, "-m", "socialdna"]
    first = subprocess.run(
        [*command, "doctor", "--data-dir", str(data), "--format", "json"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert first.returncode == 0, first.stderr + first.stdout
    with open_application(Settings(data_dir=data)) as application:
        with application.database.transaction() as connection:
            repository = Repository(connection)
            account = repository.upsert_account("local", "creator", handle="fixture")
            artifact_id = application.artifacts.put_bytes(
                connection, b"research evidence", kind="raw", mime_type="text/plain"
            )
            source_id = repository.record_source(
                source_kind="local",
                source_uri="fixture://owned",
                permission_basis="repository_owned",
                raw_artifact_id=artifact_id,
            )
            repository.set_unavailable(
                subject_type="account",
                subject_id=account,
                field_key="followers",
                status=AvailabilityStatus.NOT_SUPPLIED,
                reason="No analytics supplied",
            )
    second = subprocess.run(
        [*command, "storage", "verify", "--data-dir", str(data), "--format", "json"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert second.returncode == 0, second.stdout + second.stderr
    checks = {item["name"]: item for item in json.loads(second.stdout)["data"]["checks"]}
    assert checks["artifacts.integrity"]["message"] == "Verified 1 registered artifacts."
    with open_application(Settings(data_dir=data)) as application:
        with application.database.transaction() as connection:
            assert Repository(connection).account(account)["handle"] == "fixture"
            source = connection.execute(select(metadata.tables["source_records"])).mappings().one()
            assert source["id"] == source_id and source["raw_artifact_id"] == artifact_id
            assert application.artifacts.reference_count(connection, artifact_id) == 1
    assert list((data / "models").iterdir()) == []
