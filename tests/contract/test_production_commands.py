import json
from pathlib import Path

from typer.testing import CliRunner

from socialdna.cli.app import app


def test_invalid_professional_annotations_do_not_initialize_storage(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "key": "invalid",
                "events": [{"technique": "guaranteed_viral_editing"}],
            }
        )
    )
    destination = tmp_path / "not-created"
    result = CliRunner().invoke(
        app,
        [
            "--data-dir",
            str(destination),
            "--offline",
            "--format",
            "json",
            "creative",
            "import",
            str(path),
        ],
    )
    assert result.exit_code == 2, result.output
    assert not destination.exists()


def test_definitions_publish_both_frozen_and_professional_versions(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "--data-dir",
            str(tmp_path / "library"),
            "--offline",
            "--format",
            "json",
            "creative",
            "definitions",
        ],
    )
    assert result.exit_code == 0, result.output
    definitions = json.loads(result.stdout)["data"]
    recipes = {r["id"]: r for r in definitions["recipes"]}
    assert recipes["creative.result_first.v1"]["version"] == "1.0"
    assert recipes["creative.shot_duration_mean.v2"]["version"] == "2.0"
    assert {t["key"] for t in definitions["techniques"]} >= {
        "camera_movement",
        "subject_movement",
        "music_beat",
    }
