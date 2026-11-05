from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def valid_features(self) -> "PerformanceSpec":
        allowed = {
            "duration_seconds",
            "caption_length",
            "publishing_hour_utc",
            "visual.motion",
            "visual.appearance",
            "audio.loudness",
        }
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
