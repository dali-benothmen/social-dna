import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_data_path
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict

from socialdna.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOCIALDNA_", extra="forbid")
    data_dir: Path = Field(default_factory=lambda: user_data_path("socialdna", appauthor=False))
    lock_timeout: float = Field(default=2.0, ge=0, le=300, allow_inf_nan=False)
    busy_timeout_ms: int = Field(default=5000, ge=0, le=300_000)
    offline: bool = False
    allow_download: bool = False
    remote_media_consent: bool = False
    max_media_bytes: int = Field(default=2_000_000_000, gt=0)
    max_duration_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    max_decode_frames: int = Field(default=36_000, gt=0)
    media_timeout_seconds: float = Field(default=300, gt=0, allow_inf_nan=False)

    @classmethod
    def load(cls, *, config_file: Path | None = None, **overrides: Any) -> "Settings":
        """Precedence: CLI > environment > explicit TOML > platform defaults."""
        values: dict[str, Any] = {}
        if config_file is not None:
            try:
                with config_file.open("rb") as stream:
                    document = tomllib.load(stream)
                values = document.get("socialdna", {})
                if not isinstance(values, dict):
                    raise ValueError("[socialdna] must be a TOML table")
            except (OSError, ValueError) as exc:
                raise ConfigurationError(f"Cannot read configuration: {exc}") from exc
        # Merge raw source values first, then validate once. A CLI value must also
        # override an invalid lower-priority environment value.
        try:
            values.update(EnvSettingsSource(cls)())
            values.update({key: value for key, value in overrides.items() if value is not None})
            settings = cls(**values)
            settings.data_dir = settings.data_dir.expanduser().absolute()
            return settings
        except ValidationError as exc:
            raise ConfigurationError(str(exc)) from exc
