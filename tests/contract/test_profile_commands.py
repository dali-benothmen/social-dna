import json
from pathlib import Path

from typer.testing import CliRunner

from socialdna.cli.app import app


def test_rubric_and_invalid_specs_are_offline_and_do_not_initialize(tmp_path: Path) -> None:
    data = tmp_path / "no-library"
    prefix = ["--data-dir", str(data), "--format", "json", "profile"]
    result = CliRunner().invoke(app, [*prefix, "rubric"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)["data"]["rubric"]["criteria"]) == 6
    assert not data.exists()
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"unsupported"}')
    for command in (["import", str(path), "--dry-run"], ["report", str(path)]):
        result = CliRunner().invoke(app, [*prefix, *command])
        assert result.exit_code != 0 and json.loads(result.stdout)["status"] == "error"
        assert not data.exists()
