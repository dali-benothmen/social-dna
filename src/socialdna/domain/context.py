"""Dated publishing context. Capture, validity and import knowledge are not synonyms."""

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from socialdna.domain.evidence import EntityRef
from socialdna.ingestion.tabular import timestamp

Key = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")]
Objective = Literal["search", "recommendation", "conversion"]


class ContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ContextClock(ContextModel):
    captured_at: str
    valid_from: str | None = None
    valid_until: str | None = None
    validity_basis: Literal["unknown", "observed", "source_attested"] = "unknown"

    _times = field_validator("captured_at", "valid_from", "valid_until")(
        lambda value: timestamp(value) if value is not None else None
    )

    @model_validator(mode="after")
    def coherent(self) -> "ContextClock":
        if (self.valid_from is None) != (self.validity_basis == "unknown"):
            raise ValueError("Known validity needs an explicit interval start and basis")
        if self.valid_until and (not self.valid_from or self.valid_until <= self.valid_from):
            raise ValueError("Validity intervals must be nonempty and ordered")
        if self.valid_from and self.valid_from > self.captured_at:
            raise ValueError("Cannot attest future context")
        if self.valid_until and self.valid_until > self.captured_at:
            raise ValueError("Cannot attest a future validity endpoint")
        if self.validity_basis == "observed" and self.valid_from != self.captured_at:
            raise ValueError("A current observation cannot establish earlier validity")
        return self


class TextField(ContextModel):
    state: Literal["present", "empty", "absent", "removed", "not_collected", "unavailable"]
    value: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def coherent(self) -> "TextField":
        if (
            (self.state == "present" and (self.value is None or not self.value.strip()))
            or (self.state == "empty" and self.value != "")
            or (self.state not in ("present", "empty") and self.value is not None)
        ):
            raise ValueError("Field state and actual supplied text disagree")
        return self


class Thumbnail(ContextModel):
    variant: Key
    placement: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1, max_length=2000)


class PublicationContext(ContextModel):
    record_type: Literal["publication_context"] = "publication_context"
    key: Key
    account: EntityRef
    post: EntityRef
    clock: ContextClock
    published_original: str
    timezone: str | None = Field(default=None, max_length=100)
    native_format: str = Field(min_length=1, max_length=100)
    language: str | None = Field(default=None, min_length=2, max_length=40)
    language_basis: Literal["source", "owner_declared", "reviewed", "unknown"] = "unknown"
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    title: TextField
    description: TextField
    caption: TextField
    hashtags: tuple[str, ...] | None = Field(default=None, max_length=100)
    keywords: tuple[str, ...] | None = Field(default=None, max_length=100)
    thumbnails: tuple[Thumbnail, ...] = Field(default=(), max_length=10)
    niche: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def coherent(self) -> "PublicationContext":
        if self.account.kind != "account" or self.post.kind != "post":
            raise ValueError("Publication needs actual account and post revisions")
        published = datetime.fromisoformat(self.published_original.replace("Z", "+00:00"))
        if published.utcoffset() is None:
            raise ValueError("Preserve an explicit original publication offset")
        if timestamp(self.published_original) > self.clock.captured_at:
            raise ValueError("Publication cannot follow capture")
        if self.timezone:
            try:
                local = published.astimezone(ZoneInfo(self.timezone))
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Unknown IANA timezone") from exc
            if local.replace(tzinfo=None) != published.replace(tzinfo=None) or (
                local.utcoffset() != published.utcoffset()
            ):
                raise ValueError("Original local time/offset conflicts with IANA zone or DST")
        if (self.language is None) != (self.language_basis == "unknown"):
            raise ValueError("Language needs an explicit basis; unknown stays unknown")
        if self.language is None and self.language_confidence is not None:
            raise ValueError("Unknown language has no confidence")
        if len({t.variant for t in self.thumbnails}) != len(self.thumbnails):
            raise ValueError("Thumbnail variants must be unique")
        return self


class PublishingWindow(ContextModel):
    record_type: Literal["publishing_window"] = "publishing_window"
    key: Key
    account: EntityRef
    captured_at: str
    window_start: str
    window_end: str
    formats: tuple[str, ...] = Field(min_length=1, max_length=30)
    posts: tuple[EntityRef, ...] = Field(default=(), max_length=5000)
    complete: bool = Field(strict=True)
    includes_deleted_and_omitted: bool = Field(strict=True)
    completeness_basis: str = Field(min_length=1, max_length=3000)

    _times = field_validator("captured_at", "window_start", "window_end")(timestamp)

    @model_validator(mode="after")
    def coherent(self) -> "PublishingWindow":
        if not self.window_start < self.window_end <= self.captured_at:
            raise ValueError("Use an elapsed nonempty publishing observation window")
        if self.account.kind != "account" or any(p.kind != "post" for p in self.posts):
            raise ValueError("Window membership must use actual account/post revisions")
        if len({p.id for p in self.posts}) != len(self.posts):
            raise ValueError("A post can appear only once in an observation window")
        return self


class TrendContext(ContextModel):
    record_type: Literal["trend_context"] = "trend_context"
    key: Key
    account: EntityRef
    clock: ContextClock
    platform: str = Field(min_length=1, max_length=64)
    objective: Objective
    surface: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=40)
    locale: str = Field(min_length=2, max_length=100)
    niche: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=1000)
    query: str = Field(min_length=1, max_length=1000)
    observation_start: str
    observation_end: str
    observation: str = Field(min_length=1, max_length=5000)
    basis: Literal["permitted_export", "reviewed_official_source", "explicit_observation"]

    _times = field_validator("observation_start", "observation_end")(timestamp)

    @model_validator(mode="after")
    def coherent(self) -> "TrendContext":
        if self.account.kind != "account":
            raise ValueError("Trend context needs an actual account scope")
        if not self.observation_start < self.observation_end <= self.clock.captured_at:
            raise ValueError("Trend evidence cannot use a future observation window")
        return self


PublicationRecord = Annotated[
    PublicationContext | PublishingWindow | TrendContext, Field(discriminator="record_type")
]


class ContextExport(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Key
    source_uri: str = Field(min_length=1, max_length=2000)
    permission_basis: str = Field(min_length=1, max_length=2000)
    records: tuple[PublicationRecord, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique(self) -> "ContextExport":
        keys = [
            (r.record_type, r.account.id, getattr(r, "post", None), r.key) for r in self.records
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("Context record keys must be unique within each subject")
        return self


class PublicationReportSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    publications: tuple[EntityRef, ...] = Field(min_length=1, max_length=500)
    window: EntityRef | None = None
    trends: tuple[EntityRef, ...] = Field(default=(), max_length=50)
    objective: Objective
    surface: str = Field(min_length=1, max_length=100)
    outcome_mapping_basis: str = Field(min_length=1, max_length=2000)
    analysis_run_id: str | None = None
    as_of: str
    policy: Literal["retrospective", "historical_prediction"] = "retrospective"

    _times = field_validator("as_of")(timestamp)

    @model_validator(mode="after")
    def unique(self) -> "PublicationReportSpec":
        if len({r.id for r in self.publications}) != len(self.publications):
            raise ValueError("Each publication context can appear only once")
        return self
