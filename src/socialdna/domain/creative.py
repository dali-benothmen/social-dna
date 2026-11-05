"""Observable creative annotations, not psychological or performance findings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.core.time import MediaInterval
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.providers import ProviderIdentity

Modality = Literal[
    "visual", "audio", "speech", "subtitle", "overlay", "caption", "hashtag", "motion", "color"
]
Technique = Literal[
    "finished_dish",
    "ingredient_display",
    "preparation_instruction",
    "utility_promise",
    "text_overlay",
    "sound_effect",
    "cut",
    "warm_color",
    "hashtag",
    "unclassified",
]
TECHNIQUE_MODALITIES: dict[str, set[str]] = {
    "finished_dish": {"visual"},
    "ingredient_display": {"visual"},
    "preparation_instruction": {"visual", "speech", "subtitle", "overlay", "caption"},
    "utility_promise": {"speech", "subtitle", "overlay", "caption"},
    "text_overlay": {"visual", "overlay"},
    "sound_effect": {"audio"},
    "cut": {"visual", "motion"},
    "warm_color": {"visual", "color"},
    "hashtag": {"hashtag"},
    "unclassified": {
        "visual",
        "audio",
        "speech",
        "subtitle",
        "overlay",
        "caption",
        "hashtag",
        "motion",
        "color",
    },
}


class CreativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MediaAnchor(CreativeModel):
    """Original-presentation milliseconds. Points never masquerade as intervals."""

    kind: Literal["interval", "point", "spatial", "untimed"] = "interval"
    start_min_ms: int | None = Field(default=None, strict=True, ge=0)
    start_max_ms: int | None = Field(default=None, strict=True, ge=0)
    end_min_ms: int | None = Field(default=None, strict=True, ge=0)
    end_max_ms: int | None = Field(default=None, strict=True, ge=0)
    nominal_start_ms: int | None = Field(default=None, strict=True, ge=0)
    nominal_end_ms: int | None = Field(default=None, strict=True, ge=0)
    unknown_reason: str | None = Field(default=None, min_length=1, max_length=1000)
    box: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def coherent(self) -> "MediaAnchor":
        start = (self.start_min_ms, self.start_max_ms)
        end = (self.end_min_ms, self.end_max_ms)
        if self.kind == "untimed":
            if (
                any(
                    value is not None
                    for value in (*start, *end, self.nominal_start_ms, self.nominal_end_ms)
                )
                or not self.unknown_reason
            ):
                raise ValueError(
                    "Untimed post text has no invented playback offsets and needs a reason"
                )
        elif all(value is None for value in (*start, *end)):
            if (
                not self.unknown_reason
                or self.nominal_start_ms is not None
                or self.nominal_end_ms is not None
            ):
                raise ValueError(
                    "Unknown boundaries need a reason, not nominal invented timestamps"
                )
        else:
            if start[0] is None or start[1] is None or start[0] > start[1]:
                raise ValueError("Supply ordered start uncertainty bounds")
            if (
                self.nominal_start_ms is not None
                and not start[0] <= self.nominal_start_ms <= start[1]
            ):
                raise ValueError("Nominal start is outside its uncertainty range")
            if self.kind in ("point", "spatial"):
                if any(value is not None for value in (*end, self.nominal_end_ms)):
                    raise ValueError("A point has no duration/end bounds")
            else:
                if end[0] is None or end[1] is None or end[0] > end[1] or start[0] >= end[1]:
                    raise ValueError("No feasible nonempty interval within the supplied bounds")
                if (self.nominal_start_ms is None) != (self.nominal_end_ms is None):
                    raise ValueError("Nominal interval bounds must both be supplied or omitted")
                if self.nominal_end_ms is not None and (
                    not end[0] <= self.nominal_end_ms <= end[1]
                    or self.nominal_start_ms is None
                    or self.nominal_end_ms <= self.nominal_start_ms
                ):
                    raise ValueError("Invalid nominal end")
        if self.kind == "spatial":
            if self.box is None or not (
                0 <= self.box[0] < self.box[2] <= 1 and 0 <= self.box[1] < self.box[3] <= 1
            ):
                raise ValueError("A spatial video-frame anchor needs a normalized nonempty box")
        elif self.box is not None:
            raise ValueError("Only spatial anchors have boxes")
        return self

    def bounds(self) -> tuple[int, int, int, int] | None:
        if self.start_min_ms is None or self.start_max_ms is None:
            return None
        if self.kind in ("point", "spatial"):
            return (self.start_min_ms, self.start_max_ms, self.start_min_ms, self.start_max_ms)
        assert self.end_min_ms is not None and self.end_max_ms is not None
        # Tighten extrema to feasible intervals (s < e), not infeasible corners.
        return (
            self.start_min_ms,
            min(self.start_max_ms, self.end_max_ms - 1),
            max(self.end_min_ms, self.start_min_ms + 1),
            self.end_max_ms,
        )

    def check_duration(self, duration_ms: int) -> None:
        bounds = self.bounds()
        if bounds and (bounds[3] > duration_ms or bounds[1] >= duration_ms):
            raise ValueError("Creative anchor is outside the original media duration")


class AnnotationProtocol(CreativeModel):
    origin: Literal["human", "model", "deterministic"]
    author: str = Field(min_length=1, max_length=200)
    procedure: str = Field(min_length=1, max_length=2000)
    outcome_access: Literal["blinded", "outcome_aware", "unknown"]
    label_frozen_before_outcomes: bool = False
    provider: ProviderIdentity | None = None

    @model_validator(mode="after")
    def provenance(self) -> "AnnotationProtocol":
        if self.label_frozen_before_outcomes and self.outcome_access != "blinded":
            raise ValueError(
                "Outcome-aware/unknown annotations cannot claim outcome-blind freezing"
            )
        if (self.origin == "model") != (self.provider is not None):
            raise ValueError(
                "Model annotations require an exact provider/model revision; other origins do not"
            )
        return self


class SamplingCoverage(CreativeModel):
    modality: Modality
    techniques: tuple[Technique, ...] = Field(min_length=1)
    mode: Literal["exhaustive_review", "sampled", "unknown"]
    intervals: tuple[MediaInterval, ...] = Field(default=(), max_length=100)
    sample_times_ms: tuple[int, ...] = Field(default=(), max_length=1000)
    limitation: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def valid_sampling(self) -> "SamplingCoverage":
        if len(set(self.techniques)) != len(self.techniques) or any(
            t < 0 for t in self.sample_times_ms
        ):
            raise ValueError("Invalid coverage techniques/sample times")
        if self.mode == "exhaustive_review" and not self.intervals:
            raise ValueError("Exhaustive review requires declared intervals")
        if self.modality in ("caption", "hashtag") and self.mode == "exhaustive_review":
            raise ValueError("Untimed post text cannot use media-clock absence coverage")
        return self


class CreativeInput(CreativeModel):
    ref: EvidenceRef
    modality: Modality
    role: Literal["observed", "context"] = "observed"


class CreativeAnnotation(CreativeModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    technique: Technique
    description: str = Field(min_length=1, max_length=3000)
    modalities: tuple[Modality, ...] = Field(min_length=1, max_length=9)
    anchors: tuple[MediaAnchor, ...] = Field(min_length=1, max_length=20)
    inputs: tuple[CreativeInput, ...] = Field(default=(), max_length=40)
    state: Literal["proposed", "reviewed", "disputed"] = "proposed"
    verdict: Literal["present", "ambiguous"] = "present"
    reliability: Literal["low", "medium", "high"] = "low"
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)
    post: EntityRef | None = None

    @model_validator(mode="after")
    def reviewed(self) -> "CreativeAnnotation":
        if self.state == "reviewed" and not self.reviewer:
            raise ValueError("A reviewed annotation requires its reviewer")
        if len(set(self.modalities)) != len(self.modalities):
            raise ValueError("Modalities must be unique")
        if set(self.modalities) - TECHNIQUE_MODALITIES[self.technique]:
            raise ValueError("Technique does not support the asserted modality")
        if any(anchor.kind == "untimed" for anchor in self.anchors) and (
            not self.post or set(self.modalities) - {"caption", "hashtag"}
        ):
            raise ValueError("Untimed anchors are reserved for exact post text evidence")
        if self.post and self.post.kind != "post":
            raise ValueError("Post context must refer to a post revision")
        return self


class CreativeAnnotationSet(CreativeModel):
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    permission_basis: str = Field(min_length=1, max_length=2000)
    protocol: AnnotationProtocol
    coverage: tuple[SamplingCoverage, ...] = Field(default=(), max_length=40)
    events: tuple[CreativeAnnotation, ...] = Field(default=(), max_length=64)
    tolerance_ms: int = Field(default=100, strict=True, ge=0, le=1000)

    @model_validator(mode="after")
    def coherent(self) -> "CreativeAnnotationSet":
        if len({item.key for item in self.events}) != len(self.events):
            raise ValueError("Event keys must be unique within an annotation set")
        identities = [(item.modality, tuple(sorted(item.techniques))) for item in self.coverage]
        if len(set(identities)) != len(identities):
            raise ValueError("Coverage entries must have unique modality/technique scopes")
        if self.protocol.origin != "human" and (
            any(c.mode == "exhaustive_review" for c in self.coverage)
            or any(e.state == "reviewed" for e in self.events)
        ):
            raise ValueError(
                "Model/rule proposals cannot self-adjudicate or certify exhaustive review"
            )
        if not self.permission_basis.strip():
            raise ValueError("Permission basis cannot be blank")
        return self


class CreativeTechnique(CreativeModel):
    key: Technique
    version: Literal["1.0"] = "1.0"
    modalities: tuple[Modality, ...]
    definition: str
    inclusion: str
    exclusion: str
    required_coverage: str
    procedure: str
    examples: tuple[str, ...]
    counterexamples: tuple[str, ...]


class FeatureRecipe(CreativeModel):
    id: str
    version: Literal["1.0"] = "1.0"
    operation: Literal["presence", "first", "conjunction", "synchronized", "hashtag_count"]
    techniques: tuple[Technique, ...]
    modalities: tuple[Modality, ...]
    opening_ms: int = Field(default=3000, strict=True, gt=0)
    tolerance_ms: int = Field(default=100, strict=True, ge=0)
    unit: Literal["binary", "count"] = "binary"
    missingness: Literal["preserve_unknown"] = "preserve_unknown"
    role: Literal["observable_content"] = "observable_content"
    boundary_convention: Literal["half_open_original_ms"] = "half_open_original_ms"
    description: str
