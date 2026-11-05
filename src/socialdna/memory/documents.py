"""Allowlisted canonical representations and shared read-time eligibility gates."""

import json
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Connection, select

from socialdna.application.evidence_service import EvidenceResolver, assert_active_inputs
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.storage.audience_retention import is_redacted
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

CHUNK_SIZE = 800
REPRESENTATION = "citation-text-v1"
# Deliberately exclude authors, arbitrary source/protocol metadata, identifiers,
# URLs and full report/population rows. References are separately validated.
TEXT_KEYS = {
    "text",
    "quote",
    "excerpt",
    "caption",
    "question",
    "statement",
    "population",
    "title",
    "summary",
    "description",
    "rationale",
    "limitation",
    "limitations",
    "labels",
    "label",
    "technique",
    "key",
    "state",
    "verdict",
    "meaning",
    "semantics",
    "unit",
    "value",
    "availability",
    "reason",
    "interpretation",
    "claim_level",
    "denominator_definition",
    "numerator_definition",
    "aggregation_limitations",
    "window_start",
    "window_end",
    "data_cutoff",
    "source_point",
    "source_start",
    "source_end",
    "term",
    "diagnostic",
    "estimate",
    "ci_lower",
    "ci_upper",
    "p_value",
    "q_value",
    "effect_size",
    "n_posts",
    "n_creators",
    "status",
    "method",
    "analysis_kind",
}


def references(
    value: Any, path: str = "", depth: int = 0
) -> Iterator[tuple[str, EntityRef | EvidenceRef]]:
    if depth > 24:
        raise StorageIntegrityError("Representation reference nesting exceeds its budget")
    if isinstance(value, dict):
        if set(value) == {"kind", "id", "revision_id"}:
            yield path, EntityRef.model_validate(value)
        elif set(value) == {"id", "revision_id"}:
            yield path, EvidenceRef.model_validate(value)
        else:
            for key, child in value.items():
                yield from references(child, path + "/" + key, depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from references(child, path + "/" + str(index), depth + 1)


def text_fields(value: dict[str, Any]) -> str:
    lines = []
    for key, item in value.items():
        if key in {
            "annotation",
            "cluster",
            "spec",
            "result",
            "clock",
            "link",
            "report",
        } and isinstance(item, dict):
            nested = text_fields(item)
            if nested:
                lines.append(key + ":\n" + nested)
        if key in TEXT_KEYS and item is not None:
            if isinstance(item, dict) and "revision_id" in item:
                continue
            lines.append(key + ": " + (item if isinstance(item, str) else json.dumps(item)))
    # Do not silently truncate a canonical description (or invent a summary).
    text = "\n".join(lines)
    if len(text) > 64_000:
        raise ConfigurationError("Canonical representation exceeds 64,000 characters")
    return text


def current_revision(connection: Connection, ref: EntityRef, as_of: str | None = None) -> bool:
    table = metadata.tables["entity_revisions"]
    statement = select(table.c.id).where(table.c.kind == ref.kind, table.c.entity_id == ref.id)
    if as_of:
        statement = statement.where(
            table.c.available_at.is_not(None), table.c.available_at <= as_of
        )
    latest = connection.scalar(statement.order_by(table.c.revision_no.desc()).limit(1))
    if latest != ref.revision_id:
        return False
    # Removed annotations are historical, not current merely because their own
    # identity has not changed. Check membership in each actual latest set.
    memberships = {
        "creative_event": (
            "creative_annotation_members",
            "annotation_revision_id",
            "event_revision_id",
        ),
        "creative_coverage": (
            "creative_set_coverages",
            "annotation_revision_id",
            "coverage_revision_id",
        ),
        "reaction_annotation": (
            "audience_set_reactions",
            "set_revision_id",
            "member_revision_id",
        ),
        "reaction_cluster": ("audience_set_clusters", "set_revision_id", "member_revision_id"),
        "content_reaction_link": ("audience_set_links", "set_revision_id", "member_revision_id"),
    }
    if ref.kind in memberships:
        name, parent_key, child_key = memberships[ref.kind]
        membership = metadata.tables[name]
        if parent_key in membership.c and child_key in membership.c:
            parents: list[str] = list(
                connection.scalars(
                    select(membership.c[parent_key]).where(
                        membership.c[child_key] == ref.revision_id
                    )
                )
            )
            return any(
                current_revision(
                    connection,
                    EvidenceRepository(connection).ref(
                        EvidenceRepository(connection).get("entity_revisions", parent)
                    ),
                    as_of,
                )
                for parent in parents
            )
    return True


def entity_active(
    connection: Connection,
    ref: EntityRef,
    *,
    as_of: str | None = None,
    ancestors: tuple[str, ...] = (),
) -> dict[str, Any]:
    if ref.revision_id in ancestors or len(ancestors) >= 24:
        raise StorageIntegrityError("Cyclic or excessively deep memory entity dependencies")
    repository = EvidenceRepository(connection)
    row = repository.entity(ref)
    assert_active_inputs(connection, source_ids=(row["source_id"],) if row["source_id"] else ())
    if as_of and (not row["available_at"] or row["available_at"] > as_of):
        raise ConfigurationError("Entity was not known at this cutoff")
    # Existing citation gates implement audience expiry, behavioral parent/series
    # checks and producing-run dependencies. Never replace those with payload flags.
    citations = metadata.tables["evidence_revisions"]
    rows = list(
        connection.execute(
            select(citations.c.evidence_id, citations.c.id).where(
                citations.c.subject_revision_id == ref.revision_id
            )
        )
    )
    if rows:
        for item in rows:
            EvidenceResolver(connection).resolve(
                EvidenceRef(id=str(item.evidence_id), revision_id=str(item.id)),
                purpose="new_claim",
                as_of=as_of,
            )
    else:
        payload = json.loads(row["payload_json"])
        for _, child in references(payload):
            if isinstance(child, EvidenceRef):
                EvidenceResolver(connection).resolve(child, purpose="new_claim", as_of=as_of)
            elif child.revision_id != ref.revision_id:
                entity_active(
                    connection, child, as_of=as_of, ancestors=(*ancestors, ref.revision_id)
                )
    return row


def hydrate(
    connection: Connection,
    revision: dict[str, Any],
    *,
    as_of: str | None = None,
    historical: bool = False,
) -> dict[str, Any] | None:
    if revision["redacted"]:
        return None
    repository = EvidenceRepository(connection)
    owner = repository.ref(repository.get("entity_revisions", revision["owner_revision_id"]))
    try:
        if not historical and not current_revision(connection, owner, as_of):
            return None
        entity_active(connection, owner, as_of=as_of)
        bindings = metadata.tables["vector_document_evidence"]
        citations = []
        identity: str
        for identity in connection.scalars(
            select(bindings.c.evidence_revision_id).where(
                bindings.c.document_revision_id == revision["id"]
            )
        ):
            row = repository.get("evidence_revisions", identity)
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef(id=row["evidence_id"], revision_id=identity),
                purpose="new_claim",
                as_of=as_of,
            )
            citations.append(resolved.model_dump(mode="json"))
    except ConfigurationError:
        return None
    if hash_config(revision["text"]) != revision["content_hash"]:
        raise StorageIntegrityError("Memory document text checksum mismatch; rebuild required")
    return {
        "document_id": revision["document_id"],
        "document_revision_id": revision["id"],
        "owner": owner.model_dump(),
        "text": revision["text"],
        "citations": citations,
        "representation": json.loads(revision["metadata_json"]),
        "available_at": revision["available_at"],
        "historical": historical,
    }


def build(connection: Connection, kind: str, identity: str) -> dict[str, Any] | None:
    repository = EvidenceRepository(connection)
    citations: list[EvidenceRef] = []
    locator: dict[str, Any] = {}
    if kind == "evidence":
        if is_redacted(connection, "evidence_revision", identity):
            return None
        citation = repository.get("evidence_revisions", identity)
        ref = EvidenceRef(id=citation["evidence_id"], revision_id=identity)
        resolved = EvidenceResolver(connection).resolve(ref)
        if not resolved.eligible or resolved.locator is None:
            return None
        owner = resolved.subject
        locator = resolved.locator.model_dump(mode="json")
        citations = [ref]
        representation_key = ref.id
        available_at = resolved.available_at
    else:
        if is_redacted(connection, "entity_revision", identity):
            return None
        row = repository.get("entity_revisions", identity)
        if row["kind"] not in ("research_question", "hypothesis"):
            return None
        owner = repository.ref(row)
        representation_key = owner.kind + ":" + owner.id
        available_at = row["available_at"]
    try:
        row = entity_active(connection, owner)
    except ConfigurationError:
        return None
    payload = json.loads(row["payload_json"])
    if kind != "evidence":
        citations = [ref for _, ref in references(payload) if isinstance(ref, EvidenceRef)]
    if locator.get("kind") in ("comment_span", "post_text"):
        text = locator["quote"]  # Index only the permitted exact cited span.
    else:
        text = text_fields(payload)
        if locator.get("excerpt"):
            text += "\n" + locator["excerpt"]
        if owner.kind == "creative_event":
            technique = EntityRef.model_validate(payload["technique"])
            text = (
                text_fields(json.loads(repository.entity(technique)["payload_json"])) + "\n" + text
            )
        if locator.get("kind") == "metric_snapshot":
            definition = EntityRef.model_validate(locator["definition"])
            text = (
                text_fields(json.loads(repository.entity(definition)["payload_json"]))
                + "\n"
                + text_fields(locator)
            )
        if locator.get("kind") == "statistical_result":
            text = "Scoped statistical result (not a causal effect)\n" + text_fields(locator)
            analysis = repository.get("statistical_analyses", locator["analysis_id"])
            report = json.loads(analysis["result_json"])
            if locator["result_id"]:
                result = repository.get("statistical_results", locator["result_id"])
                text += "\n" + text_fields(result)
            else:
                diagnostic = report["results"][locator["diagnostic"]]
                if isinstance(diagnostic, dict):
                    text += "\n" + text_fields(diagnostic)
            text += "\nanalysis scope: " + locator["analysis_id"]
    if not text.strip():
        return None  # No semantic claims are invented for bare frames/scenes.
    family = (
        "audience_reactions"
        if owner.kind.startswith(("reaction_", "audience_", "content_reaction"))
        or owner.kind == "comment"
        else "behavioral_observations"
        if locator.get("kind") in ("behavioral_record", "metric_snapshot")
        else "statistical_findings"
        if owner.kind == "statistical_analysis"
        else "psychological_patterns"
        if owner.kind == "hypothesis"
        else "research_knowledge"
        if owner.kind == "research_question"
        else "content_segments"
    )
    return {
        "owner": owner,
        "text": text,
        "citations": citations,
        "key": representation_key,
        "family": family,
        "available_at": available_at,
        "locator": locator,
        "payload": payload,
        "claim_level": "hypothesis" if owner.kind == "hypothesis" else "observation",
    }
