import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from socialdna import __version__
from socialdna.domain.results import ResultEnvelope
from socialdna.storage.locking import DataDirectoryLock


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "socialdna", *args],
        capture_output=True,
        text=True,
        timeout=45,
        env=env,
    )


@pytest.mark.parametrize(
    "command",
    [("init",), ("doctor",), ("storage", "status"), ("storage", "verify"), ("models", "status")],
)
def test_commands_return_valid_json(command: tuple[str, ...], tmp_path: Path) -> None:
    data = tmp_path / "fresh"
    result = run_cli(*command, "--data-dir", str(data), "--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    envelope = ResultEnvelope.model_validate_json(result.stdout)
    assert envelope.command == ".".join(command)
    assert envelope.status == "success"
    assert envelope.errors == []
    assert result.stderr == ""
    assert (data / "socialdna.db").exists()


def test_global_options_and_version(tmp_path: Path) -> None:
    assert run_cli("--version").stdout.strip() == __version__
    data = tmp_path / "global"
    result = run_cli("--data-dir", str(data), "--format", "json", "storage", "status")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["data"]["data_dir"] == str(data)


def test_help_no_initialization(tmp_path: Path) -> None:
    data = tmp_path / "not-created"
    result = run_cli("--data-dir", str(data), "--help")
    assert result.returncode == 0
    assert "doctor" in result.stdout and "storage" in result.stdout
    assert "analyze" in result.stdout
    assert not data.exists()


@pytest.mark.parametrize(
    "args",
    [
        ("nonsense", "--format", "json"),
        ("init", "--unexpected", "--format=json"),
        ("init", "--config", "/nonexistent/socialdna.toml", "--format", "json"),
    ],
)
def test_input_errors_machine_readable(args: tuple[str, ...]) -> None:
    result = run_cli(*args)
    assert result.returncode == 2, result.stdout + result.stderr
    envelope = ResultEnvelope.model_validate_json(result.stdout)
    assert envelope.status == "error" and envelope.errors
    assert result.stderr == ""


def test_invalid_environment_machine_readable() -> None:
    env = {**os.environ, "SOCIALDNA_LOCK_TIMEOUT": "-10"}
    result = run_cli("init", "--format", "json", env=env)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"][0]["code"] == "invalid_configuration"


def test_text_output_and_missing_media_tools(tmp_path: Path) -> None:
    env = {**os.environ, "PATH": ""}
    result = run_cli("doctor", "--data-dir", str(tmp_path / "no-tools"), env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "doctor: success" in result.stdout
    assert "Warning [ffmpeg]" in result.stderr
    assert "Warning [ffprobe]" in result.stderr


def test_json_schema_fixture_matches_contract() -> None:
    fixture = Path(__file__).parent / "fixtures" / "result-envelope.schema.json"
    assert json.loads(fixture.read_text()) == ResultEnvelope.model_json_schema()


def test_storage_conflict_has_nonzero_json_exit(tmp_path: Path) -> None:
    data = tmp_path / "locked"
    data.mkdir()
    env = {**os.environ, "SOCIALDNA_LOCK_TIMEOUT": "0"}
    with DataDirectoryLock(data / ".socialdna.lock", timeout=0):
        result = run_cli("init", "--data-dir", str(data), "--format", "json", env=env)
    assert result.returncode == 6, result.stdout + result.stderr
    assert json.loads(result.stdout)["errors"][0]["code"] == "storage_conflict"


def test_corrupt_database_has_nonzero_json_exit(tmp_path: Path) -> None:
    data = tmp_path / "corrupted"
    data.mkdir()
    (data / "socialdna.db").write_bytes(b"not a SQLite database")
    result = run_cli("storage", "verify", "--data-dir", str(data), "--format", "json")
    assert result.returncode == 8, result.stdout + result.stderr
    assert json.loads(result.stdout)["errors"][0]["code"] == "storage_integrity"
