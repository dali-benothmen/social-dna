import json
from pathlib import Path

import pytest

from socialdna.core.exceptions import ConfigurationError, StoragePermissionError
from socialdna.reporting.export import export_report


@pytest.mark.parametrize("format", ["json", "markdown"])
def test_export_is_utf8_content_not_envelope_and_never_overwrites(
    tmp_path: Path, format: str
) -> None:
    content = (
        {"caption": "طبخ café"} if format == "json" else "# طبخ café\n\nEscaped &lt;script&gt;\n"
    )
    report = {"format": format, "content": content}
    destination = tmp_path / "a report"
    assert export_report(report, destination) == str(destination)
    saved = destination.read_text(encoding="utf-8")
    assert (json.loads(saved) if format == "json" else saved) == content
    with pytest.raises(ConfigurationError, match="exists"):
        export_report(report, destination)
    assert destination.read_text(encoding="utf-8") == saved


def test_export_missing_parent_does_not_create_directories(tmp_path: Path) -> None:
    with pytest.raises(StoragePermissionError, match="parent"):
        export_report({"format": "markdown", "content": "report"}, tmp_path / "missing" / "a.md")
    assert not (tmp_path / "missing").exists()


def test_export_refuses_symlink_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "important"
    target.write_text("keep")
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation unavailable for this account")
    with pytest.raises(ConfigurationError):
        export_report({"format": "markdown", "content": "replace"}, link)
    assert target.read_text() == "keep"
