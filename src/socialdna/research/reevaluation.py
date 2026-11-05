"""Conservative, deterministic comparisons; never infer global mechanism rejection."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field, model_validator

from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.investigation import ResearchModel
from socialdna.domain.research import CorrectedPerformanceSpec


class ReevaluationSpec(ResearchModel):
    """Optional explicit replacements; omitted analyses retain their registered design."""

    schema_version: Literal["1.0"] = "1.0"
    reason: str = Field(default="New eligible evidence", min_length=1, max_length=2000)
    protocol: EntityRef | None = None
    designs: tuple[CorrectedPerformanceSpec, ...] | None = Field(
        default=None, min_length=1, max_length=4
    )
    evidence: tuple[EvidenceRef, ...] | None = Field(default=None, max_length=100)
    max_analyses: int = Field(default=4, ge=1, le=4)

    @model_validator(mode="after")
    def protocol_kind(self) -> "ReevaluationSpec":
        if self.protocol and self.protocol.kind != "research_protocol":
            raise ValueError("A replacement must be an exact prepared research protocol")
        return self


@dataclass(frozen=True)
class ReevaluationContext:
    request_id: str
    previous: EntityRef
    membership: dict[str, Any]
    changes: list[dict[str, Any]]
    reason: str


def membership(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> dict[str, Any]:
    """Report units, not row occurrences; duplicates/new posts are not new creators."""
    result: dict[str, Any] = {}
    for key in ("post_id", "creator_id"):
        before, after = ({r[key] for r in rows} for rows in (old, new))
        result[key.removesuffix("_id") + "s"] = {
            "reused": sorted(before & after),
            "new": sorted(after - before),
            "removed": sorted(before - after),
        }
    prior_hashes = {r["duplicate_group"] for r in old if r.get("duplicate_group")}
    new_posts = set(result["posts"]["new"])
    result["new_posts_with_reused_content"] = sorted(
        {
            r["post_id"]
            for r in new
            if r["post_id"] in new_posts and r.get("duplicate_group") in prior_hashes
        }
    )
    result["independent_confirmation"] = False
    result["independence_limit"] = (
        "New post/creator IDs describe membership, not verified independence; "
        "audience overlap and unknown content duplicates remain possible."
    )
    return result


def compare(
    previous: dict[str, Any], current: dict[str, Any], context: ReevaluationContext
) -> dict[str, Any]:
    old = {j["hypothesis"]["id"]: j for j in previous["judgments"]}
    transitions = []
    narrowed = bool(context.membership["posts"]["removed"])
    for judgment in current["judgments"]:
        before = old[judgment["hypothesis"]["id"]]
        prior = before["local_association"]["status"]
        status = judgment["local_association"]["status"]
        changed_prediction = before["prediction"] != judgment["prediction"]
        effects = []
        for prior_observation, observation in zip(
            before["local_association"]["observations"],
            judgment["local_association"]["observations"],
            strict=False,
        ):
            prior_term, term = prior_observation["term"], observation["term"]
            if prior_term and term:
                effects.append(
                    {
                        "previous_run_id": prior_observation["run_id"],
                        "current_run_id": observation["run_id"],
                        "estimate_delta": term["estimate"] - prior_term["estimate"],
                        "previous_interval": [prior_term.get("ci_low"), prior_term.get("ci_high")],
                        "current_interval": [term.get("ci_low"), term.get("ci_high")],
                        "qualification": "Descriptive difference, not a test of effect change.",
                    }
                )
        disposition = (
            "contradicted_in_scope"
            if status == "contrary"
            else "weakened"
            if prior == "consistent" and (status != "consistent" or narrowed)
            else "supported_in_scope"
            if status == "consistent"
            else "inconclusive"
        )
        transitions.append(
            {
                "hypothesis_id": judgment["hypothesis"]["id"],
                "previous_status": prior,
                "current_status": status,
                "disposition": disposition,
                "prediction_changed": changed_prediction,
                "effect_changes": effects,
                "comparison": "changed_prediction_not_a_direct_replication"
                if changed_prediction
                else "scope_narrowed"
                if narrowed
                else "same_prediction_cumulative_evidence",
                "previous_observations": before["local_association"]["observations"],
                "current_observations": judgment["local_association"]["observations"],
            }
        )
    return {
        "request_id": context.request_id,
        "previous_assessment_revision_id": context.previous.revision_id,
        "reason": context.reason,
        "changes": context.changes,
        "membership": context.membership,
        "transitions": transitions,
        "sequential_policy": "exploratory_cumulative_repeat_look",
        "independent_confirmation": False,
        "limitations": [
            "Fixed-family adjustments do not correct repeated looks across time.",
            "Local contradictions do not reject a general psychological mechanism.",
            "Non-significance alone is not evidence of absence or a rejection criterion.",
        ],
    }
