import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from socialdna.cli.app import app


@pytest.mark.parametrize("command", ["import-literature", "prepare", "evaluate"])
def test_invalid_research_spec_does_not_initialize_storage(command: str, tmp_path: Path) -> None:
    spec = tmp_path / "invalid.json"
    spec.write_text('{"schema_version":"unsupported","invented":true}')
    destination = tmp_path / "library"
    result = CliRunner().invoke(
        app,
        [
            "--data-dir",
            str(destination),
            "--offline",
            "--format",
            "json",
            "research",
            command,
            "--spec",
            str(spec),
        ],
    )
    assert result.exit_code == 2, result.stdout
    assert json.loads(result.stdout)["status"] == "error"
    assert not destination.exists()


def test_corpus_import_command_is_real_and_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "examples/research/literature.json"
    arguments = [
        "--data-dir",
        str(tmp_path / "library"),
        "--offline",
        "--format",
        "json",
        "research",
        "import-literature",
        "--spec",
        str(source),
    ]
    first = CliRunner().invoke(app, arguments)
    second = CliRunner().invoke(app, arguments)
    assert first.exit_code == second.exit_code == 0, first.stdout + second.stdout
    a, b = json.loads(first.stdout)["data"], json.loads(second.stdout)["data"]
    assert a["sources"] == b["sources"] and a["citations"] == b["citations"]
    assert len(a["findings"]) == 2
