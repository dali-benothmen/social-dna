from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from socialdna.domain.evidence import EntityRef
from socialdna.ingestion.tabular import timestamp


class AudienceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CollectionMember(AudienceModel):
    comment: EntityRef
    eligible: bool = True
    exclusion_reason: str | None = Field(default=None, min_length=1, max_length=500)
    language: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    creator_authored: bool | None = None

    @model_validator(mode="after")
    def valid_member(self) -> "CollectionMember":
        if self.comment.kind != "comment":
            raise ValueError("Collection membership requires exact comment revisions")
        if not self.eligible and not self.exclusion_reason:
            raise ValueError("Excluded members require a reason")
        return self


class CollectionSpec(AudienceModel):
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    permission_basis: str = Field(min_length=1, max_length=2000)
    source_uri: str = Field(min_length=1, max_length=2000)
    posts: tuple[EntityRef, ...] = Field(min_length=1, max_length=100)
    members: tuple[CollectionMember, ...] = Field(default=(), max_length=2000)
    requested_start: str | None = None
    requested_end: str | None = None
    collected_at: str
    ordering: Literal["chronological", "reverse_chronological", "ranked", "unknown"]
    filters: dict[str, str] = Field(default_factory=dict, max_length=20)
    sampling_method: Literal["census", "random", "ranked", "convenience", "unknown"]
    completeness: Literal["complete_for_declared_frame", "partial", "unknown"]
    declared_frame: str = Field(min_length=1, max_length=2000)
    pagination_complete: bool | None = None
    limit: int | None = Field(default=None, strict=True, ge=1)
    truncated: bool | None = None
    supplied_count: int = Field(strict=True, ge=0)
    known_total: int | None = Field(default=None, strict=True, ge=0)
    unavailable_count: int | None = Field(default=None, strict=True, ge=0)
    deleted_moderated_coverage: str = Field(min_length=1, max_length=2000)
    source_lag_seconds: int | None = Field(default=None, strict=True, ge=0)
    duplicate_policy: Literal["collapse_exact_text", "distinct_comment_ids"] = "collapse_exact_text"
    creator_policy: Literal["exclude_known", "include"] = "exclude_known"
    retention: Literal["authorized_retention", "explicit_erasure_required"] = "authorized_retention"
    expires_at: str | None = None
    limitations: tuple[str, ...] = Field(default=(), max_length=30)

    @field_validator("requested_start", "requested_end", "collected_at", "expires_at")
    @classmethod
    def normalized_time(cls, value: str | None) -> str | None:
        return timestamp(value) if value is not None else None

    @model_validator(mode="after")
    def coherent(self) -> "CollectionSpec":
        if any(p.kind != "post" for p in self.posts) or len({p.id for p in self.posts}) != len(
            self.posts
        ):
            raise ValueError("Declare unique exact post revisions")
        if len({m.comment.id for m in self.members}) != len(self.members):
            raise ValueError("A comment identity can appear only once, even across corrections")
        if self.supplied_count < len(self.members):
            raise ValueError("Supplied rows cannot be fewer than declared unique members")
        if (
            self.requested_start
            and self.requested_end
            and self.requested_start >= self.requested_end
        ):
            raise ValueError("Requested collection period must be nonempty")
        if self.requested_end and self.requested_end > self.collected_at:
            raise ValueError("Requested period cannot end after collection")
        if self.expires_at and self.expires_at <= self.collected_at:
            raise ValueError("Retention expiry must be after collection")
        if self.completeness == "complete_for_declared_frame" and (
            self.sampling_method != "census"
            or self.ordering in ("ranked", "unknown")
            or self.pagination_complete is not True
            or self.truncated is not False
            or (self.known_total is not None and self.known_total != len(self.members))
        ):
            raise ValueError(
                "Complete coverage needs an untruncated declared census with complete pagination"
            )
        if not self.permission_basis.strip():
            raise ValueError("Permission basis cannot be blank")
        return self
