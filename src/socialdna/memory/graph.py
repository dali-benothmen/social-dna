"""Qualified SQLite relations; only a bounded view is materialized in NetworkX."""

import json
from collections import deque
from typing import Any

from sqlalchemy import Connection, or_, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.memory.documents import current_revision, entity_active, references
from socialdna.storage.evidence_repository import AUTHORED_KINDS, LEGACY_KINDS, EvidenceRepository
from socialdna.storage.schema import metadata

PROJECTION = "declared-relations-v1"
# These are structural provenance relations, not evidence of a mechanism/effect.
RELATIONS = {
    "declared_reference",
    "cites",
    "media_context",
    "post_context",
    "measured_subject",
    "definition",
}


def project_relations(connection: Connection, document: dict[str, Any]) -> None:
    repository = EvidenceRepository(connection)
    nodes, edges = (metadata.tables[name] for name in ("graph_nodes", "graph_edges"))
    owner = document["owner"]

    def node(ref: EntityRef) -> None:
        if ref.kind not in AUTHORED_KINDS | set(LEGACY_KINDS):
            raise ConfigurationError("Graph endpoint kind is not registered")
        repository.entity(ref)
        connection.execute(
            insert(nodes)
            .values(revision_id=ref.revision_id, kind=ref.kind, entity_id=ref.id)
            .on_conflict_do_nothing()
        )

    node(owner)
    primary = document["citations"][0].revision_id if document["citations"] else None
    for root, value in (("payload", document["payload"]), ("locator", document["locator"])):
        for path, ref in references(value):
            relation = "declared_reference"
            citation = primary
            if isinstance(ref, EvidenceRef):
                row = repository.get("evidence_revisions", ref.revision_id)
                if row["evidence_id"] != ref.id:
                    raise ConfigurationError("Graph citation identity mismatch")
                ref_entity = repository.ref(
                    repository.get("entity_revisions", row["subject_revision_id"])
                )
                relation, citation = "cites", ref.revision_id
            else:
                ref_entity = ref
                relation = {
                    "/media": "media_context",
                    "/post": "post_context",
                    "/measured_subject": "measured_subject",
                    "/definition": "definition",
                }.get(path, "declared_reference")
            if ref_entity == owner:
                continue
            node(ref_entity)
            assert relation in RELATIONS
            identity = stable_id(
                "memory-edge",
                owner.revision_id,
                ref_entity.revision_id,
                root + path,
                citation or "",
                PROJECTION,
            )
            connection.execute(
                insert(edges)
                .values(
                    id=identity,
                    source_revision_id=owner.revision_id,
                    target_revision_id=ref_entity.revision_id,
                    owner_revision_id=owner.revision_id,
                    evidence_revision_id=citation,
                    relation=relation,
                    qualification_json=canonical_json(
                        {
                            "field": root + path,
                            "claim_level": document["claim_level"],
                            "scope_revision_id": owner.revision_id,
                            "interpretation": "declared reference; not causation or association",
                        }
                    ),
                    projection_version=PROJECTION,
                )
                .on_conflict_do_nothing()
            )


def project_entity(connection: Connection, identity: str) -> None:
    """Project registered canonical producers even when they have no searchable text."""
    repository = EvidenceRepository(connection)
    row = repository.get("entity_revisions", identity)
    owner = repository.ref(row)
    if owner.kind in {"frame", "scene", "observation", "text_segment", "audio_segment", "ocr_box"}:
        return  # Fine-grained nodes are materialized only for actual cited relations.
    try:
        entity_active(connection, owner)
    except ConfigurationError:
        return
    payload = json.loads(row["payload_json"])
    # Pin a post's account FK to the account revision captured at that time,
    # never today's edited row; the edge qualification names this context join.
    if owner.kind == "post" and payload.get("account_id"):
        entities = metadata.tables["entity_revisions"]
        account = (
            connection.execute(
                select(entities)
                .where(
                    entities.c.kind == "account",
                    entities.c.entity_id == payload["account_id"],
                    entities.c.recorded_at <= row["recorded_at"],
                )
                .order_by(entities.c.revision_no.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if account:
            payload = {
                **payload,
                "captured_account_context": repository.ref(dict(account)).model_dump(),
            }
    project_relations(
        connection,
        {
            "owner": owner,
            "payload": payload,
            "locator": {},
            "citations": [],
            "claim_level": payload.get(
                "claim_level", "hypothesis" if owner.kind == "hypothesis" else "observation"
            ),
        },
    )


def neighborhood(
    connection: Connection,
    root: str,
    *,
    depth: int = 2,
    max_nodes: int = 2000,
    max_edges: int = 4000,
    as_of: str | None = None,
    historical: bool = False,
) -> dict[str, Any]:
    import networkx as nx

    if not 0 <= depth <= 5 or not 1 <= max_nodes <= 2000 or not 1 <= max_edges <= 4000:
        raise ConfigurationError("Graph bounds: depth 0–5, nodes 1–2000, edges 1–4000")
    repository = EvidenceRepository(connection)
    row = repository.get("entity_revisions", root)
    graph = nx.MultiDiGraph()
    cache: dict[str, bool] = {}

    def eligible(identity: str) -> bool:
        if identity not in cache:
            ref = repository.ref(repository.get("entity_revisions", identity))
            try:
                entity_active(connection, ref, as_of=as_of)
                cache[identity] = True
            except ConfigurationError:
                cache[identity] = False
        return cache[identity]

    if not eligible(root) or (
        not historical and not current_revision(connection, repository.ref(row), as_of)
    ):
        return {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "reason": "root_not_eligible_in_selected_view",
        }
    graph.add_node(root, ref=repository.ref(row).model_dump())
    frontier = deque([(root, 0)])
    expanded = set()
    truncated = False
    table = metadata.tables["graph_edges"]
    scanned = 0
    while frontier:
        identity, distance = frontier.popleft()
        if identity in expanded or distance >= depth:
            continue
        expanded.add(identity)
        rows = connection.execute(
            select(table)
            .where(
                or_(table.c.source_revision_id == identity, table.c.target_revision_id == identity)
            )
            .order_by(table.c.id)
            .limit(max_edges + 1)
        ).mappings()
        for edge in rows:
            scanned += 1
            if scanned > max_edges:
                truncated = True
                break
            source, target = edge["source_revision_id"], edge["target_revision_id"]
            if not all(eligible(item) for item in (source, target, edge["owner_revision_id"])):
                continue
            owner = repository.ref(repository.get("entity_revisions", edge["owner_revision_id"]))
            if not historical and not current_revision(connection, owner, as_of):
                continue
            if edge["evidence_revision_id"]:
                from socialdna.application.evidence_service import EvidenceResolver

                citation = repository.get("evidence_revisions", edge["evidence_revision_id"])
                if (
                    not EvidenceResolver(connection)
                    .resolve(
                        EvidenceRef(id=citation["evidence_id"], revision_id=citation["id"]),
                        as_of=as_of,
                    )
                    .eligible
                ):
                    continue
            missing = [item for item in (source, target) if item not in graph]
            if graph.number_of_nodes() + len(missing) > max_nodes:
                truncated = True
                continue
            for item in missing:
                graph.add_node(
                    item, ref=repository.ref(repository.get("entity_revisions", item)).model_dump()
                )
                frontier.append((item, distance + 1))
            graph.add_edge(
                source,
                target,
                key=edge["id"],
                id=edge["id"],
                relation=edge["relation"],
                owner_revision_id=edge["owner_revision_id"],
                evidence_revision_id=edge["evidence_revision_id"],
                qualification=json.loads(edge["qualification_json"]),
            )
        if scanned > max_edges:
            break
    return {
        "nodes": [{"revision_id": key, **attributes} for key, attributes in graph.nodes(data=True)],
        "edges": [
            {"source": source, "target": target, **attributes}
            for source, target, attributes in graph.edges(data=True)
        ],
        "truncated": truncated,
        "depth": depth,
        "historical": historical,
        "interpretation": "Provenance paths are not causation or independent confirmation.",
    }


def path(connection: Connection, source: str, target: str, **bounds: Any) -> dict[str, Any]:
    import networkx as nx

    view = neighborhood(connection, source, **bounds)
    graph = nx.MultiDiGraph()
    graph.add_nodes_from(node["revision_id"] for node in view["nodes"])
    graph.add_edges_from((edge["source"], edge["target"]) for edge in view["edges"])
    try:
        route = nx.shortest_path(graph.to_undirected(), source, target)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        route = []
    return {
        **view,
        "path": route,
        "direction": "undirected structural neighborhood",
        "reason": None if route else "no_path_within_eligible_budgeted_view",
    }
