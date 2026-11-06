import hashlib
import shutil
from pathlib import Path

import pytest

from socialdna.application import skill_service
from socialdna.application.skill_service import bundle_path, export_skill, inspect_bundle
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

    monkeypatch.setattr(skill_service, "_write_resource", refuse)
    with pytest.raises(StoragePermissionError, match="incomplete"):
        export_skill(tmp_path / "socialdna")
    assert not (tmp_path / "socialdna").exists()


def test_inspection_hashes_match_export_and_skip_unreviewed_files(tmp_path, monkeypatch):
    source = tmp_path / "source"
    shutil.copytree(bundle_path(), source)
    (source / ".env").write_text("SYNTHETIC_SECRET_CANARY")
    (source / "references" / "extra.md").write_text("unreviewed")
    monkeypatch.setattr(skill_service, "bundle_path", lambda name="socialdna": source)
    manifest = inspect_bundle()
    target = tmp_path / "socialdna"
    result = export_skill(target)
    assert result["sha256"] == manifest["sha256"]
    assert ".env" not in result["files"] and "references/extra.md" not in result["files"]
    for name, checksum in result["sha256"].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == checksum


@pytest.mark.parametrize("damage", ["missing", "symlink", "oversize", "metadata"])
def test_invalid_resource_refused_before_destination_write(tmp_path, monkeypatch, damage):
    source = tmp_path / "source"
    shutil.copytree(bundle_path(), source)
    path = source / "SKILL.md"
    if damage == "missing":
        path.unlink()
    elif damage == "symlink":
        path.unlink()
        try:
            path.symlink_to(source / "LICENSE")
        except OSError:
            pytest.skip("Symlinks unavailable on this host")
    elif damage == "oversize":
        path.write_bytes(b"x" * 1_000_001)
    else:
        path.write_text("---\nname: wrong\n")
    monkeypatch.setattr(skill_service, "bundle_path", lambda name="socialdna": source)
    with pytest.raises(ConfigurationError):
        export_skill(tmp_path / "socialdna")
    assert not (tmp_path / "socialdna").exists()


def test_skill_entrypoint_is_published_last_and_partial_write_rolls_back(tmp_path, monkeypatch):
    written = []
    real_write = skill_service._write_resource

    def fail_after_support(path, content):
        assert not (tmp_path / "socialdna" / "SKILL.md").exists()
        written.append(path.name)
        if path.name == "SKILL.md":
            raise OSError("Synthetic interrupted publication")
        real_write(path, content)

    monkeypatch.setattr(skill_service, "_write_resource", fail_after_support)
    with pytest.raises(StoragePermissionError):
        export_skill(tmp_path / "socialdna")
    assert written[-1] == "SKILL.md" and len(written) > 1
    assert not (tmp_path / "socialdna").exists()


def test_concurrent_destination_is_never_overwritten(tmp_path, monkeypatch):
    target = tmp_path / "socialdna"
    original = skill_service._bundle_contents

    def competing_install(name):
        contents = original(name)
        target.mkdir()
        (target / "user-file").write_text("preserve")
        return contents

    monkeypatch.setattr(skill_service, "_bundle_contents", competing_install)
    with pytest.raises(ConfigurationError, match="exists"):
        export_skill(target)
    assert (target / "user-file").read_text() == "preserve"


def test_entrypoint_link_failure_is_cleaned_without_partial_skill(tmp_path, monkeypatch):
    def refuse(*args):
        assert not (tmp_path / "socialdna" / "SKILL.md").exists()
        raise OSError("Synthetic filesystem publication failure")

    monkeypatch.setattr(Path, "hardlink_to", refuse)
    with pytest.raises(StoragePermissionError):
        export_skill(tmp_path / "socialdna")
    assert not (tmp_path / "socialdna").exists()


def test_windows_line_endings_validate_without_changing_exported_bytes(tmp_path, monkeypatch):
    source = tmp_path / "source"
    shutil.copytree(bundle_path(), source)
    original = (source / "SKILL.md").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    (source / "SKILL.md").write_bytes(original)
    monkeypatch.setattr(skill_service, "bundle_path", lambda name="socialdna": source)
    target = tmp_path / "socialdna"
    result = export_skill(target)
    assert (target / "SKILL.md").read_bytes() == original
    assert result["sha256"]["SKILL.md"] == hashlib.sha256(original).hexdigest()
