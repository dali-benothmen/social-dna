from pathlib import Path

from pydantic import BaseModel, ConfigDict


class StorageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_dir: Path | None = None
    config_file: Path | None = None
