import io
import runpy
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from socialdna.application.skill_service import BUNDLES, UMBRELLA_FILES

ROOT = Path(__file__).resolve().parents[2]
audit = runpy.run_path(str(ROOT / "scripts/check_distribution.py"))["audit_archive"]


@pytest.mark.parametrize(
    "member",
    [
        "../escape",
        "/absolute",
        "x/.env",
        "x/.env.production",
        "x/.agents/skills/private.md",
        "x/auth.json",
        "x/credentials.json",
        "x/data.db",
        "x/private.key",
        "x/evil\\name",
        "C:/absolute",
        "x/file:stream",
        "x/state.db-wal",
        "x/state.sqlite3-shm",
    ],
)
@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_archive_audit_refuses_unsafe_or_private_paths(tmp_path, member, kind):
    archive = tmp_path / ("test.whl" if kind == "wheel" else "test.tar.gz")
    if kind == "wheel":
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr(member, "synthetic-canary")
    else:
        with tarfile.open(archive, "w:gz") as stream:
            info = tarfile.TarInfo(member)
            info.size = len(b"synthetic-canary")
            stream.addfile(info, io.BytesIO(b"synthetic-canary"))
    with pytest.raises(RuntimeError, match="Unsafe or private"):
        audit(archive)


def test_archive_audit_refuses_links_without_extracting(tmp_path):
    archive = tmp_path / "test.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        info = tarfile.TarInfo("normal-looking-name")
        info.type = tarfile.SYMTYPE
        info.linkname = "/private"
        stream.addfile(info)
    with pytest.raises(RuntimeError):
        audit(archive)
    assert list(tmp_path.iterdir()) == [archive]


def test_wheel_resource_mapping_is_an_exact_public_allowlist():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    mapping = configuration["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    expected = {"skills/socialdna/" + name for name in UMBRELLA_FILES}
    expected |= {"skills/" + name + "/SKILL.md" for name in BUNDLES if name != "socialdna"}
    expected.add("skills/shared/workflow.md")
    assert set(mapping) == expected
    assert all((ROOT / source).is_file() for source in mapping)
