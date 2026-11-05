"""Frozen, deliberately small discovery grammar; no executable formulas or LLM fitting."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from socialdna.domain.context import ContextModel, Key
from socialdna.domain.evidence import EntityRef
from socialdna.domain.platform_research import SURFACES
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.ingestion.tabular import timestamp


class Candidate(ContextModel):
    key: Key
    kind: Literal["main", "interaction", "quadratic", "spline"]
    features: tuple[str, ...] = Field(min_length=1, max_length=2)
    adjusters: tuple[str, ...] = Field(default=(), max_length=4)
    alphas: tuple[float, ...] = Field(default=(0.0,), min_length=1, max_length=3)
    proposal_source: str = Field(min_length=1, max_length=1000)
    prediction: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def coherent(self) -> "Candidate":
        keys = self.features + self.adjusters
        if len(keys) != len(set(keys)) or len(self.features) != (
            2 if self.kind == "interaction" else 1
        ):
            raise ValueError("Declare distinct drivers/adjusters and the correct interaction order")
        if len(set(self.alphas)) != len(self.alphas) or any(a < 0 or a > 100 for a in self.alphas):
            raise ValueError("Use unique fixed ridge strengths between zero and 100")
        return self


class Scope(ContextModel):
    platform: str = Field(min_length=1, max_length=64)
    surface: str = Field(min_length=1, max_length=100)
    native_format: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=40)
    audience: str = Field(min_length=1, max_length=1000)
    market: str = Field(min_length=2, max_length=100)
    niches: tuple[str, ...] = Field(min_length=1, max_length=10)
    objective: Literal["aggregate_attention", "search", "recommendation", "conversion"]
    traffic: Literal["organic", "paid", "collaboration", "unknown"]
    period_start: str
    period_end: str
    basis: str = Field(min_length=1, max_length=2000)

    _times = field_validator("period_start", "period_end")(timestamp)

    @model_validator(mode="after")
    def coherent(self) -> "Scope":
        if self.period_start >= self.period_end or len(set(self.niches)) != len(self.niches):
            raise ValueError("Use an ordered policy/source period and unique niche labels")
        if self.objective in ("search", "recommendation"):
            if self.platform not in SURFACES or self.surface not in SURFACES[self.platform]:
                raise ValueError("Distribution research needs a platform-specific surface")
            if (self.surface == "search") != (self.objective == "search"):
                raise ValueError("Search and recommendation surfaces are separate objectives")
            if self.traffic == "unknown":
                raise ValueError("Distribution comparisons need a reviewed exposure lane")
        return self


class PostsInput(ContextModel):
    kind: Literal["posts"] = "posts"
    analysis: CorrectedPerformanceSpec
    publications: tuple[EntityRef, ...] = Field(default=(), max_length=500)
    windows: tuple[EntityRef, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def source_only(self) -> "PostsInput":
        if self.analysis.model != "none" or self.analysis.split_policy != "none":
            raise ValueError("The v2 specification supplies canonical inputs, not a second fit")
        if self.analysis.maturity_policy != "explicit_window":
            raise ValueError("Discovery requires source-defined explicit outcome windows")
        return self


class DistributionInput(ContextModel):
    kind: Literal["distribution"] = "distribution"
    observations: tuple[EntityRef, ...] = Field(min_length=1, max_length=500)
    statements: tuple[EntityRef, ...] = Field(default=(), max_length=30)
    timing: Literal["retrospective_association", "available_before_later_window"]


class FunnelsInput(ContextModel):
    kind: Literal["funnels"] = "funnels"
    observations: tuple[EntityRef, ...] = Field(min_length=1, max_length=500)
    numerator: str = Field(min_length=1, max_length=100)
    denominator: str = Field(min_length=1, max_length=100)
    exposure: Literal["source_attested"] = "source_attested"


Input = Annotated[PostsInput | DistributionInput | FunnelsInput, Field(discriminator="kind")]


class DiscoverySpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    key: Key
    family_id: Key
    parent_search: EntityRef | None = None
    input: Input
    scope: Scope
    as_of: str
    candidates: tuple[Candidate, ...] = Field(min_length=1, max_length=12)
    split: Literal["creator", "chronological", "joint"] = "creator"
    test_fraction: float = Field(default=0.25, ge=0.15, le=0.4)
    transfer_niches: tuple[str, ...] = Field(default=(), max_length=3)
    holdout_id: Key
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    max_fits: int = Field(default=128, ge=1, le=128)
    stopping_rule: Literal["complete_frozen_round"] = "complete_frozen_round"
    claim_level: Literal["exploratory_observational"] = "exploratory_observational"

    _time = field_validator("as_of")(timestamp)

    @model_validator(mode="after")
    def bounded(self) -> "DiscoverySpec":
        if len({c.key for c in self.candidates}) != len(self.candidates):
            raise ValueError("Candidate keys must be unique")
        # Three fixed inner folds per alpha, one descriptive fit per candidate,
        # and at most two outer-model fits (in-scope and transfer use the same fit).
        needed = sum(3 * len(c.alphas) + 1 for c in self.candidates) + 1
        if needed > self.max_fits:
            raise ValueError(f"Frozen search requires {needed} fits, exceeding the declared budget")
        if not set(self.transfer_niches).issubset(self.scope.niches) or len(
            set(self.transfer_niches)
        ) != len(self.transfer_niches):
            raise ValueError("Transfer labels must be unique members of the declared scope")
        if set(self.transfer_niches) == set(self.scope.niches):
            raise ValueError("Reserve at least one training niche")
        if isinstance(self.input, PostsInput):
            if self.input.analysis.knowledge_cutoff != self.as_of:
                raise ValueError("Discovery and canonical population knowledge cutoffs must agree")
            if self.scope.objective != "aggregate_attention":
                raise ValueError("Aggregate post metrics cannot identify search or recommendation")
        elif isinstance(self.input, DistributionInput):
            if self.scope.objective not in ("search", "recommendation"):
                raise ValueError("Distribution observations need a surface-specific objective")
        elif self.scope.objective != "conversion":
            raise ValueError("Measured funnels need a conversion objective")
        return self


class ConfirmationSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    key: Key
    family_id: Key
    discovery: EntityRef
    input: Input
    scope: Scope
    as_of: str
    holdout_id: Key
    direction: Literal["positive", "negative"]
    minimum_absolute_effect: float = Field(ge=0)
    interpretation: str = Field(min_length=1, max_length=2000)

    _time = field_validator("as_of")(timestamp)
