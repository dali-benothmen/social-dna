from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from socialdna.core.enums import ClaimLevel
from socialdna.domain.evidence import EvidenceRef, EvidenceReference


class ClaimReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_level: ClaimLevel
    evidence: tuple[EvidenceReference, ...]


class DraftHypothesis(BaseModel):
    """R1 registration is a draft specification, not an evaluated finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    statement: str = Field(min_length=1, max_length=10000)
    population: str = Field(min_length=1, max_length=10000)
    intended_claim_level: Literal["hypothesis", "association"] = "hypothesis"
    data_needs: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()


class ResearchRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    question: str = Field(min_length=1, max_length=10000)
    population: str = Field(min_length=1, max_length=10000)
    data_needs: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    hypotheses: tuple[DraftHypothesis, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def unique_keys(self) -> "ResearchRegistration":
        if len({item.key for item in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("Hypothesis keys must be unique within a registration")
        if not self.question.strip() or not self.population.strip():
            raise ValueError("Question and population cannot be blank")
        if any(
            not item.statement.strip() or not item.population.strip() for item in self.hypotheses
        ):
            raise ValueError("Hypothesis statement and population cannot be blank")
        return self


class Population(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    platforms: tuple[str, ...] = ()
    creator_ids: tuple[str, ...] = ()
    niches: tuple[str, ...] = ()
    content_types: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    min_duration_seconds: float | None = Field(default=None, ge=0)
    max_duration_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "Population":
        if (
            self.min_duration_seconds is not None
            and self.max_duration_seconds is not None
            and self.min_duration_seconds > self.max_duration_seconds
        ):
            raise ValueError("Minimum duration exceeds maximum")
        return self


class PerformanceSpec(BaseModel):
    """Serializable, explicit analysis specification; no free-form model formulas."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    metric_key: str = Field(min_length=1)
    numerator_keys: tuple[str, ...] = ()
    denominator_key: str | None = None
    age_days: float = Field(default=7, ge=0, le=3650)
    age_tolerance_days: float = Field(default=1, ge=0, le=30)
    window_seconds: int | None = Field(default=None, gt=0)
    population: Population = Field(default_factory=Population)
    features: tuple[str, ...] = ("duration_seconds", "caption_length")
    interactions: tuple[tuple[str, str], ...] = ()
    model: Literal["none", "ols", "poisson", "gee", "mixed"] = "none"
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    bootstrap_resamples: int = Field(default=2000, ge=200, le=10000)
    # Matched comparisons never match on an outcome/performance variable.
    matched: bool = True
    duration_caliper_seconds: float = Field(default=10, ge=0)

    def allowed_features(self) -> set[str]:
        return {
            "duration_seconds",
            "caption_length",
            "publishing_hour_utc",
            "visual.motion",
            "visual.appearance",
            "audio.loudness",
        }

    @model_validator(mode="after")
    def valid_features(self) -> "PerformanceSpec":
        allowed = self.allowed_features()
        if len(set(self.features)) != len(self.features) or len(self.features) > 6:
            raise ValueError("Specify at most six unique content features")
        if set(self.features) - allowed:
            raise ValueError(
                "Unknown or target-leaking feature; use the documented content registry"
            )
        if any(
            a not in self.features or b not in self.features or a == b for a, b in self.interactions
        ):
            raise ValueError("Interactions require two different declared features")
        if len({tuple(sorted(pair)) for pair in self.interactions}) != len(self.interactions):
            raise ValueError("Duplicate interactions are not permitted")
        keys = (self.metric_key, *self.numerator_keys)
        if len(set(keys)) != len(keys) or self.denominator_key in keys:
            raise ValueError("Numerator keys must be unique and exclude the denominator")
        if self.numerator_keys and not self.denominator_key:
            raise ValueError("Multiple numerator keys require a denominator")
        if self.model == "poisson" and self.denominator_key:
            raise ValueError("Poisson requires a count outcome, not a derived ratio")
        if self.age_tolerance_days > max(self.age_days, 1):
            raise ValueError("Age tolerance is wider than the declared target age")
        return self


class CorrectedPerformanceSpec(PerformanceSpec):
    """Explicit opt-in contract. Unversioned specifications retain v1 semantics."""

    schema_version: Literal["2.0"] = "2.0"
    estimand: Literal["descriptive", "within_creator_association", "cross_creator_comparison"]
    design: Literal["descriptive", "within_creator", "cross_creator"]
    knowledge_cutoff: str
    publication_cutoff: str
    baseline_policy: Literal["historical_as_of", "retrospective_cohort"] = "historical_as_of"
    baseline_cutoff: Literal["publication", "evaluation"] = "publication"
    baseline_min_posts: int = Field(default=3, ge=3)
    baseline_lookback_days: int = Field(default=365, ge=1, le=3650)
    feature_policy: Literal["retrospective_content", "historical_prediction"]
    maturity_policy: Literal["explicit_window", "collection_proxy"] = "explicit_window"
    sampling_frame: str = Field(min_length=1, max_length=1000)
    covariates: tuple[Literal["duration_seconds", "caption_length"], ...] = ("duration_seconds",)
    # Context is exact-matched; numeric covariates use standardized Euclidean distance.
    context: tuple[Literal["platform", "content_type", "topics", "niche"], ...] = (
        "platform",
        "content_type",
        "topics",
    )
    standardized_caliper: float = Field(default=1, gt=0, le=10)
    publication_caliper_days: float = Field(default=90, gt=0, le=3650)
    max_abs_smd: float = Field(default=0.25, gt=0, le=2)
    target_transform: Literal["identity", "log1p"] = "identity"
    split_policy: Literal["none", "chronological", "creator", "joint"] = "none"
    test_fraction: float = Field(default=0.2, ge=0.1, le=0.4)
    family_id: str = Field(min_length=1, max_length=200)
    family_terms: tuple[str, ...] = Field(min_length=1, max_length=100)
    holdout_id: str | None = Field(default=None, min_length=1, max_length=200)
    creative_recipes: dict[str, str] = Field(default_factory=dict, max_length=6)
    creative_annotation_key: str | None = Field(default=None, min_length=1, max_length=100)
    creative_label_policy: Literal["reviewed_only", "proposals_exploratory"] = "reviewed_only"

    def allowed_features(self) -> set[str]:
        return super().allowed_features() | set(self.creative_recipes)

    @field_validator("knowledge_cutoff", "publication_cutoff")
    @classmethod
    def normalize_time(cls, value: str) -> str:
        from socialdna.ingestion.tabular import timestamp

        return timestamp(value)

    @model_validator(mode="after")
    def coherent_design(self) -> "CorrectedPerformanceSpec":
        import re

        if any(
            not re.fullmatch(r"creative\.[a-z_]+", key)
            or not re.fullmatch(r"creative\.[a-z_]+\.v[1-9][0-9]*", value)
            for key, value in self.creative_recipes.items()
        ) or not set(self.creative_recipes).issubset(self.features):
            raise ValueError(
                "Creative features require declared names and exact versioned recipe IDs"
            )
        estimands = {
            "descriptive": "descriptive",
            "within_creator": "within_creator_association",
            "cross_creator": "cross_creator_comparison",
        }
        if self.estimand != estimands[self.design]:
            raise ValueError("Estimand does not match the declared design")
        if self.model not in ("none", "ols", "poisson"):
            raise ValueError("Version 2 supports OLS/Poisson; legacy GEE/mixed remain version 1")
        if self.model != "none" and self.design != "within_creator":
            raise ValueError("Adjusted models require the identifiable within-creator design")
        if self.model != "none" and not set(self.covariates).issubset(self.features):
            raise ValueError("Model covariates must be included in the declared feature matrix")
        if self.model == "poisson" and self.target_transform != "identity":
            raise ValueError("Poisson models the raw count, not a transformed count")
        if len(set(self.covariates)) != len(self.covariates) or not self.covariates:
            raise ValueError("Matching covariates must be nonempty and unique")
        if len(set(self.context)) != len(self.context) or "platform" not in self.context:
            raise ValueError("Context fields must be unique and include platform")
        if not self.matched and self.design != "descriptive":
            raise ValueError("Within/cross comparisons require declared matching")
        if self.split_policy != "none" and (self.model == "none" or not self.holdout_id):
            raise ValueError("Validation requires a selected model and a reserved holdout_id")
        expected = {*self.features, *(f"{a}*{b}" for a, b in self.interactions)}
        if len(set(self.family_terms)) != len(self.family_terms) or not expected.issubset(
            self.family_terms
        ):
            raise ValueError("Declare every tested feature/interaction in a unique test family")
        return self


AnalysisSpec = PerformanceSpec | CorrectedPerformanceSpec


def parse_performance_spec(values: dict[str, object]) -> AnalysisSpec:
    if values.get("schema_version") == "2.0":
        return CorrectedPerformanceSpec.model_validate(values)
    return PerformanceSpec.model_validate(values)
