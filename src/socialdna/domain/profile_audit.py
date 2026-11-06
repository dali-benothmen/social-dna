"""Unreviewed profile proposals are not C1-D human assessments or conversion metrics."""

from typing import Literal

from pydantic import Field

from socialdna.domain.context import ContextModel
from socialdna.domain.evidence import EntityRef, EvidenceRef


class ProfileFinding(ContextModel):
    field: str
    direction: Literal["strength", "weakness", "unknown"]
    observation: str
    proposal: str
    priority: Literal["check", "consider", "review"]
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1)


class ProfileAuditProposal(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    canonical_url: str
    account: EntityRef
    snapshot: EntityRef
    captured_at: str
    goal: str
    focus: Literal["balanced", "strengths", "improvements"]
    method: Literal["profile-field-checks-1"] = "profile-field-checks-1"
    producer: str
    review_state: Literal["unreviewed_proposal"] = "unreviewed_proposal"
    coverage: Literal["profile-observation-assisted"] = "profile-observation-assisted"
    status: Literal["partial"] = "partial"
    request_fulfilled: Literal[False] = False
    findings: tuple[ProfileFinding, ...]
    photo_measurements: dict[str, int | str] | None = None
    conversion_effect: None = None
    limitations: tuple[str, ...]
    required_actions: tuple[dict[str, str], ...]
