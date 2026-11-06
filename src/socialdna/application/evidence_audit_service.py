"""Exact SQL lineage first; bounded graph/history are separately qualified context."""

import json
import sqlite3
from collections import deque
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Connection, func, select

from socialdna.application.bootstrap import Application
from socialdna.application.context_service import provenance
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.application.workflow_sources import citations
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import hash_config
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.evidence_audit import EvidenceAudit
from socialdna.domain.workflows import WorkflowPlan, WorkflowRequest
from socialdna.memory.documents import current_revision, entity_active, references
from socialdna.reporting.markdown import escape
from socialdna.storage import content_repository as records
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata


def pin(settings: Settings, request: WorkflowRequest) -> dict[str, Any]:
    try:
        return _pin(settings, request)
    except sqlite3.Error:
        raise ConfigurationError("Cannot inspect exact evidence in this library") from None


def _pin(settings: Settings, request: WorkflowRequest) -> dict[str, Any]:
    path = DataPaths(settings.data_dir).database
    if not path.is_file():
        raise ConfigurationError("Evidence audit requires an existing library")
    revision = request.entity_revision
    with immutable_snapshot(path) as connection:
        if request.from_workflow:
            bindings = connection.execute(
                "SELECT revision_id FROM workflow_bindings WHERE workflow_id=? AND role='report'",
                (request.from_workflow,),
            ).fetchall()
            if len(bindings) != 1:
                raise ConfigurationError("Select a finished saved report with one exact output")
            revision = bindings[0][0]
        if request.evidence_reference:
            row = connection.execute(
                "SELECT subject_revision_id FROM evidence_revisions WHERE evidence_id=? AND id=?",
                (request.evidence_reference.id, request.evidence_reference.revision_id),
            ).fetchone()
            if row is None:
                raise ConfigurationError("Unknown exact evidence reference")
            revision = row[0]
        row = connection.execute(
            "SELECT kind,entity_id,id FROM entity_revisions WHERE id=?", (revision,)
        ).fetchone()
        if row is None:
            raise ConfigurationError("Unknown exact entity revision")
    return {
        "audit_root": EntityRef(kind=row[0], id=row[1], revision_id=row[2]),
        "audit_evidence": request.evidence_reference,
    }


def freshness(app: Application, ref: EntityRef) -> dict[str, Any]:
    """A mutable eligibility/currentness view, never a rewrite of the frozen conclusion."""
    with app.database.transaction() as connection:
        payload = records.active(connection, ref)
        changed = []
        seen = set()
        for _, item in references(payload):
            if isinstance(item, EntityRef) and item.revision_id not in seen:
                seen.add(item.revision_id)
                if not current_revision(connection, item):
                    changed.append(item.model_dump())
    return {
        "view": "current_library_not_frozen_conclusion",
        "superseded_inputs": changed,
        "automatic_refit": False,
    }


def _inputs(
    connection: Connection, ref: EntityRef, payload: dict[str, Any]
) -> Iterator[tuple[str, EntityRef | EvidenceRef]]:
    yield from references(payload)
    if ref.kind != "statistical_analysis":
        return
    # Statistical entities store hashes, not their input graph. Follow the actual
    # validated producer projection instead of mistaking a small envelope for full lineage.
    repo = EvidenceRepository(connection)
    report = json.loads(repo.get("statistical_analyses", payload["analysis_id"])["result_json"])
    yield from references(report, "/frozen_statistical_report")
    cutoff = report["analysis_configuration"]["spec"].get("knowledge_cutoff")
    entities = metadata.tables["entity_revisions"]
    for index, row in enumerate(report["posts"] + report.get("reference_population", [])):
        for snapshot in row.get("dependency_snapshot_ids", row.get("snapshot_ids", [])):
            query = select(entities).where(
                entities.c.kind == "metric_snapshot", entities.c.entity_id == snapshot
            )
            if cutoff:
                query = query.where(entities.c.available_at <= cutoff)
            captured = (
                connection.execute(query.order_by(entities.c.revision_no.desc()).limit(1))
                .mappings()
                .first()
            )
            if captured is not None:
                yield f"/frozen_statistical_inputs/{index}/snapshot", repo.ref(dict(captured))
        for feature in row.get("feature_values", {}).values():
            for revision in feature.get("lineage", {}).get("entity_revision_ids", []):
                yield (
                    f"/frozen_statistical_inputs/{index}/feature",
                    repo.ref(repo.get("entity_revisions", revision)),
                )


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    assert plan.audit_root is not None
    root, bounds = plan.audit_root, plan.request.audit
    with app.database.transaction() as connection:
        saved = records.records(connection, identity, "evidence_audit")
    if saved:
        from socialdna.application.workflow_report_service import generate

        return generate(app, identity)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    actions: list[dict[str, str]] = []
    dependencies: dict[str, EntityRef] = {}
    evidence: dict[str, EvidenceRef] = {}
    duplicates: dict[str, list[dict[str, str]]] = {}
    truncated = False
    graph_view = None
    history_root = None
    with app.database.transaction() as connection:
        repo, resolver = EvidenceRepository(connection), EvidenceResolver(connection)
        try:
            entity_active(connection, root)
            if plan.audit_evidence:
                resolver.resolve(plan.audit_evidence, purpose="new_claim")
        except ConfigurationError:
            workflows.state(connection, identity, "awaiting_action", "audit_source_ineligible")
            return {
                "workflow_id": identity,
                "status": "partial",
                "network_attempted": False,
                "required_actions": [
                    {
                        "code": "audit_source_ineligible",
                        "message": "The pinned source is ineligible. Its protected body "
                        "is withheld; select eligible evidence.",
                    }
                ],
            }
        queue = deque([(root, 0)])
        queued = {root.revision_id}
        while queue:
            ref, distance = queue.popleft()
            try:
                row = entity_active(connection, ref)
            except ConfigurationError:
                nodes.append({"ref": ref.model_dump(), "eligible": False, "body": None})
                continue
            dependencies[ref.revision_id] = ref
            payload = json.loads(row["payload_json"])
            source = repo.get("source_records", row["source_id"]) if row["source_id"] else {}
            nodes.append(
                {
                    "ref": ref.model_dump(),
                    "eligible": True,
                    "payload_hash": row["content_hash"],
                    "available_at": row["available_at"],
                    "source_id": row["source_id"],
                    "source": {
                        key: source.get(key)
                        for key in ("source_uri", "permission_basis", "retrieved_at")
                    },
                    "current_revision": current_revision(connection, ref),
                    "claim_level": payload.get("claim_level", "observation_or_producer_record"),
                    "declared_conclusion": {
                        key: payload[key]
                        for key in (
                            "judgments",
                            "local_association",
                            "actions",
                            "uncertainty",
                            "next_test",
                            "scope_conditions",
                            "reevaluation",
                        )
                        if key in payload
                    },
                }
            )
            if ref.kind == "url_comparison":
                nodes[-1]["declared_conclusion"] = {
                    key: payload["result"][key]
                    for key in (
                        "goal",
                        "numeric_inference",
                        "compatibility",
                        "counterexamples",
                        "sources",
                        "required_actions",
                    )
                }
            if history_root is None and ref.kind in (
                "research_question",
                "hypothesis",
                "research_assessment",
            ):
                history_root = ref
            children = list(citations(connection, ref, limit=bounds.max_edges + 1))
            if len(children) > bounds.max_edges:
                truncated = True
            if ref == root and plan.audit_evidence:
                children = [plan.audit_evidence, *children]
            # Exact citations are resolved independently of any search or graph projection.
            for citation in children[: bounds.max_edges]:
                if citation.revision_id in evidence:
                    continue
                if len(evidence) >= bounds.max_edges:
                    truncated = True
                    break
                value = resolver.resolve(citation, purpose="new_claim")
                evidence[citation.revision_id] = citation
                resolved.append(value.model_dump(mode="json"))
                key = hash_config(value.locator.model_dump(mode="json") if value.locator else {})
                duplicates.setdefault(key, []).append(citation.model_dump())
            prior = metadata.tables["entity_revisions"]
            rows = list(
                connection.execute(
                    select(prior.c.id, prior.c.revision_no, prior.c.content_hash)
                    .where(prior.c.kind == ref.kind, prior.c.entity_id == ref.id)
                    .order_by(prior.c.revision_no.desc())
                    .limit(11)
                )
            )
            revisions.append(
                {
                    "selected": ref.model_dump(),
                    "revisions": [dict(r._mapping) for r in rows[:10]],
                    "truncated": len(rows) > 10,
                }
            )
            for path, child in _inputs(connection, ref, payload):
                if len(edges) >= bounds.max_edges:
                    truncated = True
                    break
                target = child
                if isinstance(child, EvidenceRef):
                    value = resolver.resolve(child, purpose="new_claim")
                    target = value.subject
                    if child.revision_id not in evidence and len(evidence) < bounds.max_edges:
                        evidence[child.revision_id] = child
                        resolved.append(value.model_dump(mode="json"))
                        key = hash_config(
                            value.locator.model_dump(mode="json") if value.locator else {}
                        )
                        duplicates.setdefault(key, []).append(child.model_dump())
                assert isinstance(target, EntityRef)
                edges.append(
                    {
                        "source": ref.model_dump(),
                        "target": target.model_dump(),
                        "path": path,
                        "relation": "declared_reference_not_adjudicated_support",
                        "declared_role": "counterevidence"
                        if any(word in path for word in ("contrary", "counterevidence"))
                        else "inspect_producer_role",
                    }
                )
                if distance >= bounds.depth or len(queued) >= bounds.max_nodes:
                    truncated = truncated or target.revision_id not in queued
                elif target.revision_id not in queued:
                    queued.add(target.revision_id)
                    queue.append((target, distance + 1))
        if bounds.include_graph:
            from socialdna.memory.graph import neighborhood

            graph_view = neighborhood(
                connection,
                root.revision_id,
                depth=bounds.depth,
                max_nodes=bounds.max_nodes,
                max_edges=bounds.max_edges,
                historical=True,
            )
            graph_view["pending_changes"] = connection.scalar(
                select(func.count()).select_from(metadata.tables["memory_changes"])
            )
            graph_view["qualification"] = (
                "Optional potentially stale structural view; connectivity is not evidence "
                "strength. No indexing/refit performed."
            )
            # A frozen graph view must not outlive the authority of its nodes,
            # edge owners or citations, even when they are outside the SQL frontier.
            for node in graph_view["nodes"]:
                graph_ref = EntityRef.model_validate(node["ref"])
                dependencies[graph_ref.revision_id] = graph_ref
            for edge in graph_view["edges"]:
                owner = repo.ref(repo.get("entity_revisions", edge["owner_revision_id"]))
                dependencies[owner.revision_id] = owner
                if edge["evidence_revision_id"]:
                    row = repo.get("evidence_revisions", edge["evidence_revision_id"])
                    citation = EvidenceRef(id=row["evidence_id"], revision_id=row["id"])
                    resolver.resolve(citation, purpose="new_claim")
                    evidence[citation.revision_id] = citation
            truncated = truncated or graph_view["truncated"]
    history = None
    if bounds.include_history and history_root:
        from socialdna.application.reevaluation_service import history as research_history

        history = research_history(app, history_root.id, limit=20)
        truncated = truncated or history["truncated"]
        with app.database.transaction() as connection:
            for _, historical in references(history):
                if isinstance(historical, EntityRef):
                    try:
                        entity_active(connection, historical)
                        dependencies[historical.revision_id] = historical
                    except ConfigurationError:
                        pass  # The history service has already replaced its body with a tombstone.
    if truncated:
        actions.append(
            {
                "code": "audit_bound_reached",
                "message": "The finite audit stopped at its declared bounds; "
                "audit a specific child revision for more detail.",
            }
        )
    result = EvidenceAudit(
        workflow_id=identity,
        goal=plan.request.goal,
        root=root,
        requested_evidence=plan.audit_evidence,
        status="partial" if actions else "success",
        nodes=tuple(nodes),
        edges=tuple(edges),
        citations=tuple(resolved),
        revisions=tuple(revisions),
        duplicates=tuple(
            {
                "locator_hash": k,
                "references": v,
                "qualification": "Same exact locator, not independent observations",
            }
            for k, v in duplicates.items()
            if len(v) > 1
        ),
        research_history=history,
        graph=graph_view,
        truncated=truncated,
        limitations=(
            "Canonical record/citation audit, not a new collection, hypothesis refit "
            "or validation of truth.",
            "Declared reference roles and structural graph paths do not establish "
            "causation or independent support.",
            "Prior versions are immutable; eligibility/currentness are rechecked on reuse.",
            "History is bounded and separate from the exact selected root; "
            "missing indices never replace canonical SQL.",
        ),
        required_actions=tuple(actions),
    )
    with app.database.transaction() as connection:
        _, producer = provenance(
            connection,
            {"workflow_id": identity},
            f"urn:socialdna:audit:{identity}",
            "locally_authored; transitive source permissions",
        )
        ref = records.save(
            connection,
            "evidence_audit",
            identity,
            "report",
            {
                "workflow_id": identity,
                "entity_inputs": [r.model_dump() for r in dependencies.values()],
                "evidence_inputs": [r.model_dump() for r in evidence.values()],
                "result": result.model_dump(mode="json"),
            },
            producer,
        )
        records.cite(connection, ref)
        lines = [
            "# Exact evidence audit",
            "",
            escape(result.goal),
            "",
            f"Selected `{root.kind}` revision `{root.revision_id}`",
            "",
            "## Canonical records",
            "",
        ]
        lines += [
            f"- `{n['ref']['kind']}` / `{n['ref']['revision_id']}`; "
            f"eligible: {n['eligible']}; current: {n.get('current_revision')}\n"
            f"  {escape(json.dumps(n.get('declared_conclusion', {}), ensure_ascii=False))}"
            for n in nodes
        ]
        lines += ["", "## Resolved citations", ""]
        lines += [
            f"- `{c['ref']['revision_id']}`: {c['locator_kind']}; "
            f"source {escape(c['source'].get('uri'))}; producer run `{c['producer_run_id']}`"
            for c in resolved
        ]
        lines += [
            "",
            "## Preserved history and duplicate locators",
            "",
            escape(
                json.dumps(
                    {"history": history, "duplicates": result.model_dump()["duplicates"]},
                    ensure_ascii=False,
                )
            ),
            "",
            "## Limitations",
            "",
            *("- " + escape(v) for v in result.limitations),
        ]
        records.freeze(
            app, connection, ref, result.model_dump(mode="json"), "\n".join(lines) + "\n"
        )
        workflows.bind(connection, identity, "capture", root, None)
        workflows.bind(connection, identity, "report", ref, None)
        workflows.state(connection, identity, "partial" if actions else "completed")
    return records.load(app, ref, "json")
