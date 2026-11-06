from pathlib import Path

import pytest

from socialdna.application.skill_service import bundle_path, export_skill
from socialdna.core.exceptions import ConfigurationError, StoragePermissionError


def test_export_contains_identical_relative_bundle(tmp_path: Path) -> None:
    target = tmp_path / "socialdna"
    result = export_skill(target)
    assert not result["host_configuration_changed"]
    for name in result["files"]:
        assert (target / name).read_bytes() == (bundle_path() / name).read_bytes()
    with pytest.raises(ConfigurationError, match="exists"):
        export_skill(target)


@pytest.mark.parametrize("name", ["wrong-name", "missing/socialdna"])
def test_export_rejects_wrong_name_or_missing_parent(tmp_path: Path, name: str) -> None:
    with pytest.raises(ConfigurationError):
        export_skill(tmp_path / name)
    assert list(tmp_path.iterdir()) == []


def test_export_permission_failure_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("socialdna.application.skill_service.shutil.copytree", refuse)
    with pytest.raises(StoragePermissionError, match="partial copy"):
        export_skill(tmp_path / "socialdna")
