import json
from pathlib import Path

from typer.testing import CliRunner

from socialdna.cli.app import app


def test_invalid_reevaluation_spec_does_not_initialize_library(tmp_path: Path) -> None:
    spec = tmp_path / "invalid.json"
    spec.write_text('{"max_analyses":999,"invented":true}')
    destination = tmp_path / "not-initialized"
    result = CliRunner().invoke(
        app,
        [
            "--data-dir",
            str(destination),
            "--format",
            "json",
            "research",
            "reevaluate",
            "assessment",
            "--spec",
            str(spec),
        ],
    )
    assert result.exit_code == 2, result.stdout
    assert json.loads(result.stdout)["status"] == "error"
    assert not destination.exists()
