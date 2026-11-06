import re
from pathlib import Path

import pytest

from socialdna.application.skill_service import export_skill
from socialdna.core.exceptions import ConfigurationError


@pytest.mark.parametrize(
    "name",
    [
        "social-dna-ingest",
        "social-dna-report",
        "social-dna-analyze",
        "social-dna-reconstruct",
        "social-dna-account",
        "social-dna-research",
        "social-dna-compare",
        "social-dna-evidence",
    ],
)
@pytest.mark.parametrize("host", [".agents", ".claude", ".opencode"])
def test_each_task_skill_exports_independently_with_shared_reference(tmp_path, name, host):
    parent = tmp_path / host / "skills"
    parent.mkdir(parents=True)
    destination = parent / name
    result = export_skill(destination, name)
    assert set(result["files"]) == {"SKILL.md", "references/workflow.md", "references/setup.md"}
    assert not result["host_configuration_changed"]
    text = (destination / "SKILL.md").read_text()
    assert text.startswith("---\nname: " + name + "\n")
    for relative in result["files"]:
        document = destination / relative
        if document.suffix != ".md":
            continue
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text()):
            if "://" in link or link.startswith("#"):
                continue
            target = (document.parent / link).resolve()
            assert target.is_relative_to(destination.resolve()) and target.is_file()
    with pytest.raises(ConfigurationError):
        export_skill(destination, name)


def test_export_refuses_unimplemented_skills(tmp_path: Path):
    with pytest.raises(ConfigurationError, match="implemented"):
        export_skill(tmp_path / "social-dna-discover", "social-dna-discover")
