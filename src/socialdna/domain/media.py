from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MediaInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_ms: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    video_stream_index: int
    audio_stream_index: int | None = None
    origin_seconds: float
    video_start_ms: int = 0
    audio_start_ms: int | None = None
    frame_rate: float = Field(gt=0)
    time_base: str
    rotation: int = 0
    format_name: str
    streams: list[dict[str, Any]]
    raw: dict[str, Any]


class AnalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    depth: Literal["quick", "standard", "deep"] = "standard"
    palette_bins: int = Field(default=8, ge=2, le=32)
    max_frames: int = Field(default=120, ge=2, le=1000)
    scene_threshold: float = Field(default=3.0, gt=0, le=100, allow_inf_nan=False)
    silence_db: float = Field(default=-45, ge=-100, le=-1, allow_inf_nan=False)
    no_ai: bool = False
    transcribe: bool | None = None
    ocr: bool | None = None
    align: bool = False
    pose: bool = False
    classify_audio: bool = False
    reason: bool = False

    @property
    def sample_ms(self) -> int:
        return {"quick": 2000, "standard": 1000, "deep": 250}[self.depth]
