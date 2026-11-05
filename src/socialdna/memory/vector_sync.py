"""Idempotent Qdrant writes with SQLite generation guards and exact hydration."""

import math
from typing import TYPE_CHECKING, Any, Protocol

from qdrant_client import models
from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, ProviderFailure, StorageIntegrityError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.memory import EmbeddingSpace
from socialdna.memory.documents import hydrate
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

if TYPE_CHECKING:
    from socialdna.application.bootstrap import Application


class Embedder(Protocol):
    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


def vectors_checked(
    values: list[list[float]], space: EmbeddingSpace, count: int
) -> list[list[float]]:
    if len(values) != count:
        raise ProviderFailure("Embedding runtime returned the wrong batch size")
    for vector in values:
        if len(vector) != space.dimensions or any(
            type(value) not in (float, int) or not math.isfinite(value) for value in vector
        ):
            raise ProviderFailure("Embedding runtime returned incompatible or non-finite vectors")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, abs_tol=0.001):
            raise ProviderFailure("Embedding runtime did not return unit-normalized vectors")
    return values


def collection(family: str, space_id: str) -> str:
    return family + "_" + space_id.replace("-", "")


def register_space(connection: Connection, space: EmbeddingSpace) -> str:
    table = metadata.tables["embedding_spaces"]
    connection.execute(
        insert(table)
        .values(
            id=space.id,
            spec_json=canonical_json(space.model_dump(mode="json")),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    for row in connection.execute(
        select(
            metadata.tables["vector_documents"].c.id,
            metadata.tables["vector_documents"].c.desired_revision_id,
        ).where(metadata.tables["vector_documents"].c.state == "ready")
    ):
        desire(connection, row.id, row.desired_revision_id, space_id=space.id)
    return space.id


def load_space(connection: Connection, identity: str) -> EmbeddingSpace:
    row = EvidenceRepository(connection).get("embedding_spaces", identity)
    space = EmbeddingSpace.model_validate_json(row["spec_json"])
    if space.id != identity:
        raise StorageIntegrityError("Embedding space registry checksum mismatch")
    return space


def desire(
    connection: Connection,
    document_id: str,
    revision_id: str | None,
    *,
    space_id: str | None = None,
    force: bool = False,
) -> None:
    entries, outbox = (metadata.tables[name] for name in ("vector_index_entries", "vector_outbox"))
    spaces = (
        [space_id]
        if space_id
        else list(connection.scalars(select(metadata.tables["embedding_spaces"].c.id)))
    )
    for space in spaces:
        row = (
            connection.execute(
                select(entries).where(
                    entries.c.document_id == document_id, entries.c.space_id == space
                )
            )
            .mappings()
            .first()
        )
        if row and row["desired_revision_id"] == revision_id and not force:
            continue
        generation = row["generation"] + 1 if row else 1
        state = "pending" if revision_id else "delete_pending"
        values = {"desired_revision_id": revision_id, "generation": generation, "state": state}
        if row:
            connection.execute(
                entries.update()
                .where(entries.c.document_id == document_id, entries.c.space_id == space)
                .values(**values)
            )
        else:
            connection.execute(
                entries.insert().values(
                    document_id=document_id,
                    space_id=space,
                    point_id=stable_id("vector-point", document_id, space),
                    **values,
                )
            )
        digest = (
            EvidenceRepository(connection).get("vector_document_revisions", revision_id)[
                "content_hash"
            ]
            if revision_id
            else None
        )
        connection.execute(
            outbox.insert().values(
                document_id=document_id,
                space_id=space,
                operation="upsert" if revision_id else "delete",
                generation=generation,
                revision_id=revision_id,
                content_hash=digest,
                attempts=0,
                status="pending",
            )
        )


def _collection(application: "Application", family: str, space: EmbeddingSpace) -> str:
    client = application.vectors.client
    name = collection(family, space.id)
    if not client.collection_exists(name):
        client.create_collection(
            name,
            vectors_config=models.VectorParams(
                size=space.dimensions, distance=models.Distance.COSINE
            ),
        )
    config = client.get_collection(name).config.params.vectors
    if (
        not isinstance(config, models.VectorParams)
        or config.size != space.dimensions
        or config.distance != models.Distance.COSINE
    ):
        raise StorageIntegrityError(
            "Qdrant collection is incompatible with its immutable embedding space"
        )
    return name


def _entry(connection: Connection, job: dict[str, Any]) -> dict[str, Any]:
    table = metadata.tables["vector_index_entries"]
    return dict(
        connection.execute(
            select(table).where(
                table.c.document_id == job["document_id"], table.c.space_id == job["space_id"]
            )
        )
        .mappings()
        .one()
    )


def drain(
    application: "Application",
    space_id: str,
    *,
    provider: Embedder | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if not 1 <= limit <= 1000:
        raise ConfigurationError("Vector work limit must be 1–1000")
    outbox = metadata.tables["vector_outbox"]
    entries = metadata.tables["vector_index_entries"]
    with application.database.transaction() as connection:
        space = load_space(connection, space_id)
        jobs = [
            dict(row)
            for row in connection.execute(
                select(outbox)
                .where(outbox.c.space_id == space_id, outbox.c.status == "pending")
                .order_by((outbox.c.operation != "delete"), outbox.c.id)
                .limit(limit)
            ).mappings()
        ]
    completed = superseded = failed = 0
    failures: list[dict[str, Any]] = []
    encoded: dict[int, list[float]] = {}
    for ordinal, job in enumerate(jobs):
        try:
            with application.database.transaction() as connection:
                entry = _entry(connection, job)
                if (
                    entry["generation"] != job["generation"]
                    or entry["desired_revision_id"] != job["revision_id"]
                ):
                    connection.execute(
                        outbox.update().where(outbox.c.id == job["id"]).values(status="superseded")
                    )
                    superseded += 1
                    continue
                document = EvidenceRepository(connection).get(
                    "vector_documents", job["document_id"]
                )
                revision = (
                    EvidenceRepository(connection).get(
                        "vector_document_revisions", job["revision_id"]
                    )
                    if job["revision_id"]
                    else None
                )
                content = hydrate(connection, revision) if revision else None
                if revision and (
                    content is None or revision["content_hash"] != job["content_hash"]
                ):
                    desire(connection, job["document_id"], None)
                    connection.execute(
                        outbox.update().where(outbox.c.id == job["id"]).values(status="superseded")
                    )
                    superseded += 1
                    continue
                connection.execute(
                    outbox.update()
                    .where(outbox.c.id == job["id"])
                    .values(attempts=outbox.c.attempts + 1)
                )
            # No SQL transaction spans native inference or Qdrant I/O. The data
            # directory lock serializes all workers; there are no expiring leases.
            if revision:
                if provider is None:
                    from socialdna.providers.embeddings import LocalEmbedder

                    provider = LocalEmbedder(application.settings, space)
                if job["id"] not in encoded:
                    # Amortize isolated model startup over bounded batches. Each
                    # job is still revalidated after inference and acknowledged
                    # independently; cached batch vectors are never durable facts.
                    batch: list[tuple[int, str]] = []
                    with application.database.transaction() as connection:
                        repository = EvidenceRepository(connection)
                        for candidate in jobs[ordinal : ordinal + 32]:
                            if candidate["operation"] != "upsert":
                                continue
                            current = _entry(connection, candidate)
                            if (
                                current["generation"] != candidate["generation"]
                                or current["desired_revision_id"] != candidate["revision_id"]
                            ):
                                continue
                            candidate_revision = repository.get(
                                "vector_document_revisions", candidate["revision_id"]
                            )
                            if (
                                candidate_revision["content_hash"] == candidate["content_hash"]
                                and hydrate(connection, candidate_revision) is not None
                            ):
                                batch.append((candidate["id"], candidate_revision["text"]))
                    if not batch:
                        continue  # Source changed since this job's initial gate.
                    values = vectors_checked(
                        provider.encode([text for _, text in batch]), space, len(batch)
                    )
                    encoded.update(
                        {
                            identity: value
                            for (identity, _), value in zip(batch, values, strict=True)
                        }
                    )
                if job["id"] not in encoded:
                    continue
                vector = encoded.pop(job["id"])
            # Re-check after inference, before a stale job can write.
            with application.database.transaction() as connection:
                entry = _entry(connection, job)
                if entry["generation"] != job["generation"] or (
                    revision and hydrate(connection, revision) is None
                ):
                    connection.execute(
                        outbox.update().where(outbox.c.id == job["id"]).values(status="superseded")
                    )
                    if entry["generation"] == job["generation"]:
                        desire(connection, job["document_id"], None)
                    superseded += 1
                    continue
            name = collection(document["family"], space_id)
            if revision:
                name = _collection(application, document["family"], space)
                application.vectors.client.upsert(
                    name,
                    points=[
                        models.PointStruct(
                            id=entry["point_id"],
                            vector=vector,
                            payload={
                                "document_id": job["document_id"],
                                "revision_id": revision["id"],
                                "space_id": space_id,
                                "generation": job["generation"],
                                "content_hash": job["content_hash"],
                                "owner_revision_id": revision["owner_revision_id"],
                                "owner": content["owner"] if content else None,
                                "evidence": [item["ref"] for item in content["citations"]]
                                if content
                                else [],
                                "claim_level": content["representation"]["claim_level"]
                                if content
                                else None,
                                "available_at": revision["available_at"],
                                "family": document["family"],
                                "representation": REPRESENTATION_VERSION,
                            },
                        )
                    ],
                    wait=True,
                )
            elif application.vectors.client.collection_exists(name):
                application.vectors.client.delete(
                    name, points_selector=[entry["point_id"]], wait=True
                )
            with application.database.transaction() as connection:
                updated = connection.execute(
                    entries.update()
                    .where(
                        entries.c.document_id == job["document_id"],
                        entries.c.space_id == space_id,
                        entries.c.generation == job["generation"],
                    )
                    .values(
                        indexed_revision_id=job["revision_id"],
                        indexed_generation=job["generation"],
                        state="ready" if revision else "deleted",
                    )
                )
                connection.execute(
                    outbox.update()
                    .where(outbox.c.id == job["id"])
                    .values(status="done" if updated.rowcount else "superseded", last_error=None)
                )
            completed += 1
        except Exception as exc:
            # Keep jobs pending, including an upsert that succeeded before an
            # acknowledgement failure. Do not persist source text in error logs.
            with application.database.transaction() as connection:
                connection.execute(
                    outbox.update()
                    .where(outbox.c.id == job["id"])
                    .values(last_error=type(exc).__name__)
                )
            failed += 1
            failures.append(
                {
                    "job_id": job["id"],
                    "error_type": type(exc).__name__,
                    "next_action": "Inspect models status / storage verify, then retry.",
                }
            )
            break
    with application.database.transaction() as connection:
        pending = (
            connection.scalar(
                select(func.count())
                .select_from(outbox)
                .where(outbox.c.space_id == space_id, outbox.c.status == "pending")
            )
            or 0
        )
    return {
        "space_id": space_id,
        "completed": completed,
        "superseded": superseded,
        "failed": failed,
        "pending": pending,
        "failures": failures,
    }


REPRESENTATION_VERSION = "citation-text-v1"


def repair(application: "Application", space_id: str, *, limit: int = 1000) -> dict[str, Any]:
    """Detect absent/mismatched points, including after a canonical-only restore."""
    entries = metadata.tables["vector_index_entries"]
    repaired = 0
    state = metadata.tables["memory_projection_state"]
    cursor_key = "repair:" + space_id
    with application.database.transaction() as connection:
        load_space(connection, space_id)
        cursor = connection.scalar(select(state.c.value).where(state.c.key == cursor_key)) or ""
        rows = [
            dict(row)
            for row in connection.execute(
                select(entries)
                .where(
                    entries.c.space_id == space_id,
                    entries.c.state == "ready",
                    entries.c.document_id > cursor,
                )
                .order_by(entries.c.document_id)
                .limit(limit + 1)
            ).mappings()
        ]
    more = len(rows) > limit
    for row in rows[:limit]:
        with application.database.transaction() as connection:
            document = EvidenceRepository(connection).get("vector_documents", row["document_id"])
            revision = EvidenceRepository(connection).get(
                "vector_document_revisions", row["desired_revision_id"]
            )
        name = collection(document["family"], space_id)
        client = application.vectors.client
        points = client.retrieve(name, [row["point_id"]]) if client.collection_exists(name) else []
        if (
            not points
            or not points[0].payload
            or any(
                points[0].payload.get(key) != value
                for key, value in (
                    ("revision_id", row["desired_revision_id"]),
                    ("generation", row["generation"]),
                    ("space_id", space_id),
                    ("document_id", row["document_id"]),
                    ("content_hash", revision["content_hash"]),
                    ("owner_revision_id", revision["owner_revision_id"]),
                )
            )
        ):
            with application.database.transaction() as connection:
                desire(
                    connection,
                    row["document_id"],
                    row["desired_revision_id"],
                    space_id=space_id,
                    force=True,
                )
            repaired += 1
    with application.database.transaction() as connection:
        next_cursor = rows[limit - 1]["document_id"] if more else ""
        connection.execute(
            insert(state)
            .values(key=cursor_key, value=next_cursor)
            .on_conflict_do_update(
                index_elements=[state.c.key],
                set_={"value": next_cursor},
            )
        )
    return {"checked": min(len(rows), limit), "requeued": repaired, "scan_limit_reached": more}
