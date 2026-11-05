"""Active-library erasure of derived text, relations and persistent vector bytes."""

import sqlite3
from typing import Any

from sqlalchemy import Connection, delete, or_, select

from socialdna.config.paths import DataPaths
from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.memory.vector_sync import collection, desire
from socialdna.storage.schema import metadata
from socialdna.storage.vectors import LocalVectorStore


def scrub(connection: Connection, items: dict[str, list[str]]) -> list[dict[str, Any]]:
    connection.exec_driver_sql(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(revision_id UNINDEXED, text)"
    )
    revisions = metadata.tables["vector_document_revisions"]
    bindings = metadata.tables["vector_document_evidence"]
    entities = items.get("entity_revision", [])
    evidence = items.get("evidence_revision", [])
    affected = list(
        connection.execute(
            select(revisions).where(
                or_(
                    revisions.c.owner_revision_id.in_(entities),
                    revisions.c.id.in_(
                        select(bindings.c.document_revision_id).where(
                            bindings.c.evidence_revision_id.in_(evidence)
                        )
                    ),
                )
            )
        ).mappings()
    )
    documents = metadata.tables["vector_documents"]
    entries = metadata.tables["vector_index_entries"]
    points: list[dict[str, Any]] = []
    for revision in affected:
        document = (
            connection.execute(select(documents).where(documents.c.id == revision["document_id"]))
            .mappings()
            .one()
        )
        points.extend(
            {**dict(row), "family": document["family"]}
            for row in connection.execute(
                select(entries).where(entries.c.document_id == revision["document_id"])
            ).mappings()
        )
        connection.exec_driver_sql("DELETE FROM memory_fts WHERE revision_id=?", (revision["id"],))
        connection.execute(
            revisions.update()
            .where(revisions.c.id == revision["id"])
            .values(
                text="[redacted]",
                content_hash=hash_config("[redacted]"),
                metadata_json='{"redacted":true}',
                redacted=True,
            )
        )
        connection.execute(
            documents.update().where(documents.c.id == document["id"]).values(state="erased")
        )
        desire(connection, document["id"], None, force=True)
    edges = metadata.tables["graph_edges"]
    connection.execute(
        delete(edges).where(
            or_(
                edges.c.owner_revision_id.in_(entities),
                edges.c.source_revision_id.in_(entities),
                edges.c.target_revision_id.in_(entities),
                edges.c.evidence_revision_id.in_(evidence),
            )
        )
    )
    nodes = metadata.tables["graph_nodes"]
    connection.execute(delete(nodes).where(nodes.c.revision_id.in_(entities)))
    # Ordinary FTS DELETE can leave recoverable old terms in unmerged segment
    # b-trees. Rebuild from the surviving FTS content while secure_delete is ON;
    # the journal's subsequent VACUUM/checkpoint removes the freed page bytes.
    # This also works on SQLite versions predating FTS5's secure-delete option.
    connection.exec_driver_sql("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')")
    return points


def purge_vectors(paths: DataPaths, points: list[dict[str, Any]]) -> None:
    if not points or not paths.vectors.exists():
        return
    # Startup / redaction callers close their application client before entering.
    with LocalVectorStore(paths.vectors) as store:
        for point in points:
            name = collection(point["family"], point["space_id"])
            if store.client.collection_exists(name):
                store.client.delete(name, points_selector=[point["point_id"]], wait=True)
    # Qdrant Local 1.x persists points in these dedicated SQLite files. Closing
    # the client before secure vacuum also removes freed historical vector blobs.
    # No canonical files, arbitrary paths or unregistered user files are removed.
    for path in paths.vectors.glob("collection/*/storage.sqlite"):
        if not path.resolve().is_relative_to(paths.vectors.resolve()):
            raise StorageIntegrityError("Derived vector storage escaped the managed directory")
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA secure_delete=ON")
            connection.execute("VACUUM")
            if connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
                raise StorageIntegrityError(
                    "Vector erasure checkpoint is busy; erasure remains pending"
                )
