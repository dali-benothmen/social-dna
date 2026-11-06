"""Shared exact, permission-qualified readers; never retrieve truth from an index."""

import json
from typing import Any

from sqlalchemy import Connection, select

from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.memory.documents import entity_active
from socialdna.storage import content_repository, context_repository, research_repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def citations(
    connection: Connection, ref: EntityRef, *, limit: int = 100
) -> tuple[EvidenceRef, ...]:
    preferred: tuple[EvidenceRef, ...] = ()
    if ref.kind in content_repository.KINDS:
        preferred = (content_repository.cite(connection, ref),)
    elif ref.kind in context_repository.KINDS:
        preferred = (context_repository.cite(connection, ref),)
    if ref.kind in research_repository.KINDS and ref.kind not in {
        "literature_source",
        "psychological_construct",
        "operationalization",
        "research_protocol",
    }:
        preferred = (research_repository.cite(connection, ref),)
    table = metadata.tables["evidence_revisions"]
    existing = tuple(
        EvidenceRef(id=row.evidence_id, revision_id=row.id)
        for row in connection.execute(
            select(table.c.evidence_id, table.c.id)
            .where(table.c.subject_revision_id == ref.revision_id)
            .order_by(table.c.id)
            .limit(limit)
        )
    )
    return tuple({r.revision_id: r for r in (*preferred, *existing)}.values())


def read(connection: Connection, ref: EntityRef) -> tuple[dict[str, Any], tuple[EvidenceRef, ...]]:
    row = entity_active(connection, ref)
    refs = citations(connection, ref)
    for citation in refs:
        EvidenceResolver(connection).resolve(citation, purpose="new_claim")
    return json.loads(row["payload_json"]), refs


def qualified_summary(
    connection: Connection, ref: EntityRef
) -> tuple[str, dict[str, Any], tuple[EvidenceRef, ...]]:
    payload, refs = read(connection, ref)
    lanes = {
        "statistical_analysis": "measured_association_not_causal",
        "research_assessment": "reviewed_protocol_assessment_not_causal",
        "research_finding": "literature_backed_hypothesis_not_proven_mechanism",
        "study_finding": "reviewed_external_literature_not_local_replication",
        "platform_statement": "official_guidance_not_observed_local_effect",
        "profile_review": "human_qualitative_review_not_measured_conversion",
        "funnel_context": "measured_aggregate_funnel_not_profile_effect",
        "recommendation": "proposed_test_not_guaranteed",
        "experiment_assessment": "registered_experiment_assessment_with_scope_limits",
        "creative_pattern": "exploratory_pattern_not_independent_confirmation",
        "discovery_search": "exploratory_search_not_causal",
        "profile_audit": "unreviewed_field_check_not_quality_review",
    }
    if ref.kind not in lanes:
        raise ConfigurationError(
            "Select a qualified assessment/finding, C1 statement/review/funnel, pattern or proposal"
        )
    summary = {
        k: payload[k]
        for k in (
            "claim_level",
            "scope_conditions",
            "judgments",
            "local_association",
            "actions",
            "uncertainty",
            "next_test",
            "sources",
            "assessment_disposition",
            "summary",
            "status",
            "mechanism_status",
            "evidence_roles",
            "competing_explanations",
        )
        if k in payload
    }
    spec = payload.get("spec", {})
    summary["specification"] = {
        k: spec[k]
        for k in (
            "scope",
            "surface",
            "statement",
            "quote",
            "summary",
            "direction",
            "limitations",
            "snapshot",
            "criteria",
            "interpretation",
            "limitation",
            "location",
            "result_summary",
            "prediction",
            "features",
            "adjusters",
            "population",
            "exposure",
            "outcome",
            "design",
        )
        if k in spec
    }
    if ref.kind in ("funnel_context", "profile_review", "profile_audit"):
        summary["result"] = payload.get("result")
    if ref.kind == "statistical_analysis":
        report = json.loads(
            EvidenceRepository(connection).get("statistical_analyses", payload["analysis_id"])[
                "result_json"
            ]
        )
        summary["result"] = report["results"]
        summary["configuration"] = report["analysis_configuration"]
    if ref.kind == "discovery_search":
        summary["result"] = {
            k: payload["result"][k]
            for k in ("status", "selected", "outer", "coverage", "family", "limitations")
            if k in payload["result"]
        }
    summary["scope_match"] = "inspect_declared_scope; not_automatically_generalized_to_comparison"
    return lanes[ref.kind], summary, refs
