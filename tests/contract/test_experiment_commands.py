"""The delivered analysis-only surface rejects malformed input without library writes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from socialdna.cli.app import app


@pytest.mark.parametrize(
    "group,commands",
    [
        ("experiment", ("register", "import-results", "analyze", "show")),
        ("recommendation", ("create", "show")),
    ],
)
def test_commands_exposed_without_initialization(
    tmp_path: Path, group: str, commands: tuple[str, ...]
) -> None:
    data = tmp_path / "absent"
    result = CliRunner().invoke(app, ["--data-dir", str(data), group, "--help"])
    assert result.exit_code == 0
    assert all(command in result.stdout for command in commands)
    assert not data.exists()


@pytest.mark.parametrize(
    "group,command",
    [
        ("experiment", "register"),
        ("experiment", "import-results"),
        ("recommendation", "create"),
    ],
)
def test_invalid_spec_does_not_initialize(tmp_path: Path, group: str, command: str) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"1.0","unexpected":true}')
    data = tmp_path / "absent"
    result = CliRunner().invoke(
        app, ["--data-dir", str(data), "--format", "json", group, command, "--spec", str(path)]
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "error"
    assert not data.exists()
