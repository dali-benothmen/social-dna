import os
from pathlib import Path

import pytest

from socialdna.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("SOCIALDNA_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("SOCIALDNA_DATA_DIR", str(tmp_path / "default-data"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", lock_timeout=0)
