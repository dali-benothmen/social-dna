"""Public profile observations and measured aggregate outcomes are separate contracts."""

from typing import Annotated, Any, Literal
from urllib.parse import parse_qs, urlparse

from pydantic import Field, field_validator, model_validator

from socialdna.domain.context import ContextClock, ContextModel, Key, TextField
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.ingestion.tabular import timestamp

CollectionState = Literal["collected", "empty", "not_collected", "unavailable"]
Signal = Literal[
    "attention",
    "profile_visits",
    "follows",
    "link_clicks",
    "app_installs",
    "purchases",
    "returning_followers",
    "churn",
]
CRITERIA = (
    "bio_clarity",
    "cta_clarity",
    "link_consistency",
    "pin_alignment",
    "pillar_consistency",
    "profile_consistency",
)
RUBRIC: dict[str, Any] = {
    "id": "profile.qualitative.v1",
    "version": "1.0",
    "criteria": list(CRITERIA),
    "procedure": "Human review of exact public snapshot and declared post sample; "
    "cite literal evidence and contrary examples.",
    "boundary": "Qualitative source-qualified assessment, not measured conversion, "
    "personality inference or a universal quality score.",
}


class ProfilePhoto(ContextModel):
    path: str = Field(min_length=1, max_length=2000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProfileLink(ContextModel):
    key: Key
    label: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def public_destination(self) -> "ProfileLink":
        url = urlparse(self.destination)
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
            raise ValueError("Use a public HTTP(S) destination without credentials")
        if set(parse_qs(url.query)) & {
            "token",
            "access_token",
            "auth",
            "password",
            "session",
            "key",
        }:
            raise ValueError("Do not import secret-bearing link parameters")
        return self


class ProfileSnapshot(ContextModel):
    record_type: Literal["profile_snapshot"] = "profile_snapshot"
    key: Key
    account: EntityRef
    clock: ContextClock
    username: TextField
    display_name: TextField
    bio: TextField
    category: TextField
    positioning: TextField
    declaration_basis: Literal["owner_declared", "source_record", "unknown"]
    content_pillars: tuple[Annotated[str, Field(min_length=1, max_length=200)], ...] = Field(
        default=(), max_length=20
    )
    photo_state: Literal["present", "absent", "removed", "not_collected", "unavailable"]
    photo: ProfilePhoto | None = None
    links_state: CollectionState
    links: tuple[ProfileLink, ...] = Field(default=(), max_length=20)
    pins_state: CollectionState
    pins: tuple[EntityRef, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def coherent(self) -> "ProfileSnapshot":
        if self.account.kind != "account" or any(p.kind != "post" for p in self.pins):
            raise ValueError("Profiles need real account and pinned-post revisions")
        if (self.photo_state == "present") != (self.photo is not None):
            raise ValueError("Photo presence requires actual supplied bytes")
        if (
            self.links_state != "collected"
            and self.links
            or self.pins_state != "collected"
            and self.pins
        ):
            raise ValueError("Uncollected/empty lists cannot assert collected links or pins")
        if (
            self.links_state == "collected"
            and not self.links
            or self.pins_state == "collected"
            and not self.pins
        ):
            raise ValueError("Use explicit empty state for a collected empty inventory")
        if len({p.id for p in self.pins}) != len(self.pins) or len(
            {p.key for p in self.links}
        ) != len(self.links):
            raise ValueError("Pins and link keys must be unique and retain source order")
        if self.content_pillars and self.declaration_basis == "unknown":
            raise ValueError(
                "Pillars must be attributed declarations, not invented interpretations"
            )
        return self


class ProfileCriterion(ContextModel):
    key: Literal[
        "bio_clarity",
        "cta_clarity",
        "link_consistency",
        "pin_alignment",
        "pillar_consistency",
        "profile_consistency",
    ]
    verdict: Literal["supported", "mixed", "unclear", "unknown"]
    rationale: str = Field(min_length=1, max_length=3000)
    evidence: tuple[EvidenceRef, ...] = Field(default=(), max_length=10)
    counterexamples: tuple[EvidenceRef, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def evidence_required(self) -> "ProfileCriterion":
        if self.verdict != "unknown" and not self.evidence:
            raise ValueError("Profile judgments need actual scoped evidence")
        return self


class ProfileReview(ContextModel):
    record_type: Literal["profile_review"] = "profile_review"
    key: Key
    account: EntityRef
    snapshot: EntityRef
    rubric_id: Literal["profile.qualitative.v1"] = "profile.qualitative.v1"
    reviewer: str = Field(min_length=1, max_length=200)
    procedure: str = Field(min_length=1, max_length=3000)
    reviewed_at: str
    outcome_access: Literal["blinded", "outcome_aware", "unknown"]
    sample_posts: tuple[EntityRef, ...] = Field(default=(), max_length=100)
    sample_window_start: str | None = None
    sample_window_end: str | None = None
    criteria: tuple[ProfileCriterion, ...] = Field(min_length=6, max_length=6)

    _time = field_validator("reviewed_at")(timestamp)
    _sample_times = field_validator("sample_window_start", "sample_window_end")(
        lambda v: timestamp(v) if v else None
    )

    @model_validator(mode="after")
    def complete_rubric(self) -> "ProfileReview":
        if {c.key for c in self.criteria} != set(CRITERIA):
            raise ValueError("Represent every frozen criterion, retaining unknowns")
        if self.sample_posts and (not self.sample_window_start or not self.sample_window_end):
            raise ValueError("A declared post sample needs its actual sampling window")
        if bool(self.sample_window_start) != bool(self.sample_window_end) or (
            self.sample_window_start
            and self.sample_window_end
            and not self.sample_window_start < self.sample_window_end <= self.reviewed_at
        ):
            raise ValueError("Sample windows must be nonempty and end by review")
        return self


class FunnelBinding(ContextModel):
    definition: EntityRef
    signal: Signal
    uniqueness: Literal["unique_accounts", "events", "unknown"]
    source_event_code: Key
    source_definition_excerpt: str = Field(min_length=1, max_length=2000)


class FunnelDefinition(ContextModel):
    record_type: Literal["funnel_definition"] = "funnel_definition"
    key: Key
    account: EntityRef
    clock: ContextClock
    reviewer: str = Field(min_length=1, max_length=200)
    source_report: str = Field(min_length=1, max_length=2000)
    join_basis: Literal["source_reported_nested_counts", "unlinked_aggregates", "unknown"]
    deduplication: Literal["source_unique_per_window", "unknown"]
    linkage_limitations: str = Field(min_length=1, max_length=3000)
    bindings: tuple[FunnelBinding, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique(self) -> "FunnelDefinition":
        if len({b.definition.revision_id for b in self.bindings}) != len(self.bindings):
            raise ValueError("One source counter cannot acquire multiple event meanings")
        return self


class FunnelStage(ContextModel):
    key: Key
    measurement: EntityRef


class FunnelRate(ContextModel):
    numerator: Key
    denominator: Key
    source_reports_subset: bool = Field(strict=True)
    linkage_evidence: tuple[EvidenceRef, ...] = Field(default=(), max_length=10)


class FunnelContext(ContextModel):
    record_type: Literal["funnel_context"] = "funnel_context"
    key: Key
    account: EntityRef
    clock: ContextClock
    definition: EntityRef
    stages: tuple[FunnelStage, ...] = Field(min_length=1, max_length=20)
    rates: tuple[FunnelRate, ...] = Field(default=(), max_length=20)
    profile: EntityRef | None = None
    profile_exposure: Literal["unknown", "source_attested"] = "unknown"
    exposure_evidence: tuple[EvidenceRef, ...] = Field(default=(), max_length=10)
    attributions: tuple[EntityRef, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def branches(self) -> "FunnelContext":
        if len({s.key for s in self.stages}) != len(self.stages) or len(
            {s.measurement.revision_id for s in self.stages}
        ) != len(self.stages):
            raise ValueError("Each stage must have one distinct actual counter")
        names = {s.key for s in self.stages}
        if any(
            r.numerator not in names or r.denominator not in names or r.numerator == r.denominator
            for r in self.rates
        ):
            raise ValueError("Rates must connect two supplied distinct stages")
        if len({r.numerator for r in self.rates}) != len(self.rates):
            raise ValueError("A conversion counter cannot receive repeated branch credit")
        if self.profile_exposure == "source_attested" and (
            not self.profile or not self.exposure_evidence
        ):
            raise ValueError("Known profile exposure needs an actual snapshot and source evidence")
        if self.exposure_evidence and not self.profile:
            raise ValueError("Exposure evidence requires its actual profile context")
        return self


ProfileRecord = Annotated[
    ProfileSnapshot | ProfileReview | FunnelDefinition | FunnelContext,
    Field(discriminator="record_type"),
]


class ProfileExport(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Key
    source_uri: str = Field(min_length=1, max_length=2000)
    permission_basis: str = Field(min_length=1, max_length=2000)
    records: tuple[ProfileRecord, ...] = Field(min_length=1, max_length=100)


class ProfileReportSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    prior: EntityRef
    later: EntityRef
    reviews: tuple[EntityRef, ...] = Field(default=(), max_length=2)
    funnel: EntityRef | None = None
    as_of: str

    _time = field_validator("as_of")(timestamp)
