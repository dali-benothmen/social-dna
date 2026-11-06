"""Prospective, fixed-roster two-arm experiments; no publishing or participant data."""

from collections import Counter
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from socialdna.domain.context import ContextModel, Key
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.ingestion.tabular import timestamp
from socialdna.research.candidates import Scope


class Variant(ContextModel):
    key: Key
    change: str = Field(min_length=1, max_length=2000)


class Unit(ContextModel):
    key: Key
    account: EntityRef
    block: Key
    starts_at: str
    # Only nonrandomized/source-native registrations supply assignments.
    variant: Key | None = None

    _time = field_validator("starts_at")(timestamp)


class Outcome(ContextModel):
    key: Key
    definition: EntityRef
    role: Literal["primary", "secondary", "mechanism"]
    direction: Literal["positive", "negative"]
    minimum_meaningful_difference: float = Field(ge=0)
    window_seconds: int = Field(strict=True, gt=0, le=31_536_000)
    window_offset_seconds: int = Field(default=0, strict=True, ge=0, le=31_536_000)
    lag_seconds: int = Field(default=0, strict=True, ge=0, le=31_536_000)
    operationalization: EntityRef | None = None

    @model_validator(mode="after")
    def typed(self) -> "Outcome":
        if self.definition.kind != "behavioral_metric_definition":
            raise ValueError("Outcomes require actual source-defined behavioral metrics")
        if (self.role == "mechanism") != (self.operationalization is not None):
            raise ValueError(
                "Mechanism measurements need an actual reviewed/unvalidated instrument"
            )
        if self.operationalization and self.operationalization.kind != "operationalization":
            raise ValueError("Use the registered operationalization kind")
        return self


class HypothesisPrediction(ContextModel):
    hypothesis: EntityRef
    outcome_key: Key
    direction: Literal["positive", "negative"]
    rationale: str = Field(min_length=1, max_length=2000)


class ExperimentSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    analysis_method: Literal["paired-assignment-1"] = "paired-assignment-1"
    key: Key
    version: int = Field(default=1, strict=True, ge=1, le=10)
    predecessor: EntityRef | None = None
    scope: Scope
    domain: Literal["production", "publishing", "distribution", "profile"]
    assignment_unit: Literal["post", "account_period", "impression"]
    assignment_method: Literal["engine_block_randomized", "nonrandomized", "source_native"]
    variants: tuple[Variant, Variant]
    units: tuple[Unit, ...] = Field(min_length=2, max_length=200)
    outcomes: tuple[Outcome, ...] = Field(min_length=1, max_length=6)
    seed: int = Field(default=42, strict=True, ge=0, le=2**32 - 1)
    permutation_resamples: int = Field(default=9999, strict=True, ge=999, le=19999)
    stopping: Literal["fixed_complete_roster_no_interim_looks"] = (
        "fixed_complete_roster_no_interim_looks"
    )
    precision_rationale: str = Field(min_length=1, max_length=2000)
    held_constant: tuple[str, ...] = Field(min_length=1, max_length=20)
    interference_plan: str = Field(min_length=1, max_length=2000)
    authority: str = Field(min_length=1, max_length=2000)
    ethics_and_permissions: str = Field(min_length=1, max_length=2000)
    origin: tuple[EvidenceRef, ...] = Field(default=(), max_length=20)
    context: tuple[EntityRef, ...] = Field(default=(), max_length=100)
    prior_assessment: EntityRef | None = None
    predictions: tuple[HypothesisPrediction, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def bounded_design(self) -> "ExperimentSpec":
        if len({v.key for v in self.variants}) != 2 or len({u.key for u in self.units}) != len(
            self.units
        ):
            raise ValueError("Two distinct variants and unique assignment-unit keys are required")
        if (
            len({o.key for o in self.outcomes}) != len(self.outcomes)
            or Counter(o.role for o in self.outcomes)["primary"] != 1
        ):
            raise ValueError("Declare unique outcomes and exactly one primary")
        if len({o.definition.revision_id for o in self.outcomes}) != len(self.outcomes):
            raise ValueError("One counter cannot be tested as several different outcomes")
        if any(u.account.kind != "account" for u in self.units):
            raise ValueError("Assignment units require actual authorized account revisions")
        if self.assignment_method == "engine_block_randomized":
            if self.assignment_unit == "impression" or any(u.variant for u in self.units):
                raise ValueError(
                    "Engine randomization uses post/account units, not source arms/impressions"
                )
            if any(n != 2 for n in Counter(u.block for u in self.units).values()):
                raise ValueError(
                    "The initial randomized estimator requires matched two-unit blocks"
                )
        elif any(u.variant not in {v.key for v in self.variants} for u in self.units):
            raise ValueError(
                "Nonrandomized/native source units require supplied variant assignments"
            )
        if (self.assignment_unit == "impression") != (self.assignment_method == "source_native"):
            raise ValueError("Native impression reports require source-native assignment evidence")
        if self.domain == "profile" and self.assignment_unit != "account_period":
            raise ValueError("Profile interventions require actual account-period assignment")
        if self.domain == "profile" and self.scope.objective != "conversion":
            raise ValueError("Profile experiments must name the actual conversion objective")
        if self.domain == "distribution" and self.scope.objective not in (
            "search",
            "recommendation",
        ):
            raise ValueError("Distribution experiments require a platform/surface objective")
        if len({p.hypothesis.id for p in self.predictions}) != len(self.predictions):
            raise ValueError("Register each hypothesis prediction once")
        if any(
            p.hypothesis.kind != "hypothesis" or p.outcome_key not in {o.key for o in self.outcomes}
            for p in self.predictions
        ):
            raise ValueError("Predictions must bind actual hypotheses and declared outcomes")
        if bool(self.predictions) != bool(self.prior_assessment):
            raise ValueError(
                "Hypothesis feedback needs an exact prior assessment and declared predictions"
            )
        return self

    def final_cutoff(self) -> str:
        return timestamp(
            max(
                (
                    datetime.fromisoformat(u.starts_at)
                    + timedelta(
                        seconds=max(
                            o.window_offset_seconds + o.window_seconds + o.lag_seconds
                            for o in self.outcomes
                        )
                    )
                ).isoformat()
                for u in self.units
            )
        )


class UnitResult(ContextModel):
    unit_key: Key
    subject: EntityRef | None = None
    implemented_variant: Key | None = None
    outcomes: dict[str, EntityRef] = Field(default_factory=dict, max_length=6)
    context: tuple[EntityRef, ...] = Field(default=(), max_length=4)
    missing_reason: str | None = Field(default=None, min_length=1, max_length=2000)


class ExecutionReview(ContextModel):
    reviewer: str = Field(min_length=1, max_length=200)
    basis: str = Field(min_length=1, max_length=3000)
    allocation_intact: bool | None
    no_spillover: bool | None
    no_carryover: bool | None
    no_concurrent_changes: bool | None
    no_interim_looks: bool | None
    complete_roster: bool | None
    # These are reviewed source attestations, not engine-verified facts.
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=20)


class ExperimentResults(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    key: Key
    registration: EntityRef
    supersedes: EntityRef | None = None
    correction_reason: str | None = Field(default=None, min_length=1, max_length=2000)
    source_uri: str = Field(min_length=1, max_length=2000)
    permission_basis: Literal["creator_authorized_results", "permitted_native_experiment_export"]
    collected_at: str
    review: ExecutionReview
    deviations: tuple[str, ...] = Field(default=(), max_length=20)
    units: tuple[UnitResult, ...] = Field(min_length=1, max_length=200)

    _time = field_validator("collected_at")(timestamp)

    @model_validator(mode="after")
    def unambiguous(self) -> "ExperimentResults":
        if self.registration.kind != "experiment_registration":
            raise ValueError("Results require an exact registered experiment revision")
        if len({u.unit_key for u in self.units}) != len(self.units):
            raise ValueError("Repeated assignment units cannot increase sample size")
        if bool(self.supersedes) != bool(self.correction_reason):
            raise ValueError("Corrections require both the prior results and an explicit reason")
        return self
