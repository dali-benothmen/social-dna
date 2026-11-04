from pathlib import Path

import pytest

from socialdna.application.account_import_service import import_dataset
from socialdna.config.settings import Settings


@pytest.mark.parametrize(
    "content", ['{"schema_version":"1.0","schema_version":"2.0"}', '{"profile": {"number": 1e999}}']
)
def test_ambiguous_or_nonfinite_json_is_rejected_without_initialization(
    settings: Settings,
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(content)
    result = import_dataset(settings, path, "json")
    assert not result["valid"] and not settings.data_dir.exists()
