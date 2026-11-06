import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from socialdna.config.settings import Settings
from socialdna.core.enums import ExitCode
from socialdna.core.exceptions import (
    ConfigurationError,
    DependencyUnavailable,
    StorageConflict,
    StorageIntegrityError,
    StoragePermissionError,
)
from socialdna.core.hashing import hash_config, hash_file
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import MediaInterval, format_utc
from socialdna.domain.results import ResultEnvelope


@given(st.integers(0, 1_000_000), st.integers(1, 1_000_000))
def test_interval_properties(start: int, duration: int) -> None:
    interval = MediaInterval(start_ms=start, end_ms=start + duration)
    neighbor = MediaInterval(start_ms=interval.end_ms, end_ms=interval.end_ms + 1)
    assert not interval.overlaps(neighbor)
    assert interval.overlaps(interval)


@pytest.mark.parametrize("start,end", [(0, 0), (2, 1), (-1, 1), (True, 4), (1.2, 4)])
def test_invalid_intervals(start: object, end: object) -> None:
    with pytest.raises(ValidationError):
        MediaInterval(start_ms=start, end_ms=end)


@given(st.text(), st.text())
def test_stable_ids(first: str, second: str) -> None:
    result = stable_id("post", first, second)
    assert result == stable_id("post", first, second)
    assert UUID(result).version == 5
    assert result != stable_id("account", first, second)


def test_ids_unambiguous_and_random() -> None:
    assert stable_id("account", "a:b", "c") != stable_id("account", "a", "b:c")
    assert new_id() != new_id()
    assert UUID(new_id()).version == 4
    with pytest.raises(ValueError):
        stable_id("account")


def test_utc_serialization() -> None:
    local = datetime(2026, 11, 4, 12, tzinfo=timezone(timedelta(hours=1)))
    assert format_utc(local) == "2026-11-04T11:00:00.000000Z"
    assert format_utc(local.astimezone(UTC)) == format_utc(local)
    with pytest.raises(ValueError):
        format_utc(datetime(2026, 11, 4))


def test_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"example")
    assert hash_file(source) == hashlib.sha256(b"example").hexdigest()
    assert hash_file(source, byte_limit=7) == hashlib.sha256(b"example").hexdigest()
    with pytest.raises(ValueError, match="limit"):
        hash_file(source, byte_limit=6)
    with pytest.raises(ValueError, match="non-negative"):
        hash_file(source, byte_limit=-1)
    assert hash_config({"b": 2, "a": 1}) == hash_config({"a": 1, "b": 2})
    with pytest.raises(ValueError):
        hash_config(float("nan"))


def test_settings_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.toml"
    file_directory = tmp_path / "from-file"
    config.write_text(
        "[socialdna]\ndata_dir=" + json.dumps(str(file_directory)) + "\nlock_timeout=4\n"
    )
    monkeypatch.setenv("SOCIALDNA_LOCK_TIMEOUT", "6")
    assert Settings.load(config_file=config).lock_timeout == 6
    assert Settings.load(config_file=config, lock_timeout=8).lock_timeout == 8
    monkeypatch.setenv("SOCIALDNA_LOCK_TIMEOUT", "invalid-shadowed-value")
    assert Settings.load(config_file=config, lock_timeout=9).lock_timeout == 9
    monkeypatch.delenv("SOCIALDNA_LOCK_TIMEOUT")
    assert Settings.load(config_file=config).lock_timeout == 4
    monkeypatch.delenv("SOCIALDNA_DATA_DIR")
    assert Settings.load(config_file=config).data_dir == file_directory
    assert Settings.load().data_dir.is_absolute()


def test_invalid_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    for content in ("[socialdna]\nunknown=true", "socialdna=4", "[broken"):
        config.write_text(content)
        with pytest.raises(ConfigurationError):
            Settings.load(config_file=config)
    with pytest.raises(ConfigurationError):
        Settings.load(lock_timeout=-1)


def test_envelope_contract() -> None:
    result = ResultEnvelope(command="init")
    assert ResultEnvelope.model_validate_json(result.model_dump_json()) == result
    assert result.run_id is None
    assert result.evidence == []
    assert result.model_dump().keys() == {
        "schema_version",
        "command",
        "status",
        "run_id",
        "data",
        "evidence",
        "warnings",
        "limitations",
        "errors",
        "next_actions",
    }
    with pytest.raises(ValidationError):
        ResultEnvelope(command="init", status="finished")


def test_error_codes() -> None:
    assert ConfigurationError.exit_code == ExitCode.INVALID_INPUT
    assert DependencyUnavailable.exit_code == ExitCode.UNAVAILABLE
    assert StorageConflict.exit_code == ExitCode.STORAGE_CONFLICT
    assert StoragePermissionError.exit_code == ExitCode.PERMISSION
    assert StorageIntegrityError.exit_code == ExitCode.STORAGE_INTEGRITY
