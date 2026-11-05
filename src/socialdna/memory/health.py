"""Inspect derived memory without confusing projection lag with canonical data loss."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from socialdna.core.hashing import hash_config
from socialdna.domain.results import CheckResult
from socialdna.memory.graph import RELATIONS
from socialdna.memory.vector_sync import load_space
from socialdna.storage.schema import metadata

if TYPE_CHECKING:
    from socialdna.application.bootstrap import Application


def checks(application: "Application") -> list[CheckResult]:
    failed = []
    with application.database.transaction() as connection:
        revisions = metadata.tables["vector_document_revisions"]
        for row in connection.execute(select(revisions)).mappings():
            if hash_config(row["text"]) != row["content_hash"]:
                failed.append(row["id"])
        for row in connection.execute(select(metadata.tables["graph_edges"])).mappings():
            if (
                row["relation"] not in RELATIONS
                or row["source_revision_id"] != row["owner_revision_id"]
            ):
                failed.append(row["id"])
        mismatch: list[str] = list(
            connection.exec_driver_sql(
                "SELECT g.revision_id FROM graph_nodes g JOIN entity_revisions e "
                "ON g.revision_id=e.id WHERE g.kind!=e.kind OR g.entity_id!=e.entity_id"
            ).scalars()
        )
        failed.extend(mismatch)
        space_id: str
        for space_id in connection.scalars(select(metadata.tables["embedding_spaces"].c.id)):
            load_space(connection, space_id)
        for point in connection.exec_driver_sql(
            "SELECT e.point_id FROM vector_index_entries e JOIN vector_document_revisions r "
            "ON e.desired_revision_id=r.id WHERE e.document_id!=r.document_id"
        ):
            failed.append(point[0])
        fts_exists = (
            connection.exec_driver_sql(
                "SELECT 1 FROM sqlite_master WHERE name='memory_fts' AND type='table'"
            ).first()
            is not None
        )
        if fts_exists:
            for identity, text, canonical, redacted in connection.exec_driver_sql(
                "SELECT f.revision_id,f.text,r.text,r.redacted FROM memory_fts f "
                "LEFT JOIN vector_document_revisions r ON r.id=f.revision_id"
            ):
                if canonical is None or redacted or text != canonical:
                    failed.append(identity)
    return [
        CheckResult(
            name="memory.projections",
            status="warning" if failed or not fts_exists else "ok",
            message="Derived memory inspected; rebuild damaged projections with storage reindex.",
            details={
                "failed_ids": sorted(set(failed)),
                "fts_exists": fts_exists,
                "canonical_authority": "SQLite entities/evidence; projections are rebuildable",
            },
        )
    ]
