"""First-use research projections, source eligibility and exact excerpt bindings."""

import json
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef, ResearchLocator, StudyLocator
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {
    "recommendation",
    "experiment_registration",
    "experiment_results",
    "experiment_analysis",
    "experiment_assessment",
    "discovery_search",
    "creative_pattern",
    "literature_source",
    "study_finding",
    "psychological_construct",
    "operationalization",
    "research_protocol",
    "research_assessment",
    "research_finding",
    "experiment_brief",
}


def provenance(
    connection: Connection,
    key: str,
    payload: dict[str, Any],
    *,
    uri: str | None = None,
    permission: str = "user_authored_research",
    source_kind: str | None = None,
) -> str:
    source_id = stable_id("research-source", uri or key)
    connection.execute(
        insert(metadata.tables["source_records"])
        .values(
            id=source_id,
            source_kind=source_kind or ("reviewed_literature" if uri else "research_import"),
            source_uri=uri or "urn:socialdna:research:" + key,
            permission_basis=permission,
            terms_json=canonical_json({"review": "human supplied; not automatic verification"}),
            retrieved_at=utc_now(),
            content_hash=hash_config(payload),
        )
        .on_conflict_do_nothing()
    )
    identity = stable_id("research-provenance", source_id, hash_config(payload))
    connection.execute(
        insert(metadata.tables["provenance_records"])
        .values(
            id=identity,
            source_record_id=source_id,
            method="reviewed-research-1",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json({"input_hash": hash_config(payload)}),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    return identity


def save(
    connection: Connection,
    kind: str,
    key: str,
    payload: dict[str, Any],
    provenance_id: str,
    *,
    entities: tuple[EntityRef, ...] = (),
    evidence: tuple[EvidenceRef, ...] = (),
) -> EntityRef:
    return EvidenceRepository(connection).save_entity(
        kind,
        stable_id("research", kind, key),
        {
            **payload,
            "entity_inputs": [r.model_dump() for r in entities],
            "evidence_inputs": [r.model_dump() for r in evidence],
        },
        provenance_id,
        available_at=utc_now(),
    )


def cite(connection: Connection, ref: EntityRef) -> EvidenceRef:
    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    payload = json.loads(row["payload_json"])
    if ref.kind == "study_finding":
        source = EntityRef.model_validate(payload["source_document"])
        finding = payload["spec"]
        locator: StudyLocator | ResearchLocator = StudyLocator(
            subject=ref,
            source_document=source,
            **{k: finding[k] for k in ("start_char", "end_char", "quote", "location")},
        )
        table, values = (
            "study_evidence_bindings",
            {
                "finding_revision_id": ref.revision_id,
                "source_revision_id": source.revision_id,
            },
        )
    elif ref.kind in (
        "recommendation",
        "experiment_registration",
        "experiment_results",
        "experiment_analysis",
        "experiment_assessment",
        "research_assessment",
        "research_finding",
        "experiment_brief",
        "discovery_search",
        "creative_pattern",
    ):
        locator = ResearchLocator(subject=ref)
        table, values = "research_evidence_bindings", {"subject_revision_id": ref.revision_id}
    else:
        raise ConfigurationError("This research kind has no direct evidence binding")
    citation = repo.save_evidence(
        stable_id("research-evidence", ref.revision_id),
        locator,
        row["provenance_id"],
        available_at=row["available_at"],
    )
    connection.execute(
        insert(metadata.tables[table])
        .values(
            evidence_revision_id=citation.revision_id,
            **values,
        )
        .on_conflict_do_nothing()
    )
    return citation


def active(
    connection: Connection,
    ref: EntityRef,
    as_of: str | None = None,
    *,
    ancestors: frozenset[str] = frozenset(),
) -> tuple[EvidenceRef, ...]:
    """Validate entity closure; caller resolves returned evidence with its cycle guards."""
    from socialdna.application.evidence_service import assert_active_inputs

    if ref.revision_id in ancestors or len(ancestors) >= 24:
        raise StorageIntegrityError("Cyclic or excessively deep research dependencies")
    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    if as_of and (not row["available_at"] or row["available_at"] > as_of):
        raise ConfigurationError("Research input was not available at the cutoff")
    if row["source_id"]:
        assert_active_inputs(connection, source_ids=(row["source_id"],))
    payload = json.loads(row["payload_json"])
    if ref.kind == "discovery_search" and "snapshot" in payload:
        from socialdna.application.statistical_service import assert_design_inputs

        assert_design_inputs(
            connection, [r for r in payload["snapshot"]["rows"] if "source_ids" in r]
        )
    if ref.kind == "literature_source":
        latest = repo.latest("literature_source", ref.id)
        assert latest is not None
        current = json.loads(repo.entity(latest)["payload_json"])["spec"]
        if (
            payload["spec"]["review_status"] != "reviewed"
            or current["review_status"] != "reviewed"
            or payload["spec"]["publication_status"] == "retracted"
            or current["publication_status"] == "retracted"
            or (current["publication_status"] == "corrected" and latest != ref)
        ):
            raise ConfigurationError("Literature is unverified, corrected or retracted")
    dependencies = [EvidenceRef.model_validate(r) for r in payload.get("evidence_inputs", [])]
    for raw in payload.get("entity_inputs", []):
        child = EntityRef.model_validate(raw)
        if child.kind in KINDS:
            dependencies.extend(
                active(connection, child, as_of, ancestors=ancestors | {ref.revision_id})
            )
        else:
            child_row = repo.entity(child)
            from socialdna.storage.context_repository import KINDS as CONTEXT_KINDS
            from socialdna.storage.context_repository import cite as context_cite

            if child.kind in CONTEXT_KINDS:
                dependencies.append(context_cite(connection, child))
            if child.kind in ("research_question", "hypothesis"):
                child_payload = json.loads(child_row["payload_json"])
                dependencies.extend(
                    EvidenceRef.model_validate(r) for r in child_payload.get("evidence", [])
                )
            if child_row["source_id"]:
                assert_active_inputs(connection, source_ids=(child_row["source_id"],))
    return tuple({r.revision_id: r for r in dependencies}.values())


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    if ref.kind in ("research_protocol", "research_assessment"):
        table = "research_protocols" if ref.kind == "research_protocol" else "research_assessments"
        row = repo.get(table, ref.revision_id, "revision_id")
        if row["question_revision_id"] != payload["question"]["revision_id"]:
            raise StorageIntegrityError("Research question projection mismatch")
        if ref.kind == "research_assessment":
            if (
                row["protocol_revision_id"] != payload["protocol"]["revision_id"]
                or row["input_hash"] != payload["input_hash"]
            ):
                raise StorageIntegrityError("Research assessment projection mismatch")
            table_obj = metadata.tables["assessment_dependencies"]
            rows = (
                repo.connection.execute(
                    select(table_obj).where(table_obj.c.assessment_revision_id == ref.revision_id)
                )
                .mappings()
                .all()
            )
            actual = {(r["entity_revision_id"], r["evidence_revision_id"]) for r in rows}
            expected = {(r["revision_id"], None) for r in payload["entity_inputs"]} | {
                (None, r["revision_id"]) for r in payload["evidence_inputs"]
            }
            if actual != expected:
                raise StorageIntegrityError("Research assessment dependency projection mismatch")
