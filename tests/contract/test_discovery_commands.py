import json
from pathlib import Path

from typer.testing import CliRunner

from socialdna.cli.app import app
from socialdna.research.candidates import DiscoverySpec


def test_published_example_matches_delivered_schema_and_exact_fit_budget() -> None:
    spec = DiscoverySpec.model_validate_json(Path("examples/research/discovery.json").read_text())
    assert sum(3 * len(c.alphas) + 1 for c in spec.candidates) + 1 == spec.max_fits


def test_invalid_discovery_spec_is_rejected_before_initializing_library(tmp_path: Path) -> None:
    source = json.loads(Path("examples/research/discovery.json").read_text())
    source["max_fits"] = 1
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(source))
    data = tmp_path / "must-not-initialize"
    result = CliRunner().invoke(
        app,
        ["--data-dir", str(data), "--format", "json", "research", "discover", "--spec", str(path)],
    )
    assert result.exit_code != 0 and "budget" in result.stdout
    assert not data.exists()


def test_delivered_discovery_commands_are_exposed() -> None:
    result = CliRunner().invoke(app, ["research", "--help"])
    assert result.exit_code == 0
    assert all(
        name in result.stdout for name in ("discover", "confirm-discovery", "show-discovery")
    )
