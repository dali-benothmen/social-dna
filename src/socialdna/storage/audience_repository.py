"""Canonical audience documents with concrete, immutable FK projections."""

import json
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.audience.annotations import RUBRIC, RUBRIC_VERSION, AnnotationSet
from socialdna.audience.collections import CollectionSpec
from socialdna.audience.linking import ContentLink, parse_reference_time
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.creative import MediaAnchor
from socialdna.domain.evidence import AudienceLocator, EntityRef, EvidenceRef
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {
    "audience_collection": "audience_collections",
    "audience_annotation_set": "audience_annotation_sets",
    "reaction_annotation": "reaction_annotations",
    "reaction_cluster": "reaction_clusters",
    "content_reaction_link": "content_reaction_links",
    "audience_analysis": "audience_analyses",
}


def put(connection: Connection, table: str, **values: Any) -> None:
    connection.execute(insert(metadata.tables[table]).values(**values).on_conflict_do_nothing())


def entity_active(
    connection: Connection, ref: EntityRef, cutoff: str | None = None
) -> dict[str, Any]:
    from socialdna.application.evidence_service import assert_active_inputs
    from socialdna.storage.audience_retention import is_redacted

    repository = EvidenceRepository(connection)
    row = repository.entity(ref)
    if is_redacted(connection, "entity_revision", ref.revision_id):
        raise ConfigurationError("Audience input was erased")
    if not row["source_id"]:
        raise ConfigurationError("Audience input needs an authorized captured source")
    assert_active_inputs(connection, source_ids=(row["source_id"],))
    source = repository.get("source_records", row["source_id"])
    if not source["permission_basis"].strip() or (
        ref.kind == "comment"
        and source["source_kind"] == "tabular_export"
        and not json.loads(source["terms_json"]).get("comments_permitted")
    ):
        raise ConfigurationError("Source does not authorize audience reuse")
    if cutoff and (row["available_at"] is None or row["available_at"] > cutoff):
        raise ConfigurationError("Audience input availability is unknown or after the cutoff")
    payload: dict[str, Any] = json.loads(row["payload_json"])
    return payload


def register_rubric(connection: Connection) -> list[EntityRef]:
    from socialdna.application.evidence_service import assert_active_inputs

    source = stable_id("audience-rubric-source", RUBRIC_VERSION)
    provenance = stable_id("audience-rubric-provenance", RUBRIC_VERSION)
    assert_active_inputs(connection, source_ids=(source,))
    put(
        connection,
        "source_records",
        id=source,
        source_kind="engine_definition",
        source_uri="socialdna:" + RUBRIC_VERSION,
        permission_basis="Apache-2.0 engine rubric",
        terms_json="{}",
        retrieved_at=utc_now(),
    )
    put(
        connection,
        "provenance_records",
        id=provenance,
        source_record_id=source,
        method=RUBRIC_VERSION,
        tool_name="socialdna",
        tool_version=__version__,
        config_json="{}",
        created_at=utc_now(),
    )
    repository, refs = EvidenceRepository(connection), []
    for label, rules in RUBRIC.items():
        document = {
            "label": label,
            "version": RUBRIC_VERSION,
            **rules,
            "scope": "expressed text, not hidden mental state or verified behavior",
        }
        identity = stable_id("reaction-rubric", RUBRIC_VERSION, label)
        prior = repository.latest("reaction_rubric", identity)
        if prior and repository.entity(prior)["content_hash"] != hash_config(document):
            raise StorageIntegrityError("Reaction rubric changed without a new version")
        refs.append(
            prior
            or repository.save_entity(
                "reaction_rubric", identity, document, provenance, available_at=utc_now()
            )
        )
    return refs


def save(
    connection: Connection,
    kind: str,
    identity: str,
    payload: dict[str, Any],
    provenance: str,
    *,
    entity_inputs: list[EntityRef],
    evidence_inputs: list[EvidenceRef],
    **projection: Any,
) -> EntityRef:
    repository = EvidenceRepository(connection)
    document = {
        **payload,
        "entity_inputs": [r.model_dump() for r in entity_inputs],
        "evidence_inputs": [r.model_dump() for r in evidence_inputs],
    }
    prior = repository.latest(kind, identity)
    from socialdna.storage.audience_retention import is_redacted

    if prior and is_redacted(connection, "entity_revision", prior.revision_id):
        prior = None
    ref = (
        prior
        if prior and repository.entity(prior)["content_hash"] == hash_config(document)
        else repository.save_entity(kind, identity, document, provenance, available_at=utc_now())
    )
    put(connection, KINDS[kind], revision_id=ref.revision_id, **projection)
    for index, child in enumerate(
        [
            *(("entity_revision_id", r.revision_id) for r in entity_inputs),
            *(("evidence_revision_id", r.revision_id) for r in evidence_inputs),
        ]
    ):
        put(
            connection,
            "audience_dependencies",
            parent_revision_id=ref.revision_id,
            ordinal=index,
            **{child[0]: child[1]},
        )
    return ref


def cite(
    connection: Connection, ref: EntityRef, collection: EntityRef, *, run_id: str | None = None
) -> EvidenceRef:
    repository = EvidenceRepository(connection)
    row = repository.entity(ref)
    result = repository.save_evidence(
        stable_id("audience-evidence", ref.revision_id),
        AudienceLocator(subject=ref, collection=collection),
        row["provenance_id"],
        available_at=row["available_at"],
        run_id=run_id,
    )
    put(
        connection,
        "audience_evidence_bindings",
        evidence_revision_id=result.revision_id,
        subject_revision_id=ref.revision_id,
        collection_revision_id=collection.revision_id,
    )
    return result


def evidence_ref(connection: Connection, ref: EntityRef) -> EvidenceRef:
    table = metadata.tables["evidence_revisions"]
    rows = list(
        connection.execute(
            select(table.c.id, table.c.evidence_id).where(
                table.c.subject_revision_id == ref.revision_id,
                table.c.locator_kind == "audience_record",
            )
        ).mappings()
    )
    if len(rows) != 1:
        raise StorageIntegrityError("Audience revision needs exactly one canonical citation")
    return EvidenceRef(id=rows[0]["evidence_id"], revision_id=rows[0]["id"])


def persist_collection(
    connection: Connection, spec: CollectionSpec, provenance: str
) -> dict[str, Any]:
    repository = EvidenceRepository(connection)
    if spec.collected_at > utc_now():
        raise ConfigurationError("Collection time cannot be in the future")
    for post in spec.posts:
        entity_active(connection, post)
    for member in spec.members:
        comment = entity_active(connection, member.comment)
        if comment["post_id"] not in {p.id for p in spec.posts}:
            raise ConfigurationError("Comment does not belong to a declared collection post")
        if member.eligible and (
            comment["published_at"] > spec.collected_at
            or (spec.requested_start and comment["published_at"] < spec.requested_start)
            or (spec.requested_end and comment["published_at"] >= spec.requested_end)
        ):
            raise ConfigurationError("Eligible comment is outside the declared collection period")
    ref = save(
        connection,
        "audience_collection",
        stable_id("audience-collection", spec.key),
        {"spec": spec.model_dump(mode="json")},
        provenance,
        entity_inputs=[*spec.posts, *(m.comment for m in spec.members)],
        evidence_inputs=[],
        key=spec.key,
        available_at=utc_now(),
    )
    for index, member in enumerate(spec.members):
        put(
            connection,
            "audience_collection_members",
            collection_revision_id=ref.revision_id,
            ordinal=index,
            comment_revision_id=member.comment.revision_id,
            **member.model_dump(exclude={"comment"}),
        )
    citation = cite(connection, ref, ref)
    return {
        "ref": ref.model_dump(),
        "evidence": citation.model_dump(),
        "member_count": len(spec.members),
        "available_at": repository.entity(ref)["available_at"],
    }


def _link_inputs(
    connection: Connection, link: ContentLink, reaction: dict[str, Any], collection: dict[str, Any]
) -> tuple[list[EntityRef], list[EvidenceRef], int | None]:
    from socialdna.application.evidence_service import EvidenceResolver

    repository = EvidenceRepository(connection)
    comment = entity_active(connection, EntityRef.model_validate(reaction["annotation"]["comment"]))
    post_id = comment["post_id"]
    target = entity_active(connection, link.target)
    entities, evidence = [link.target], []
    if link.target.kind == "post":
        if link.target.id != post_id:
            raise ConfigurationError("A reaction cannot link to an unrelated post")
    else:
        links = metadata.tables["post_media"]
        if not connection.scalar(
            select(links.c.post_id).where(
                links.c.post_id == post_id, links.c.media_asset_id == target["media"]["id"]
            )
        ):
            raise ConfigurationError("Creative target does not belong to the comment's post")
    if post_id not in {p["id"] for p in collection["spec"]["posts"]}:
        raise ConfigurationError("Link lies outside this collection")
    resolved_target = None
    if link.target_evidence:
        resolved_target = EvidenceResolver(connection).resolve(
            link.target_evidence,
            purpose="new_claim",
            expected_subject=link.target if link.target.kind == "creative_event" else None,
            post_id=post_id if link.target.kind == "post" else None,
        )
        evidence.append(link.target_evidence)
    playback = None
    if link.origin == "explicit_reference":
        assert link.reference_text is not None
        if link.reference_text not in reaction["annotation"]["quote"]:
            raise ConfigurationError("Explicit reference text is not in the cited reaction span")
        if link.reference_kind == "timestamp":
            playback = parse_reference_time(link.reference_text)
            if link.target.kind == "creative_event":
                if not any(
                    (b := MediaAnchor.model_validate(a).bounds()) is not None
                    and b[0] <= playback
                    and (playback <= b[3] if a["kind"] in ("point", "spatial") else playback < b[3])
                    for a in target["annotation"]["anchors"]
                ):
                    raise ConfigurationError(
                        "Explicit playback reference is outside the target's possible anchors"
                    )
            else:
                from socialdna.domain.evidence import MediaLocator

                if not resolved_target or not isinstance(resolved_target.locator, MediaLocator):
                    raise ConfigurationError(
                        "Post playback references require actual media evidence"
                    )
                asset = repository.get("media_assets", resolved_target.locator.media.id)
                if playback >= asset["duration_ms"]:
                    raise ConfigurationError(
                        "Explicit playback reference exceeds the video duration"
                    )
        else:
            assert link.target_quote_evidence is not None
            target_text = EvidenceResolver(connection).resolve(
                link.target_quote_evidence, purpose="new_claim", post_id=post_id
            )
            from socialdna.domain.evidence import PostTextLocator

            if (
                link.target.kind == "post"
                and isinstance(target_text.locator, PostTextLocator)
                and target_text.subject != link.target
            ):
                raise ConfigurationError(
                    "Quoted post text must cite the exact target post revision"
                )
            if (
                link.target.kind == "creative_event"
                and link.target_quote_evidence.model_dump()
                not in [item["ref"] for item in target["inputs"]]
            ):
                raise ConfigurationError(
                    "Explicit event quotes require the event's literal input evidence"
                )
            literal = getattr(target_text.locator, "quote", None) or getattr(
                target_text.locator, "excerpt", None
            )
            if not literal or link.reference_text not in literal:
                raise ConfigurationError("Explicit quote is not supported by literal target text")
            evidence.append(link.target_quote_evidence)
    for alternative in link.alternatives:
        candidate = entity_active(connection, alternative.target)
        if alternative.target.kind not in ("post", "creative_event"):
            raise ConfigurationError("Alternative links need exact content targets")
        if alternative.target.kind == "post" and alternative.target.id != post_id:
            raise ConfigurationError("Alternative target lies outside the comment's post")
        if alternative.target.kind == "creative_event":
            media_links = metadata.tables["post_media"]
            if not connection.scalar(
                select(media_links.c.post_id).where(
                    media_links.c.post_id == post_id,
                    media_links.c.media_asset_id == candidate["media"]["id"],
                )
            ):
                raise ConfigurationError("Alternative event lies outside the comment's post")
        entities.append(alternative.target)
    return entities, evidence, playback


def persist_annotations(
    connection: Connection, spec: AnnotationSet, provenance: str
) -> dict[str, Any]:
    from socialdna.application.evidence_service import EvidenceResolver

    repository = EvidenceRepository(connection)
    collection = entity_active(connection, spec.collection)
    EvidenceResolver(connection).resolve(
        evidence_ref(connection, spec.collection), purpose="new_claim"
    )
    members = {m["comment"]["revision_id"] for m in collection["spec"]["members"]}
    rubrics = register_rubric(connection)
    reactions, clusters, links = {}, [], []
    for annotation in spec.annotations:
        if annotation.comment.revision_id not in members:
            raise ConfigurationError(
                "Reaction does not refer to a member of this collection revision"
            )
        comment = entity_active(connection, annotation.comment)
        if (
            annotation.end_char > len(comment["body"])
            or comment["body"][annotation.start_char : annotation.end_char] != annotation.quote
        ):
            raise ConfigurationError(
                "Reaction quote does not match the captured original Unicode span"
            )
        if annotation.complete_rubric_review and (
            annotation.start_char != 0 or annotation.end_char != len(comment["body"])
        ):
            raise ConfigurationError("Complete rubric review must cite the entire comment")
        span = repository.comment_evidence(
            annotation.comment.id,
            annotation.start_char,
            annotation.end_char,
            revision_id=annotation.comment.revision_id,
        )
        EvidenceResolver(connection).resolve(span, purpose="new_claim")
        ref = save(
            connection,
            "reaction_annotation",
            stable_id("reaction", spec.collection.id, spec.key, annotation.key),
            {
                "collection": spec.collection.model_dump(),
                "annotation": annotation.model_dump(mode="json"),
                "protocol": spec.protocol.model_dump(mode="json"),
            },
            provenance,
            entity_inputs=[annotation.comment, *rubrics],
            evidence_inputs=[span],
            collection_revision_id=spec.collection.revision_id,
            comment_revision_id=annotation.comment.revision_id,
            span_evidence_revision_id=span.revision_id,
            state=annotation.state,
        )
        reactions[annotation.key] = {
            "ref": ref.model_dump(),
            "evidence": cite(connection, ref, spec.collection).model_dump(),
            **json.loads(repository.entity(ref)["payload_json"]),
        }
    for cluster in spec.clusters:
        refs = [EntityRef.model_validate(reactions[m.reaction_key]["ref"]) for m in cluster.members]
        refs_evidence = [
            EvidenceRef.model_validate(reactions[m.reaction_key]["evidence"])
            for m in cluster.members
        ]
        ref = save(
            connection,
            "reaction_cluster",
            stable_id("reaction-cluster", spec.collection.id, spec.key, cluster.key),
            {
                "collection": spec.collection.model_dump(),
                "cluster": cluster.model_dump(mode="json"),
                "protocol": spec.protocol.model_dump(mode="json"),
                "members": [
                    {"reaction": r.model_dump(), "role": m.role}
                    for r, m in zip(refs, cluster.members, strict=True)
                ],
            },
            provenance,
            entity_inputs=refs,
            evidence_inputs=refs_evidence,
            collection_revision_id=spec.collection.revision_id,
            state=cluster.state,
        )
        for child, member in zip(refs, cluster.members, strict=True):
            put(
                connection,
                "reaction_cluster_members",
                cluster_revision_id=ref.revision_id,
                reaction_revision_id=child.revision_id,
                role=member.role,
            )
        clusters.append(
            {
                "ref": ref.model_dump(),
                "evidence": cite(connection, ref, spec.collection).model_dump(),
            }
        )
    for link in spec.links:
        reaction = reactions[link.reaction_key]
        entities, inputs, playback = _link_inputs(connection, link, reaction, collection)
        reaction_ref = EntityRef.model_validate(reaction["ref"])
        target_payload = entity_active(connection, link.target)
        context: dict[str, Any] = {"ref": link.target.model_dump()}
        if link.target.kind == "creative_event":
            context.update(
                {
                    "media_id": target_payload["media"]["id"],
                    **{
                        key: target_payload["annotation"][key]
                        for key in ("description", "technique", "anchors", "modalities", "state")
                    },
                }
            )
        else:
            context.update(
                {"title": target_payload.get("title"), "caption": target_payload.get("caption")}
            )
        ref = save(
            connection,
            "content_reaction_link",
            stable_id("content-reaction-link", spec.collection.id, spec.key, link.key),
            {
                "collection": spec.collection.model_dump(),
                "link": link.model_dump(mode="json"),
                "reaction": reaction_ref.model_dump(),
                "playback_reference_ms": playback,
                "target_context": context,
                "protocol": spec.protocol.model_dump(mode="json"),
                "claim_scope": "qualified content reference/interpretation; "
                "not a causal or behavioral observation",
            },
            provenance,
            entity_inputs=[reaction_ref, *entities],
            evidence_inputs=[EvidenceRef.model_validate(reaction["evidence"]), *inputs],
            collection_revision_id=spec.collection.revision_id,
            reaction_revision_id=reaction_ref.revision_id,
            target_revision_id=link.target.revision_id,
            origin=link.origin,
            state=link.state,
            playback_reference_ms=playback,
        )
        links.append(
            {
                "ref": ref.model_dump(),
                "evidence": cite(connection, ref, spec.collection).model_dump(),
            }
        )
    all_items = [*reactions.values(), *clusters, *links]
    ref = save(
        connection,
        "audience_annotation_set",
        stable_id("audience-set", spec.collection.id, spec.key),
        {"collection": spec.collection.model_dump(), "spec": spec.model_dump(mode="json")},
        provenance,
        entity_inputs=[spec.collection],
        evidence_inputs=[
            evidence_ref(connection, spec.collection),
            *(EvidenceRef.model_validate(i["evidence"]) for i in all_items),
        ],
        collection_revision_id=spec.collection.revision_id,
        key=spec.key,
    )
    for plural, items in (
        ("reactions", list(reactions.values())),
        ("clusters", clusters),
        ("links", links),
    ):
        for index, item in enumerate(items):
            put(
                connection,
                "audience_set_" + plural,
                set_revision_id=ref.revision_id,
                member_revision_id=item["ref"]["revision_id"],
                ordinal=index,
            )
    return {
        "ref": ref.model_dump(),
        "evidence": cite(connection, ref, spec.collection).model_dump(),
        "reactions": list(reactions.values()),
        "clusters": clusters,
        "links": links,
    }


def validate_projection(
    repository: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]
) -> None:
    row = repository.get(KINDS[ref.kind], ref.revision_id, "revision_id")
    if ref.kind == "audience_collection":
        valid = row["key"] == payload["spec"]["key"]
        table = metadata.tables["audience_collection_members"]
        actual = list(
            repository.connection.execute(
                select(table)
                .where(table.c.collection_revision_id == ref.revision_id)
                .order_by(table.c.ordinal)
            ).mappings()
        )
        valid = valid and [
            (
                r["comment_revision_id"],
                r["eligible"],
                r["language"],
                r["creator_authored"],
                r["exclusion_reason"],
            )
            for r in actual
        ] == [
            (
                m["comment"]["revision_id"],
                m["eligible"],
                m["language"],
                m["creator_authored"],
                m["exclusion_reason"],
            )
            for m in payload["spec"]["members"]
        ]
    else:
        valid = row["collection_revision_id"] == payload["collection"]["revision_id"]
        if ref.kind == "reaction_annotation":
            valid = (
                valid
                and row["comment_revision_id"] == payload["annotation"]["comment"]["revision_id"]
                and row["state"] == payload["annotation"]["state"]
                and row["span_evidence_revision_id"] == payload["evidence_inputs"][0]["revision_id"]
            )
        elif ref.kind == "content_reaction_link":
            valid = (
                valid
                and row["reaction_revision_id"] == payload["reaction"]["revision_id"]
                and row["target_revision_id"] == payload["link"]["target"]["revision_id"]
                and row["origin"] == payload["link"]["origin"]
                and row["state"] == payload["link"]["state"]
                and row["playback_reference_ms"] == payload["playback_reference_ms"]
            )
        elif ref.kind == "reaction_cluster":
            members = metadata.tables["reaction_cluster_members"]
            actual_members = {
                (r[0], r[1])
                for r in repository.connection.execute(
                    select(members.c.reaction_revision_id, members.c.role).where(
                        members.c.cluster_revision_id == ref.revision_id
                    )
                )
            }
            valid = (
                valid
                and row["state"] == payload["cluster"]["state"]
                and actual_members
                == {(m["reaction"]["revision_id"], m["role"]) for m in payload["members"]}
            )
        elif ref.kind == "audience_annotation_set":
            valid = valid and row["key"] == payload["spec"]["key"]
            for plural, field in (
                ("reactions", "annotations"),
                ("clusters", "clusters"),
                ("links", "links"),
            ):
                table = metadata.tables["audience_set_" + plural]
                children: list[str] = list(
                    repository.connection.scalars(
                        select(table.c.member_revision_id)
                        .where(table.c.set_revision_id == ref.revision_id)
                        .order_by(table.c.ordinal)
                    )
                )
                name = {"reactions": "annotation", "clusters": "cluster", "links": "link"}[plural]
                captured = [
                    json.loads(repository.get("entity_revisions", child)["payload_json"])[name]
                    for child in children
                ]
                valid = valid and captured == payload["spec"][field]
        elif ref.kind == "audience_analysis":
            valid = (
                valid
                and row["run_id"] == payload["report"]["run_id"]
                and row["fingerprint"] == payload["fingerprint"]
            )
    deps = metadata.tables["audience_dependencies"]
    actual_deps = list(
        repository.connection.execute(
            select(deps.c.entity_revision_id, deps.c.evidence_revision_id)
            .where(deps.c.parent_revision_id == ref.revision_id)
            .order_by(deps.c.ordinal)
        )
    )
    expected = [
        *((r["revision_id"], None) for r in payload["entity_inputs"]),
        *((None, r["revision_id"]) for r in payload["evidence_inputs"]),
    ]
    if not valid or actual_deps != expected:
        raise StorageIntegrityError(
            "Audience document disagrees with its typed projection/dependencies"
        )
