import json
import re
from pathlib import Path

import pytest
from typer.core import TyperGroup, TyperOption
from typer.main import get_command
from typer.testing import CliRunner

from socialdna.application.capability_service import capabilities
from socialdna.application.skill_service import SCHEMAS, bundle_path
from socialdna.cli.app import app
from socialdna.config.settings import Settings
from socialdna.core.enums import ExitCode
from socialdna.domain.capabilities import CapabilityManifest


def test_bundle_links_and_frontmatter_are_self_contained() -> None:
    root = bundle_path()
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: socialdna\n")
    description = text.split("description: ")[1].splitlines()[0]
    assert 0 < len(description) <= 1024
    for document in root.rglob("*.md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if target.startswith("https://"):
                continue
            linked = (document.parent / target).resolve()
            assert linked.is_relative_to(root.resolve()) and linked.is_file(), target


def test_bundled_export_example_validates_without_creating_library(tmp_path: Path) -> None:
    data = tmp_path / "absent"
    example = bundle_path() / "assets" / "account.json"
    result = CliRunner().invoke(
        app,
        ["--data-dir", str(data), "--format", "json", "import", "json", str(example), "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["data"]["valid"] and not data.exists()


def test_documented_commands_flags_and_capability_routes_exist(tmp_path: Path) -> None:
    contract = json.loads((bundle_path() / "references" / "commands.json").read_text())
    paths = set()
    for item in contract["commands"]:
        command = get_command(app)
        for part in item["path"]:
            assert isinstance(command, TyperGroup)
            found = command.commands.get(part)
            assert found is not None, item["path"]
            command = found
        assert set(item["options"]) <= {
            flag
            for parameter in command.params
            if isinstance(parameter, TyperOption)
            for flag in parameter.opts + parameter.secondary_opts
        }, item
        paths.add(tuple(item["path"]))
    for entry in capabilities(Settings(data_dir=tmp_path / "unused"), no_ai=True)["capabilities"]:
        assert all(tuple(path) in paths for path in entry["commands"])
    assert set(contract["exit_codes"].values()) == {int(code) for code in ExitCode}


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_schema_command_returns_actual_contract_without_storage(tmp_path: Path, name: str) -> None:
    data = tmp_path / "absent"
    result = CliRunner().invoke(
        app, ["--data-dir", str(data), "--format", "json", "skill", "schema", name]
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["data"]["schema"] == SCHEMAS[name].model_json_schema()
    assert not data.exists()


def test_preflight_does_not_open_library_and_returns_typed_envelope(tmp_path: Path) -> None:
    data = tmp_path / "absent"
    result = CliRunner().invoke(
        app, ["--data-dir", str(data), "--offline", "--no-ai", "--format", "json", "capabilities"]
    )
    assert result.exit_code == 0, result.stdout
    manifest = CapabilityManifest.model_validate(json.loads(result.stdout)["data"])
    assert manifest.policy["offline"] and manifest.policy["no_ai"]
    assert not data.exists()


def test_unknown_schema_is_actionable_and_machine_readable() -> None:
    result = CliRunner().invoke(app, ["--format", "json", "skill", "schema", "not-supported"])
    assert result.exit_code == 2
    assert "comparison" in json.loads(result.stdout)["errors"][0]["message"]
