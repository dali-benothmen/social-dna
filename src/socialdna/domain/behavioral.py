"""Source-defined aggregate behavior; no viewer records or causal promotion."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from socialdna.domain.evidence import EntityRef
from socialdna.ingestion.tabular import timestamp

Availability = Literal[
    "available",
    "not_supplied",
    "not_permitted",
    "not_applicable",
    "failed",
    "unavailable",
    "source_suppressed",
]
Key = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")]


def actual_number(value: object) -> object:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or abs(value) > 2**53
        or not math.isfinite(value)
    ):
        raise ValueError("Use a finite actual number within the lossless storage range")
    return value


Number = Annotated[float, BeforeValidator(actual_number), Field(strict=True, ge=-(2**53), le=2**53)]


class BehavioralModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BehavioralMetricDefinition(BehavioralModel):
    record_type: Literal["behavioral_definition"] = "behavioral_definition"
    key: Key
    platform: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    subject_type: Literal["post", "account"]
    meaning: Literal[
        "retention", "completion", "watch_time", "followers", "net_growth", "conversion", "other"
    ]
    semantics: Literal["count", "duration", "probability", "ratio", "index", "net_change", "value"]
    unit: str = Field(min_length=1, max_length=100)
    domain: Literal["nonnegative", "bounded_probability", "signed"]
    measurement: Literal["cumulative", "period", "series"]
    numerator_definition: str = Field(min_length=1, max_length=2000)
    denominator_definition: str | None = Field(default=None, min_length=1, max_length=2000)
    population_basis: Literal[
        "unique_viewers", "plays", "starts", "sessions", "accounts", "unknown"
    ]
    replay_policy: Literal["includes_replays", "excludes_replays", "not_applicable", "unknown"]
    aggregation: Literal["none", "sum_disjoint", "weighted_by_denominator"] = "none"
    completion_threshold: float | None = Field(default=None, ge=0, le=1)
    source_definition_uri: str = Field(min_length=1, max_length=2000)
    description: str = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def coherent(self) -> "BehavioralMetricDefinition":
        if not self.key.startswith(self.platform + ".") or len(self.key.split(".")) < 3:
            raise ValueError("Definitions need a platform-namespaced versioned key")
        if (self.semantics == "probability") != (self.domain == "bounded_probability"):
            raise ValueError("Only probability definitions use the bounded-probability domain")
        if self.domain == "signed" and self.semantics not in ("net_change", "index", "value"):
            raise ValueError("Counts, ratios, durations and probabilities cannot be signed")
        if self.semantics in ("ratio", "probability") and not self.denominator_definition:
            raise ValueError("Rates need an explicit denominator definition")
        if self.meaning == "completion" and (
            self.completion_threshold is None
            or self.semantics != "probability"
            or self.population_basis not in ("starts", "plays", "unique_viewers")
        ):
            raise ValueError(
                "Completion needs a probability, threshold and eligible-start/play basis"
            )
        if self.meaning == "net_growth" and (
            self.subject_type != "account"
            or self.semantics != "net_change"
            or self.domain != "signed"
            or self.measurement != "period"
        ):
            raise ValueError("Net growth is a signed, account-scoped period measurement")
        if self.meaning == "followers" and (
            self.subject_type != "account"
            or self.semantics != "count"
            or self.measurement != "cumulative"
        ):
            raise ValueError("Follower history requires account count snapshots")
        return self


class AudienceCohort(BehavioralModel):
    record_type: Literal["audience_cohort"] = "audience_cohort"
    key: Key
    account: EntityRef
    known: bool
    eligibility: str = Field(min_length=1, max_length=2000)
    dimensions: dict[str, str] = Field(default_factory=dict, max_length=10)
    aggregation_limitations: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def aggregate_only(self) -> "AudienceCohort":
        if self.account.kind != "account":
            raise ValueError("Cohorts need an exact account revision")
        if set(self.dimensions) - {
            "geography",
            "device",
            "traffic",
            "subscription",
            "content_type",
        }:
            raise ValueError("Only minimized aggregate cohort dimensions are supported")
        return self


class ObservationClock(BehavioralModel):
    window_start: str
    window_end: str
    data_cutoff: str | None = None
    collected_at: str
    source_generated_at: str | None = None
    source_lag_seconds: float | None = Field(default=None, ge=0)

    _times = field_validator(
        "window_start", "window_end", "data_cutoff", "collected_at", "source_generated_at"
    )(lambda v: timestamp(v) if v is not None else None)

    @model_validator(mode="after")
    def ordered(self) -> "ObservationClock":
        if not self.window_start <= self.window_end <= self.collected_at:
            raise ValueError("Require window_start <= window_end <= collected_at")
        if self.data_cutoff and not self.window_start <= self.data_cutoff <= self.window_end:
            raise ValueError("Effective data cutoff must lie in the declared reporting window")
        if (
            self.source_generated_at
            and not self.window_end <= self.source_generated_at <= self.collected_at
        ):
            raise ValueError("Source generation must be after its window and before collection")
        return self


class PopulationCount(BehavioralModel):
    value: Number | None = None
    availability: Availability = "available"
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    definition: str = Field(min_length=1, max_length=2000)
    population_basis: Literal[
        "unique_viewers", "plays", "starts", "sessions", "accounts", "unknown"
    ]
    cohort: EntityRef
    window_start: str
    window_end: str

    _times = field_validator("window_start", "window_end")(timestamp)

    @model_validator(mode="after")
    def valid_count(self) -> "PopulationCount":
        if (self.availability == "available") != (self.value is not None):
            raise ValueError("Only available components carry a value")
        if self.availability != "available" and not self.reason:
            raise ValueError("Unavailable components require their reason")
        if self.value is not None and (self.value < 0 or not self.value.is_integer()):
            raise ValueError("Population components are nonnegative integer counts")
        if self.cohort.kind != "audience_cohort" or self.window_start > self.window_end:
            raise ValueError("Components need a cohort and valid window")
        return self


class MetricValue(BehavioralModel):
    value: Number | None = None
    availability: Availability = "available"
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    origin: Literal["source_reported", "ratio_components"] = "source_reported"
    numerator: PopulationCount | None = None
    denominator: PopulationCount | None = None

    @model_validator(mode="after")
    def valid_value(self) -> "MetricValue":
        if self.origin == "ratio_components":
            if self.value is not None or self.numerator is None or self.denominator is None:
                raise ValueError("Derived rates require actual components, not an asserted value")
        elif (self.availability == "available") != (self.value is not None):
            raise ValueError("Only available measurements carry a value")
        if self.availability != "available" and not self.reason:
            raise ValueError("Unavailable measurements require their source reason")
        return self


class MetricMeasurement(BehavioralModel):
    record_type: Literal["metric_measurement"] = "metric_measurement"
    key: Key
    subject: EntityRef
    definition: EntityRef
    cohort: EntityRef
    clock: ObservationClock
    measurement: MetricValue

    @model_validator(mode="after")
    def references(self) -> "MetricMeasurement":
        if (
            self.subject.kind not in ("post", "account")
            or self.definition.kind != "behavioral_metric_definition"
            or self.cohort.kind != "audience_cohort"
        ):
            raise ValueError(
                "Measurements require exact subject, behavioral definition and cohort references"
            )
        return self


class MetricBin(BehavioralModel):
    ordinal: int = Field(strict=True, ge=0)
    start: Number | None = None
    end: Number | None = None
    point: Number | None = None
    measurement: MetricValue

    @model_validator(mode="after")
    def coordinates(self) -> "MetricBin":
        interval = self.start is not None and self.end is not None and self.start < self.end
        if not (
            (self.point is not None and self.start is None and self.end is None)
            or (self.point is None and interval)
        ):
            raise ValueError("A bin needs exactly one source point or nonempty interval")
        return self


class MetricSeries(BehavioralModel):
    record_type: Literal["metric_series"] = "metric_series"
    key: Key
    subject: EntityRef
    definition: EntityRef
    cohort: EntityRef
    clock: ObservationClock
    media: EntityRef | None = None
    coordinate_kind: Literal["media_ms", "normalized_progress", "provider_index"]
    resolution: str = Field(min_length=1, max_length=1000)
    convention: Literal["points", "half_open_intervals"]
    completeness: Literal["complete_for_declared_grid", "partial", "unknown"]
    expected_bins: int | None = Field(default=None, strict=True, ge=1, le=2000)
    overlapping_bins: bool = False
    overlap_reason: str | None = Field(default=None, min_length=1, max_length=1000)
    bins: tuple[MetricBin, ...] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def ordered(self) -> "MetricSeries":
        if self.subject.kind != "post" or (self.media and self.media.kind != "media"):
            raise ValueError("Series require a post and optional exact media revision")
        if self.coordinate_kind == "media_ms" and self.media is None:
            raise ValueError("Media-ms bins require actual matching media")
        if self.overlapping_bins and not self.overlap_reason:
            raise ValueError("Source-overlapping bins need a declared reason")
        if self.expected_bins is not None and len(self.bins) > self.expected_bins:
            raise ValueError("Supplied bins exceed the declared source grid")
        if self.completeness == "complete_for_declared_grid" and self.expected_bins != len(
            self.bins
        ):
            raise ValueError("Complete grids need an explicit matching bin count")
        previous, previous_end, seen = -1, float("-inf"), set()
        for item in self.bins:
            point = item.point is not None
            start = item.point if point else item.start
            end = item.point if point else item.end
            assert start is not None and end is not None
            if point != (self.convention == "points") or start < 0:
                raise ValueError("Bin coordinates must match the source convention")
            if self.coordinate_kind == "normalized_progress" and end > 1:
                raise ValueError("Normalized coordinates must stay within [0,1]")
            if self.coordinate_kind == "media_ms" and (
                not start.is_integer() or not end.is_integer()
            ):
                raise ValueError("Media-ms source coordinates must be integer milliseconds")
            if item.ordinal <= previous or start in seen:
                raise ValueError("Bin ordinals/coordinates must be unique and ordered")
            if start < previous_end and not self.overlapping_bins:
                raise ValueError("Unmarked overlapping or out-of-order bins")
            previous, previous_end = item.ordinal, end
            seen.add(start)
        if self.completeness == "complete_for_declared_grid" and [
            b.ordinal for b in self.bins
        ] != list(range(len(self.bins))):
            raise ValueError("Complete source grids cannot omit ordinals")
        return self


class AttributionCredit(BehavioralModel):
    post: EntityRef
    weight: float = Field(ge=0, le=1)
    campaign: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def post_target(self) -> "AttributionCredit":
        if self.post.kind != "post":
            raise ValueError("Attribution credits need exact supplied post revisions")
        return self


class AttributionObservation(MetricMeasurement):
    record_type: Literal["attribution_observation"] = "attribution_observation"  # type: ignore[assignment]
    attribution_type: Literal["platform_reported", "observational_association", "unknown"]
    model: str | None = Field(default=None, min_length=1, max_length=2000)
    lookback_start: str | None = None
    lookback_end: str | None = None
    allocation_policy: Literal["fractional", "full_credit_each", "unallocated"] = "unallocated"
    deduplication_key: str = Field(min_length=1, max_length=256)
    credits: tuple[AttributionCredit, ...] = Field(default=(), max_length=100)

    _times = field_validator("lookback_start", "lookback_end")(
        lambda v: timestamp(v) if v is not None else None
    )

    @model_validator(mode="after")
    def attribution(self) -> "AttributionObservation":
        if bool(self.lookback_start) != bool(self.lookback_end):
            raise ValueError("Supply both attribution window bounds")
        if (
            self.lookback_start
            and self.lookback_end
            and not self.lookback_start < self.lookback_end <= self.clock.window_end
        ):
            raise ValueError(
                "Attribution lookback must be nonempty and end by the reporting cutoff"
            )
        if self.attribution_type != "unknown" and (not self.model or not self.lookback_start):
            raise ValueError("Known attribution needs its actual source model and window")
        if len({c.post.id for c in self.credits}) != len(self.credits):
            raise ValueError("A post may receive only one credit in an observation")
        if self.allocation_policy == "unallocated" and self.credits:
            raise ValueError("Unallocated observations do not invent post credits")
        if (
            self.allocation_policy == "fractional"
            and sum(c.weight for c in self.credits) > 1 + 1e-12
        ):
            raise ValueError("Fractional attribution cannot allocate more than the supplied total")
        return self


BehavioralRecord = Annotated[
    BehavioralMetricDefinition
    | AudienceCohort
    | MetricMeasurement
    | MetricSeries
    | AttributionObservation,
    Field(discriminator="record_type"),
]


class BehavioralSource(BehavioralModel):
    dataset_id: Key
    source_uri: str = Field(min_length=1, max_length=2000)
    permission_basis: Literal["creator_owned_export", "authorized_export", "public_permitted"]
    analytics_permitted: Literal[True]
    limitations: tuple[str, ...] = Field(default=(), max_length=30)


class BehavioralExport(BehavioralModel):
    schema_version: Literal["2.0"]
    source: BehavioralSource
    records: tuple[BehavioralRecord, ...] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def unique_records(self) -> "BehavioralExport":
        keys = [(r.record_type, r.key) for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("An import must not repeat a behavioral record identity")
        if sum(len(r.bins) for r in self.records if isinstance(r, MetricSeries)) > 5000:
            raise ValueError("At most 5000 bins are permitted per behavioral export")
        return self


class AccountOutcomeSpec(BehavioralModel):
    schema_version: Literal["1.0"] = "1.0"
    definition: EntityRef
    cohort: EntityRef
    start: str
    end: str
    knowledge_cutoff: str | None = None
    mode: Literal["endpoint_difference", "supplied_change"] = "endpoint_difference"
    attribution_definition: EntityRef | None = None

    _times = field_validator("start", "end", "knowledge_cutoff")(
        lambda v: timestamp(v) if v is not None else None
    )

    @model_validator(mode="after")
    def period(self) -> "AccountOutcomeSpec":
        if (
            self.definition.kind != "behavioral_metric_definition"
            or self.cohort.kind != "audience_cohort"
            or (
                self.attribution_definition
                and self.attribution_definition.kind != "behavioral_metric_definition"
            )
        ):
            raise ValueError(
                "Outcome specifications require exact behavioral definition and cohort references"
            )
        if self.start >= self.end:
            raise ValueError("Account outcomes require a nonempty exact period")
        return self
