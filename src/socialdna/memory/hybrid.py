"""Bounded ranked retrieval; candidates never define a statistical population."""

from typing import TYPE_CHECKING, Any

from qdrant_client import models
from sqlalchemy import select

from socialdna.core.exceptions import DependencyUnavailable, SocialDNAError
from socialdna.domain.memory import QuerySpec
from socialdna.memory.documents import hydrate
from socialdna.memory.lexical import candidates
from socialdna.memory.vector_sync import Embedder, collection, load_space, vectors_checked
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

if TYPE_CHECKING:
    from socialdna.application.bootstrap import Application


def semantic_candidates(
    application: "Application",
    spec: QuerySpec,
    provider: Embedder | None = None,
) -> tuple[list[str], bool]:
    if not spec.space_id:
        raise DependencyUnavailable(
            "Semantic retrieval needs an explicitly registered, prepared embedding space"
        )
    if spec.as_of or spec.revision_id:
        raise DependencyUnavailable(
            "Vector spaces index current documents only; use SQL/FTS for exact historical views"
        )
    documents, revisions, entities, entries = (
        metadata.tables[name]
        for name in (
            "vector_documents",
            "vector_document_revisions",
            "entity_revisions",
            "vector_index_entries",
        )
    )
    with application.database.transaction() as connection:
        space = load_space(connection, spec.space_id)
        statement = (
            select(documents.c.id, documents.c.family)
            .join(revisions, revisions.c.id == documents.c.desired_revision_id)
            .join(entities, entities.c.id == revisions.c.owner_revision_id)
            .where(documents.c.state == "ready")
        )
        for column, value in (
            (documents.c.family, spec.family),
            (documents.c.owner_kind, spec.owner_kind),
            (documents.c.owner_id, spec.owner_id),
            (entities.c.source_id, spec.source_id),
        ):
            if value is not None:
                statement = statement.where(column == value)
        rows = list(
            connection.execute(statement.order_by(documents.c.id).limit(spec.candidate_limit + 1))
        )
    budget = len(rows) > spec.candidate_limit
    families: dict[str, list[str]] = {}
    for row in rows[: spec.candidate_limit]:
        families.setdefault(row.family, []).append(row.id)
    if provider is None:
        from socialdna.providers.embeddings import LocalEmbedder

        provider = LocalEmbedder(application.settings, space)
    query = vectors_checked(provider.encode([spec.text], query=True), space, 1)[0]
    points = []
    for family, identities in families.items():
        name = collection(family, space.id)
        client = application.vectors.client
        if not client.collection_exists(name):
            continue
        points.extend(
            client.query_points(
                name,
                query=query,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchAny(any=identities)
                        ),
                        models.FieldCondition(
                            key="space_id", match=models.MatchValue(value=space.id)
                        ),
                    ]
                ),
                limit=spec.candidate_limit,
                with_payload=True,
            ).points
        )
    results = []
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        for point in sorted(points, key=lambda item: (-item.score, str(item.id))):
            payload = point.payload or {}
            entry = (
                connection.execute(
                    select(entries).where(
                        entries.c.point_id == str(point.id), entries.c.space_id == space.id
                    )
                )
                .mappings()
                .first()
            )
            if (
                entry is None
                or any(
                    payload.get(key) != value
                    for key, value in (
                        ("document_id", entry["document_id"]),
                        ("revision_id", entry["desired_revision_id"]),
                        ("generation", entry["generation"]),
                        ("space_id", space.id),
                    )
                )
                or entry["desired_revision_id"] is None
            ):
                continue
            revision = repository.get("vector_document_revisions", entry["desired_revision_id"])
            if payload.get("content_hash") != revision["content_hash"]:
                continue
            if hydrate(connection, revision) is not None:
                results.append(revision["id"])
    return results[: spec.candidate_limit], budget or len(results) > spec.candidate_limit


def search(
    application: "Application", spec: QuerySpec, *, provider: Embedder | None = None
) -> dict[str, Any]:
    rankings: list[list[str]] = []
    limitations = [
        "Discovery candidates only: rank is not truth, confidence, an effect or a sampling frame."
    ]
    truncated = False
    semantic_state = "not_requested"
    if spec.mode in ("fts", "sql", "hybrid"):
        with application.database.transaction() as connection:
            lexical, budget = candidates(connection, spec)
        rankings.append(lexical)
        truncated |= budget
    if spec.mode in ("semantic", "hybrid"):
        try:
            semantic, budget = semantic_candidates(application, spec, provider)
            rankings.append(semantic)
            truncated |= budget
            semantic_state = "available"
        except SocialDNAError as exc:
            semantic_state = "unavailable"
            limitations.append(str(exc))
        except (OSError, ValueError, RuntimeError):
            semantic_state = "unavailable"
            limitations.append(
                "Derived semantic index unavailable; inspect storage and reconcile --repair."
            )
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, identity in enumerate(ranking, 1):
            scores[identity] = scores.get(identity, 0.0) + 1 / (60 + rank)
    hits = []
    seen = set()
    duplicates = 0
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        for identity in sorted(scores, key=lambda item: (-scores[item], item)):
            revision = repository.get("vector_document_revisions", identity)
            hit = hydrate(connection, revision, as_of=spec.as_of, historical=bool(spec.revision_id))
            if not hit:
                continue
            owner = hit["owner"]["revision_id"]
            if owner in seen:
                duplicates += 1
                continue
            seen.add(owner)
            hit["retrieval_score"] = scores[identity]
            if spec.graph_depth:
                from socialdna.memory.graph import neighborhood

                hit["graph"] = neighborhood(
                    connection,
                    owner,
                    depth=spec.graph_depth,
                    max_nodes=100,
                    max_edges=200,
                    as_of=spec.as_of,
                    historical=bool(spec.revision_id),
                )
            hits.append(hit)
            if len(hits) >= spec.limit:
                break
    if truncated:
        limitations.append(
            "Candidate budget reached; results are bounded, not exhaustive eligible coverage."
        )
    return {
        "status": "partial" if semantic_state == "unavailable" or truncated else "success",
        "query": spec.model_dump(),
        "hits": hits,
        "semantic": semantic_state,
        "candidate_budget_reached": truncated,
        "duplicate_chunks_or_owners_removed": duplicates,
        "score_semantics": "reciprocal-rank fusion k=60; not a probability",
        "limitations": limitations,
    }
