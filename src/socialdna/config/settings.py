import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_data_path
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict

from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.providers import Capability, ReasoningProfile


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOCIALDNA_", extra="forbid")
    data_dir: Path = Field(default_factory=lambda: user_data_path("socialdna", appauthor=False))
    lock_timeout: float = Field(default=2.0, ge=0, le=300, allow_inf_nan=False)
    busy_timeout_ms: int = Field(default=5000, ge=0, le=300_000)
    offline: bool = False
    allow_download: bool = False
    remote_media_consent: bool = False
    max_media_bytes: int = Field(default=2_000_000_000, gt=0)
    max_image_pixels: int = Field(default=40_000_000, gt=0, le=80_000_000)
    max_image_bytes: int = Field(default=50_000_000, gt=0, le=200_000_000)
    max_duration_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    max_decode_frames: int = Field(default=36_000, gt=0)
    media_timeout_seconds: float = Field(default=300, gt=0, allow_inf_nan=False)
    asr_model: str = "asr-tiny"
    ocr_model: str = "ocr-en"
    pose_model: str = "pose-lite"
    audio_classifier_model: str = "yamnet"
    alignment_model: str | None = None
    asr_language: str | None = None
    asr_device: str = Field(default="cpu", pattern="^(cpu|cuda|auto)$")
    asr_compute_type: str = Field(default="int8", pattern="^(int8|float16|float32|int8_float16)$")
    inference_timeout_seconds: float = Field(default=300, gt=0, le=3600, allow_inf_nan=False)
    inference_threads: int = Field(default=2, ge=1, le=64)
    provider_python: Path | None = None
    provider_pythons: dict[Capability, Path] = Field(default_factory=dict)
    max_enrichment_frames: int = Field(default=24, ge=1, le=120)
    max_input_bytes: int = Field(default=2_000_000, ge=1000, le=20_000_000)
    max_input_tokens: int = Field(default=16000, ge=100, le=100000)
    max_output_tokens: int = Field(default=2000, ge=100, le=16000)
    max_provider_attempts: int = Field(default=2, ge=1, le=3)
    reasoning_profile: ReasoningProfile | None = None
    youtube_api_key_env: str = Field(
        default="SOCIALDNA_YOUTUBE_API_KEY", pattern=r"^[A-Z][A-Z0-9_]{0,100}$"
    )
    workflow_retention_days: int = Field(default=7, ge=1, le=29)
    workflow_request_timeout_seconds: float = Field(default=20, gt=0, le=60, allow_inf_nan=False)
    workflow_response_byte_limit: int = Field(default=1_048_576, ge=1024, le=10_485_760)

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
