"""Exact finite comparison scopes and separately qualified synthesis lanes."""

from typing import Any, Literal

from pydantic import Field, model_validator

from socialdna.domain.context import ContextModel
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.research.recommendations import RecommendationSpec


class ComparisonOptions(ContextModel):
    design: CorrectedPerformanceSpec | None = None
    support_revisions: tuple[str, ...] = Field(default=(), max_length=10)
    contrary_revisions: tuple[str, ...] = Field(default=(), max_length=10)
    recommendation: RecommendationSpec | None = None

    @model_validator(mode="after")
    def unique_inputs(self) -> "ComparisonOptions":
        inputs = (*self.support_revisions, *self.contrary_revisions)
        if len(set(inputs)) != len(inputs):
            raise ValueError("Select each prepared revision once with an explicit role")
        return self


class ComparisonSubject(ContextModel):
    url: str
    platform: Literal["youtube", "instagram", "tiktok"]
    kind: Literal["account", "post"]
    role: Literal["left", "right"]
    subject: EntityRef | None = None
    posts: tuple[EntityRef, ...] = Field(default=(), max_length=50)
    identity_inputs: tuple[EntityRef, ...] = ()
    known_posts_count: int = Field(default=0, ge=0)
    reason: str | None = None


class SynthesisSource(ContextModel):
    subject: EntityRef
    role: Literal["support", "counterevidence", "context", "proposal"]
    lane: str
    evidence: tuple[EvidenceRef, ...] = ()
    summary: dict[str, Any]


class URLComparison(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    goal: str
    coverage: Literal["comparison-library-assisted"] = "comparison-library-assisted"
    status: Literal["success", "partial"]
    request_fulfilled: bool
    subjects: tuple[ComparisonSubject, ...]
    manifest: EntityRef
    inventory: tuple[dict[str, Any], ...]
    comparison_run_id: str | None = None
    statistical_evidence: tuple[EvidenceRef, ...] = ()
    quantitative: dict[str, Any] | None = None
    numeric_inference: Literal["withheld", "descriptive_only"]
    compatibility: dict[str, Any]
    counterexamples: tuple[dict[str, Any], ...] = ()
    sources: tuple[SynthesisSource, ...] = ()
    limitations: tuple[str, ...]
    required_actions: tuple[dict[str, str], ...] = ()
