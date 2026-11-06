import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from socialdna.cli.app import app


@pytest.mark.parametrize("command", ["image", "carousel"])
def test_static_help_does_not_initialize(tmp_path: Path, command: str) -> None:
    data = tmp_path / "absent"
    result = CliRunner().invoke(app, ["--data-dir", str(data), "analyze", command, "--help"])
    assert result.exit_code == 0 and not data.exists()


@pytest.mark.parametrize(
    "args",
    [("image", "missing.png", "--max-side", "1"), ("carousel", "unknown", "--max-items", "0")],
)
def test_invalid_budget_is_rejected_before_opening_library(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    data = tmp_path / "absent"
    result = CliRunner().invoke(
        app, ["--data-dir", str(data), "--format", "json", "analyze", *args]
    )
    assert result.exit_code == 2 and json.loads(result.stdout)["status"] == "error"
    assert not data.exists()
