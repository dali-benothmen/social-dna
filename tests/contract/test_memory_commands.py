import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from socialdna.cli.app import app
from socialdna.core.enums import ExitCode


@pytest.mark.parametrize(
    "arguments",
    [
        ["query", "opening", "--mode", "invented"],
        ["query", "opening", "--as-of", "2026-01-01"],
        ["query", "opening", "--limit", "0"],
        ["memory", "register-space", "missing-space.json"],
        ["graph", "neighbors", "not-a-revision", "--as-of", "naive-cutoff"],
        ["storage", "reconcile", "--vectors"],
    ],
)
def test_invalid_memory_commands_are_actionable_json(arguments: list[str], tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["--data-dir", str(tmp_path / "library"), "--format", "json", *arguments]
    )
    assert result.exit_code == ExitCode.INVALID_INPUT, result.stdout
    document = json.loads(result.stdout)
    assert document["status"] == "error"
    assert document["errors"][0]["code"] == "invalid_configuration"
