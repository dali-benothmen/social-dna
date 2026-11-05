import json
from pathlib import Path

from typer.testing import CliRunner

from socialdna.cli.app import app


def test_templates_are_distinct_and_invalid_import_does_not_initialize(tmp_path: Path) -> None:
    library = tmp_path / "library"
    prefix = ["--data-dir", str(library), "--format", "json", "platform"]
    template = CliRunner().invoke(app, [*prefix, "templates"])
    assert template.exit_code == 0
    surfaces = json.loads(template.stdout)["data"]["surfaces"]
    assert surfaces["instagram"] != surfaces["tiktok"] != surfaces["youtube"]
    assert not library.exists()
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"unsupported"}')
    for command in (["import", str(path), "--dry-run"], ["report", str(path)]):
        result = CliRunner().invoke(app, [*prefix, *command])
        assert result.exit_code != 0 and json.loads(result.stdout)["status"] == "error"
        assert not library.exists()
