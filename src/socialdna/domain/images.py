"""Static media contracts; positions and regions are never playback intervals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImageOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    palette_bins: int = Field(default=8, ge=2, le=32)
    max_side: int = Field(default=1024, ge=64, le=2048)
    ocr: bool = False
    no_ai: bool = False


class ImageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    media_type: Literal["image"] = "image"
    format: str
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    orientation_applied: int = Field(ge=1, le=8)
    alpha: bool
    metadata_policy: Literal["dimensions_orientation_only"] = "dimensions_orientation_only"
