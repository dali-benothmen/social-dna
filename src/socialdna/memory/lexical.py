"""Incremental SQL/FTS projection, transactionally paired with vector desires."""

import re
from typing import Any

from sqlalchemy import Connection, delete, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.memory import QuerySpec
from socialdna.memory.documents import CHUNK_SIZE, REPRESENTATION, build, hydrate
from socialdna.storage.schema import metadata


def project(connection: Connection, document: dict[str, Any]) -> int:
    from socialdna.memory.graph import project_relations
    from socialdna.memory.vector_sync import desire

    documents = metadata.tables["vector_documents"]
    revisions = metadata.tables["vector_document_revisions"]
    bindings = metadata.tables["vector_document_evidence"]
    owner = document["owner"]
    text = document["text"]
    count = 0
    for ordinal, start in enumerate(range(0, len(text), CHUNK_SIZE)):
        chunk = text[start : start + CHUNK_SIZE]
        key = document["key"] + ":" + str(ordinal)
        identity = stable_id("memory-document", key, REPRESENTATION)
        citation_ids = sorted({ref.revision_id for ref in document["citations"]})
        revision = stable_id(
            "memory-revision",
            identity,
            owner.revision_id,
            hash_config(chunk),
            hash_config(citation_ids),
        )
        if connection.scalar(select(revisions.c.redacted).where(revisions.c.id == revision)):
            continue  # A terminal erased representation never becomes a rebuild input.
        connection.execute(
            insert(documents)
            .values(
                id=identity,
                owner_kind=owner.kind,
                owner_id=owner.id,
                representation_key=key,
                family=document["family"],
                state="pending",
            )
            .on_conflict_do_nothing()
        )
        representation = {
            "version": REPRESENTATION,
            "chunk_policy": "unicode-800-no-overlap-v1",
            "chunk": ordinal,
            "representation_start_char": start,
            "representation_end_char": start + len(chunk),
            "claim_level": document["claim_level"],
            "family": document["family"],
            "locator_kind": document["locator"].get("kind"),
            "scope": "exact canonical owner and citations; no inferred mechanism or effect",
        }
        connection.execute(
            insert(revisions)
            .values(
                id=revision,
                document_id=identity,
                owner_revision_id=owner.revision_id,
                evidence_revision_id=citation_ids[0] if len(citation_ids) == 1 else None,
                text=chunk,
                content_hash=hash_config(chunk),
                metadata_json=canonical_json(representation),
                created_at=utc_now(),
                available_at=document["available_at"],
                redacted=False,
            )
            .on_conflict_do_update(
                index_elements=[revisions.c.id],
                set_={
                    "text": chunk,
                    "content_hash": hash_config(chunk),
                    "metadata_json": canonical_json(representation),
                },
            )
        )
        for citation in citation_ids:
            connection.execute(
                insert(bindings)
                .values(
                    document_revision_id=revision,
                    evidence_revision_id=citation,
                    role="context",
                )
                .on_conflict_do_nothing()
            )
        connection.exec_driver_sql("DELETE FROM memory_fts WHERE revision_id=?", (revision,))
        connection.exec_driver_sql(
            "INSERT INTO memory_fts(revision_id,text) VALUES (?,?)", (revision, chunk)
        )
        # Replayed history must not roll the current pointer back to an old owner.
        prior = connection.scalar(
            select(documents.c.desired_revision_id).where(documents.c.id == identity)
        )
        if prior and prior != revision:
            entities = metadata.tables["entity_revisions"]
            previous_owner = connection.scalar(
                select(revisions.c.owner_revision_id).where(revisions.c.id == prior)
            )
            numbers: dict[str, int] = dict(
                connection.execute(
                    select(entities.c.id, entities.c.revision_no).where(
                        entities.c.id.in_([previous_owner, owner.revision_id])
                    )
                ).all()
            )
            if previous_owner and numbers.get(previous_owner, 0) > numbers.get(
                owner.revision_id, 0
            ):
                continue
        connection.execute(
            documents.update()
            .where(documents.c.id == identity)
            .values(
                desired_revision_id=revision,
                state="ready",
            )
        )
        desire(connection, identity, revision)
        count += 1
    project_relations(connection, document)
    return count


def reconcile(
    connection: Connection, *, limit: int = 1000, rebuild: bool = False
) -> dict[str, Any]:
    from socialdna.memory.vector_sync import desire

    changes = metadata.tables["memory_changes"]
    if rebuild:
        # The queue is the durable rebuild manifest. Clearing derived projections
        # and enqueuing their canonical inputs is one atomic transaction. A bounded
        # partial rebuild is explicitly labeled until subsequent reconciles drain it.
        connection.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(revision_id UNINDEXED, text)"
        )
        connection.exec_driver_sql("DELETE FROM memory_fts")
        connection.execute(delete(metadata.tables["graph_edges"]))
        connection.execute(delete(metadata.tables["graph_nodes"]))
        for table, kind in (("entity_revisions", "entity"), ("evidence_revisions", "evidence")):
            connection.exec_driver_sql(
                f"INSERT INTO memory_changes(kind,target_id) SELECT '{kind}',id FROM {table}"
            )
    jobs = list(connection.execute(select(changes).order_by(changes.c.seq).limit(limit)).mappings())
    projected = 0
    for job in jobs:
        if job["kind"] in ("entity", "evidence"):
            if job["kind"] == "entity":
                from socialdna.memory.graph import project_entity

                project_entity(connection, job["target_id"])
            document = build(connection, job["kind"], job["target_id"])
            if document:
                projected += project(connection, document)
        connection.execute(delete(changes).where(changes.c.seq == job["seq"]))
    # Includes transitive withdrawals/expiry and removed annotation memberships.
    # Bounded read-time hydration is still mandatory even with an empty journal.
    documents = metadata.tables["vector_documents"]
    revisions = metadata.tables["vector_document_revisions"]
    gated = 0
    state = metadata.tables["memory_projection_state"]
    cursor = (
        connection.scalar(select(state.c.value).where(state.c.key == "eligibility_cursor")) or ""
    )
    scan = (
        select(revisions)
        .join(documents, documents.c.desired_revision_id == revisions.c.id)
        .where(documents.c.state == "ready")
    )
    rows = list(
        connection.execute(
            scan.where(documents.c.id > cursor).order_by(documents.c.id).limit(limit + 1)
        ).mappings()
    )
    if not rows and cursor:
        rows = list(connection.execute(scan.order_by(documents.c.id).limit(limit + 1)).mappings())
    more = len(rows) > limit
    for raw in rows[:limit]:
        row = dict(raw)
        if hydrate(connection, row) is None:
            connection.execute(
                documents.update()
                .where(documents.c.id == row["document_id"])
                .values(state="ineligible")
            )
            if hydrate(connection, row, historical=True) is None:
                connection.exec_driver_sql(
                    "DELETE FROM memory_fts WHERE revision_id=?", (row["id"],)
                )
            desire(connection, row["document_id"], None)
            gated += 1
    next_cursor = rows[limit - 1]["document_id"] if more else ""
    connection.execute(
        insert(state)
        .values(key="eligibility_cursor", value=next_cursor)
        .on_conflict_do_update(
            index_elements=[state.c.key],
            set_={"value": next_cursor},
        )
    )
    return {
        "processed_changes": len(jobs),
        "projected_chunks": projected,
        "gated_documents": gated,
        "eligibility_sweep_truncated": more,
        "pending_changes": connection.scalar(select(func.count()).select_from(changes)) or 0,
    }


def candidates(connection: Connection, spec: QuerySpec) -> tuple[list[str], bool]:
    documents = metadata.tables["vector_documents"]
    revisions = metadata.tables["vector_document_revisions"]
    entities = metadata.tables["entity_revisions"]
    statement = (
        select(revisions.c.id)
        .join(documents, documents.c.id == revisions.c.document_id)
        .join(entities, entities.c.id == revisions.c.owner_revision_id)
        .where(revisions.c.redacted.is_(False))
    )
    for column, value in (
        (documents.c.family, spec.family),
        (documents.c.owner_kind, spec.owner_kind),
        (documents.c.owner_id, spec.owner_id),
        (entities.c.source_id, spec.source_id),
        (revisions.c.owner_revision_id, spec.revision_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if spec.as_of:
        statement = statement.where(
            revisions.c.available_at.is_not(None), revisions.c.available_at <= spec.as_of
        )
    if spec.mode == "sql":
        # SQL literal substring route is available independently of FTS semantics.
        statement = statement.where(revisions.c.text.contains(spec.text, autoescape=True)).order_by(
            revisions.c.id
        )
        rows = list(connection.scalars(statement.limit(spec.candidate_limit + 1)))
    else:
        tokens = re.findall(r"[^\W_]+", spec.text, flags=re.UNICODE)
        if not tokens:
            return [], False
        expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        # Scope filters precede the candidate budget, never after an unscoped top-K.
        compiled = statement.compile(connection, compile_kwargs={"literal_binds": True})
        rows = [
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT revision_id FROM memory_fts WHERE memory_fts MATCH ? "
                f"AND revision_id IN ({compiled}) ORDER BY bm25(memory_fts),revision_id LIMIT ?",
                (expression, spec.candidate_limit + 1),
            )
        ]
    return rows[: spec.candidate_limit], len(rows) > spec.candidate_limit
