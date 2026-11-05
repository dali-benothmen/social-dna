"""Shared memory services, usable without a host agent or CLI."""

from typing import Any

from sqlalchemy import func, select

from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.memory import EmbeddingSpace, QuerySpec
from socialdna.memory import graph, hybrid, lexical, vector_sync
from socialdna.storage.schema import metadata


def status(application: Application) -> dict[str, Any]:
    with application.database.transaction() as connection:
        counts = {
            name: connection.scalar(select(func.count()).select_from(metadata.tables[name])) or 0
            for name in (
                "memory_changes",
                "vector_documents",
                "vector_document_revisions",
                "graph_nodes",
                "graph_edges",
            )
        }
        spaces = []
        for row in connection.execute(select(metadata.tables["embedding_spaces"])).mappings():
            entries = metadata.tables["vector_index_entries"]
            states: dict[str, int] = dict(
                connection.execute(
                    select(entries.c.state, func.count())
                    .where(entries.c.space_id == row["id"])
                    .group_by(entries.c.state)
                ).all()
            )
            spaces.append(
                {
                    "id": row["id"],
                    "specification": vector_sync.load_space(connection, row["id"]).model_dump(),
                    "entries": states,
                }
            )
    return {
        "counts": counts,
        "spaces": spaces,
        "fts": "available",
        "semantic": "not_configured"
        if not spaces
        else "prepared_runtime_required; see per-space lag",
        "graph": "sqlite-backed bounded NetworkX views",
        "pending_changes": counts["memory_changes"],
    }


def reconcile(
    application: Application,
    *,
    limit: int = 1000,
    rebuild: bool = False,
    space_id: str | None = None,
    vectors: bool = False,
    repair: bool = False,
) -> dict[str, Any]:
    if not 1 <= limit <= 5000:
        raise ConfigurationError("Memory change budget must be 1–5000")
    if (vectors or repair) and not space_id:
        raise ConfigurationError("Vector maintenance requires an explicit --space")
    with application.database.transaction() as connection:
        projection = lexical.reconcile(connection, limit=limit, rebuild=rebuild)
    result: dict[str, Any] = {"projection": projection}
    if space_id:
        with application.database.transaction() as connection:
            vector_sync.load_space(connection, space_id)
            if rebuild:
                table = metadata.tables["vector_index_entries"]
                for row in connection.execute(
                    select(table.c.document_id, table.c.desired_revision_id).where(
                        table.c.space_id == space_id
                    )
                ):
                    vector_sync.desire(
                        connection,
                        row.document_id,
                        row.desired_revision_id,
                        space_id=space_id,
                        force=True,
                    )
        if repair:
            result["repair"] = vector_sync.repair(application, space_id, limit=limit)
        if vectors:
            result["vectors"] = vector_sync.drain(application, space_id, limit=min(limit, 1000))
    result["status"] = (
        "partial"
        if projection["pending_changes"]
        or projection["eligibility_sweep_truncated"]
        or result.get("vectors", {}).get("pending")
        or result.get("repair", {}).get("scan_limit_reached")
        else "success"
    )
    result["memory"] = status(application)
    return result


def query(application: Application, spec: QuerySpec) -> dict[str, Any]:
    with application.database.transaction() as connection:
        progress = lexical.reconcile(connection, limit=1000)
    result = hybrid.search(application, spec)
    result["index"] = {**progress, "memory": status(application)}
    if progress["pending_changes"] or progress["eligibility_sweep_truncated"]:
        result["status"] = "partial"
        result["limitations"].append(
            "Projection or eligibility maintenance remains; run storage reconcile again."
        )
    return result


def graph_query(
    application: Application, root: str, *, target: str | None = None, **bounds: Any
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        progress = lexical.reconcile(connection, limit=1000)
        view = (
            graph.path(connection, root, target, **bounds)
            if target
            else graph.neighborhood(connection, root, **bounds)
        )
    return {
        "status": "partial"
        if progress["pending_changes"]
        or progress["eligibility_sweep_truncated"]
        or view["truncated"]
        else "success",
        "index": progress,
        **view,
    }


def register_embedding_space(application: Application, space: EmbeddingSpace) -> dict[str, Any]:
    from socialdna.providers.embeddings import LocalEmbedder

    LocalEmbedder(application.settings, space)  # Verify manifest/runtime; no inference or download.
    with application.database.transaction() as connection:
        lexical.reconcile(connection, limit=1000)
        identity = vector_sync.register_space(connection, space)
    return {
        "space_id": identity,
        "specification": space.model_dump(),
        "indexing": "pending; explicitly reconcile --vectors",
    }
