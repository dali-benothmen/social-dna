from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.core.time import MediaInterval


class EvidenceReference(BaseModel):
    """Legacy v1 media citation; its original identity remains supported."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: UUID
    interval: MediaInterval | None = None


class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: str = Field(min_length=1, max_length=64)
    id: str = Field(min_length=1, max_length=500)
    revision_id: str = Field(min_length=1, max_length=36)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=36)
    revision_id: str = Field(min_length=1, max_length=36)


class MediaLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["media_span"] = "media_span"
    subject: EntityRef
    media: EntityRef
    interval: MediaInterval
    artifact_id: str | None = None
    excerpt: str | None = None


class CommentLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["comment_span"] = "comment_span"
    subject: EntityRef
    post: EntityRef
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)
    index_convention: Literal["unicode_code_points_original"] = "unicode_code_points_original"
    quote: str

    @model_validator(mode="after")
    def ordered(self) -> "CommentLocator":
        if self.end_char <= self.start_char or len(self.quote) != self.end_char - self.start_char:
            raise ValueError("Comment quote must exactly match its nonempty character span")
        return self


class MetricLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    kind: Literal["metric_snapshot"] = "metric_snapshot"
    subject: EntityRef
    measured_subject: EntityRef
    definition: EntityRef
    value: float | None
    availability: str
    reason: str | None
    observed_at: str
    window_start: str | None
    window_end: str | None


EvidenceLocator = Annotated[
    MediaLocator | CommentLocator | MetricLocator, Field(discriminator="kind")
]


class ResolvedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ref: EvidenceRef
    locator_kind: str
    subject: EntityRef
    locator: EvidenceLocator | None
    source: dict[str, str | None]
    provenance_id: str
    producer_run_id: str | None
    producer_task_id: str | None
    captured_at: str
    available_at: str | None
    eligible: bool
    limitations: tuple[str, ...] = ()
