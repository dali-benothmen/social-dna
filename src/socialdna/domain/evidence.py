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


class StatisticalLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["statistical_result"] = "statistical_result"
    subject: EntityRef
    analysis_id: str
    result_id: str | None = None
    term: str | None = None
    diagnostic: Literal["regression", "validation", "creator_baselines", "comparison"] | None = None

    @model_validator(mode="after")
    def exact_target(self) -> "StatisticalLocator":
        if (self.result_id is None) == (self.diagnostic is None):
            raise ValueError(
                "A statistical locator needs exactly one result or declared diagnostic"
            )
        if (self.result_id is None) != (self.term is None):
            raise ValueError("A statistical term needs its exact result identity")
        return self


class PostTextLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["post_text"] = "post_text"
    subject: EntityRef
    field: Literal["caption", "hashtag"]
    tag_index: int | None = Field(default=None, strict=True, ge=0)
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)
    quote: str
    normalization: Literal["none", "hashtag_casefold_strip"] = "none"
    index_convention: Literal["unicode_code_points_captured_text"] = (
        "unicode_code_points_captured_text"
    )

    @model_validator(mode="after")
    def valid_span(self) -> "PostTextLocator":
        if self.end_char <= self.start_char or len(self.quote) != self.end_char - self.start_char:
            raise ValueError("Post quote must match its nonempty character span")
        if (self.field == "hashtag") != (self.tag_index is not None) or (
            (self.field == "hashtag") != (self.normalization == "hashtag_casefold_strip")
        ):
            raise ValueError("Hashtag evidence must identify its normalized captured tag")
        return self


class CreativeEventLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["creative_event", "creative_coverage"] = "creative_event"
    subject: EntityRef
    media: EntityRef


EvidenceLocator = Annotated[
    MediaLocator
    | CommentLocator
    | MetricLocator
    | StatisticalLocator
    | PostTextLocator
    | CreativeEventLocator,
    Field(discriminator="kind"),
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
