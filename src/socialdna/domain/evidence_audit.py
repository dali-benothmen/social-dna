"""Bounded canonical lineage snapshots; graph connectivity is not claim support."""

from typing import Any, Literal

from pydantic import Field

from socialdna.domain.context import ContextModel
from socialdna.domain.evidence import EntityRef, EvidenceRef


class AuditOptions(ContextModel):
    depth: int = Field(default=2, ge=0, le=5, strict=True)
    max_nodes: int = Field(default=50, ge=1, le=100, strict=True)
    max_edges: int = Field(default=100, ge=1, le=200, strict=True)
    include_graph: bool = False
    include_history: bool = True


class EvidenceAudit(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    goal: str
    root: EntityRef
    requested_evidence: EvidenceRef | None = None
    coverage: Literal["canonical-evidence-audit"] = "canonical-evidence-audit"
    status: Literal["success", "partial"]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    citations: tuple[dict[str, Any], ...]
    duplicates: tuple[dict[str, Any], ...]
    revisions: tuple[dict[str, Any], ...]
    research_history: dict[str, Any] | None = None
    graph: dict[str, Any] | None = None
    truncated: bool
    limitations: tuple[str, ...]
    required_actions: tuple[dict[str, str], ...] = ()
