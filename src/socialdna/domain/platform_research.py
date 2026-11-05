"""Reviewed official guidance and observable distribution are distinct evidence lanes."""

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from socialdna.domain.context import ContextClock, ContextModel, Key
from socialdna.domain.evidence import EntityRef
from socialdna.ingestion.tabular import timestamp

Platform = Literal["instagram", "tiktok", "youtube"]
SURFACES = {
    "instagram": ("feed", "explore", "reels", "search"),
    "tiktok": ("for_you", "search"),
    "youtube": ("home", "suggested", "search", "shorts"),
}
OFFICIAL_HOSTS = {
    "instagram": {
        "about.fb.com",
        "transparency.meta.com",
        "help.instagram.com",
        "developers.facebook.com",
    },
    "tiktok": {"support.tiktok.com", "newsroom.tiktok.com", "developers.tiktok.com"},
    "youtube": {"support.google.com", "blog.youtube", "developers.google.com"},
}


class PlatformDocument(ContextModel):
    record_type: Literal["platform_document"] = "platform_document"
    key: Key
    account: EntityRef
    platform: Platform
    surfaces: tuple[str, ...] = Field(min_length=1, max_length=10)
    publisher: Literal["Meta", "TikTok", "YouTube"]
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=1000)
    source_text: str = Field(min_length=1, max_length=32000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capture_scope: Literal["permitted_excerpt", "permitted_document"]
    clock: ContextClock
    published_at: str | None = None
    review_status: Literal["reviewed", "unreviewed", "withdrawn"]
    reviewer: str = Field(min_length=1, max_length=200)
    review_basis: str = Field(min_length=1, max_length=3000)
    revision_reason: Literal["new_version", "correction", "withdrawal"] = "new_version"

    _times = field_validator("published_at")(lambda v: timestamp(v) if v else None)

    @model_validator(mode="after")
    def official_scope(self) -> "PlatformDocument":
        parsed = urlparse(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in OFFICIAL_HOSTS[self.platform]
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Official guidance requires a supported HTTPS publisher origin")
        if (
            self.publisher
            != {"instagram": "Meta", "tiktok": "TikTok", "youtube": "YouTube"}[self.platform]
        ):
            raise ValueError("Publisher and platform disagree")
        if set(self.surfaces) - set(SURFACES[self.platform]):
            raise ValueError("Surface does not belong to this platform")
        if self.published_at and self.published_at > self.clock.captured_at:
            raise ValueError("Document publication cannot follow capture")
        return self


class PlatformStatement(ContextModel):
    record_type: Literal["platform_statement"] = "platform_statement"
    key: Key
    account: EntityRef
    document: EntityRef
    surface: str = Field(min_length=1, max_length=100)
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, gt=0)
    quote: str = Field(min_length=1, max_length=2000)
    interpretation: str = Field(min_length=1, max_length=3000)
    limitation: str = Field(min_length=1, max_length=3000)
    claim_level: Literal["official_guidance"] = "official_guidance"


class PlatformScope(ContextModel):
    platform: Platform
    surface: str = Field(min_length=1, max_length=100)
    native_format: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=40)
    market: str = Field(min_length=2, max_length=100)
    niche: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def surface_scope(self) -> "PlatformScope":
        if self.surface not in SURFACES[self.platform]:
            raise ValueError("Surface does not belong to this platform")
        return self


class MetricCapability(ContextModel):
    definition: EntityRef
    role: Literal[
        "retention", "completion", "shares", "saves", "watch_time", "impressions", "reach", "views"
    ]
    availability: Literal["available", "unavailable", "source_suppressed", "not_permitted"]
    reason: str = Field(min_length=1, max_length=2000)


class SurfaceMapping(ContextModel):
    raw_code: str = Field(min_length=1, max_length=100)
    surface: str | None = Field(default=None, max_length=100)
    traffic: Literal["organic", "paid", "collaboration", "unknown"]


class PlatformCapabilities(ContextModel):
    record_type: Literal["platform_capabilities"] = "platform_capabilities"
    key: Key
    account: EntityRef
    scope: PlatformScope
    clock: ContextClock
    analytics_permitted: bool = Field(strict=True)
    access_scope: str = Field(min_length=1, max_length=2000)
    collection_method: Literal["authorized_export", "authorized_api", "creator_experiment_export"]
    source_report: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=200)
    mapping_basis: str = Field(min_length=1, max_length=3000)
    source_lag_seconds: float = Field(strict=True, ge=0)
    metrics: tuple[MetricCapability, ...] = Field(min_length=1, max_length=50)
    mappings: tuple[SurfaceMapping, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique(self) -> "PlatformCapabilities":
        if len({m.raw_code for m in self.mappings}) != len(self.mappings):
            raise ValueError("Source mappings must be unambiguous")
        if len({m.definition.revision_id for m in self.metrics}) != len(self.metrics):
            raise ValueError("Each exact source definition has one reviewed role")
        if any(m.surface and m.surface not in SURFACES[self.scope.platform] for m in self.mappings):
            raise ValueError("Mapped surface belongs to a different platform")
        return self


class DistributionObservation(ContextModel):
    record_type: Literal["distribution_observation"] = "distribution_observation"
    key: Key
    account: EntityRef
    post: EntityRef
    capabilities: EntityRef
    early: EntityRef
    later: EntityRef
    raw_surface_code: str = Field(min_length=1, max_length=100)
    clock: ContextClock


PlatformRecord = Annotated[
    PlatformDocument | PlatformStatement | PlatformCapabilities | DistributionObservation,
    Field(discriminator="record_type"),
]


class PlatformExport(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Key
    source_uri: str = Field(min_length=1, max_length=2000)
    permission_basis: str = Field(min_length=1, max_length=2000)
    records: tuple[PlatformRecord, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self) -> "PlatformExport":
        keys = [(r.record_type, r.account.id, r.key) for r in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("Platform record keys must be unique in an export")
        return self


class PlatformReportSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    account: EntityRef
    scope: PlatformScope
    statements: tuple[EntityRef, ...] = Field(default=(), max_length=50)
    observations: tuple[EntityRef, ...] = Field(default=(), max_length=500)
    traffic: Literal["organic", "paid", "collaboration"]
    minimum_lag_seconds: float = Field(default=0, strict=True, ge=0)
    as_of: str
    claim_level: Literal["descriptive_observational"] = "descriptive_observational"

    _times = field_validator("as_of")(timestamp)

    @model_validator(mode="after")
    def unique_statements(self) -> "PlatformReportSpec":
        if len({r.revision_id for r in self.statements}) != len(self.statements):
            raise ValueError("Official statements must not be duplicated")
        return self
