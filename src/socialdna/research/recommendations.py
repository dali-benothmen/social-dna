"""Original proposed strategies with explicit evidence lanes, scope and a next test."""

from typing import Literal

from pydantic import Field, model_validator

from socialdna.domain.context import ContextModel, Key
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.research.candidates import Scope

TARGETS = {
    "production": {
        "camera_angle",
        "composition",
        "movement",
        "lighting",
        "color_focus",
        "shot_size",
        "editing_rhythm",
        "cuts",
        "transitions",
        "pacing",
        "subtitles",
        "visual_effects",
        "music",
        "sound_sync",
    },
    "publishing": {
        "title",
        "thumbnail",
        "caption",
        "keywords",
        "hashtags",
        "local_schedule",
        "cadence",
        "format",
    },
    "distribution": {
        "early_response",
        "retention",
        "shares_saves",
        "watch_time",
        "topic_relevance",
        "eligibility",
    },
    "profile": {
        "bio",
        "display_name",
        "profile_photo",
        "links",
        "pins",
        "branding",
        "pillars",
        "positioning",
        "cta",
    },
}


class StrategyAction(ContextModel):
    target: Key
    change: str = Field(min_length=1, max_length=2000)
    hold_constant: str = Field(min_length=1, max_length=2000)
    measure: str = Field(min_length=1, max_length=2000)
    falsifier: str = Field(min_length=1, max_length=2000)


class RecommendationEvidence(ContextModel):
    evidence: EvidenceRef
    role: Literal["support", "counterevidence"]
    applicability: Literal["direct", "indirect"]
    rationale: str = Field(min_length=1, max_length=2000)


class RecommendationSpec(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    key: Key
    supersedes: EntityRef | None = None
    domain: Literal["production", "publishing", "distribution", "profile"]
    scope: Scope
    actions: tuple[StrategyAction, ...] = Field(min_length=1, max_length=4)
    evidence: tuple[RecommendationEvidence, ...] = Field(min_length=1, max_length=30)
    context: tuple[EntityRef, ...] = Field(default=(), max_length=20)
    counterevidence_search: str = Field(min_length=1, max_length=3000)
    uncertainty: tuple[str, ...] = Field(min_length=1, max_length=20)
    next_test: str = Field(min_length=1, max_length=3000)
    requested_claim: Literal["testable_strategy_not_guaranteed"] = (
        "testable_strategy_not_guaranteed"
    )

    @model_validator(mode="after")
    def original_scoped_proposal(self) -> "RecommendationSpec":
        if any(a.target not in TARGETS[self.domain] for a in self.actions):
            raise ValueError("Action target must belong to the declared production/growth domain")
        ids = [e.evidence.revision_id for e in self.evidence]
        if len(set(ids)) != len(ids) or not any(e.role == "support" for e in self.evidence):
            raise ValueError(
                "Distinct source revisions and at least one qualified support source are required"
            )
        if self.domain == "profile" and self.scope.objective != "conversion":
            raise ValueError(
                "Profile recommendations distinguish measured conversion from public quality"
            )
        if self.domain == "distribution" and self.scope.objective not in (
            "search",
            "recommendation",
        ):
            raise ValueError(
                "Distribution recommendations need a platform-specific channel objective"
            )
        if self.supersedes and self.supersedes.kind != "recommendation":
            raise ValueError("Recommendation revision must name its actual predecessor kind")
        return self
