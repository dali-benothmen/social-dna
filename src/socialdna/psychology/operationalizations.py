"""Literature applicability is a reviewed judgment, never an embedding similarity."""

from typing import Any

from sqlalchemy import Connection

from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.investigation import HypothesisPlan


def applicability(connection: Connection, plan: HypothesisPlan) -> dict[str, Any]:
    for review in plan.literature:
        citation = EvidenceResolver(connection).resolve(review.finding, purpose="new_claim")
        if citation.locator_kind != "study_excerpt":
            raise ConfigurationError("Literature applicability requires an exact study excerpt")
    relevant = [r for r in plan.literature if r.applicability != "not_applicable"]
    return {
        "status": "reviewed_plausibility_only"
        if relevant and plan.construct_ref
        else "unsupported",
        "reviews": [r.model_dump(mode="json") for r in plan.literature],
        "limitation": "Reviewed applicability is not evidence that a mediator occurred locally.",
    }
