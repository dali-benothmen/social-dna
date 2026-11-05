"""Canonical creative revisions, typed projections and literal source citations."""

import json
from typing import Any, Literal

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.analyzers.creative import RECIPES, TECHNIQUES, temporal_relation
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import MediaInterval, utc_now
from socialdna.domain.creative import CreativeAnnotationSet, MediaAnchor
from socialdna.domain.evidence import (
    CreativeEventLocator,
    EntityRef,
    EvidenceRef,
    MediaLocator,
    PostTextLocator,
)
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def _put(connection: Connection, name: str, **values: Any) -> None:
    connection.execute(insert(metadata.tables[name]).values(**values).on_conflict_do_nothing())


def _reuse(
    repository: EvidenceRepository,
    kind: str,
    identity: str,
    payload: dict[str, Any],
    provenance_id: str,
) -> EntityRef:
    previous = repository.latest(kind, identity)
    if previous and repository.entity(previous)["content_hash"] == hash_config(payload):
        return previous
    return repository.save_entity(kind, identity, payload, provenance_id, available_at=utc_now())


def register_definitions(connection: Connection) -> dict[str, EntityRef]:
    from socialdna.application.evidence_service import assert_active_inputs

    repository = EvidenceRepository(connection)
    source_id, provenance_id = (
        stable_id("creative-definitions-source", "1"),
        stable_id("creative-definitions-provenance", "1"),
    )
    assert_active_inputs(connection, source_ids=(source_id,))
    _put(
        connection,
        "source_records",
        id=source_id,
        source_kind="engine_definition",
        source_uri="socialdna:creative-definitions/1",
        permission_basis="locally installed Apache-2.0 engine definitions",
        terms_json="{}",
        retrieved_at=utc_now(),
    )
    _put(
        connection,
        "provenance_records",
        id=provenance_id,
        source_record_id=source_id,
        method="creative-definitions-1",
        tool_name="socialdna",
        tool_version=__version__,
        config_json=canonical_json(
            {"annotation": "observable content, not psychological constructs"}
        ),
        created_at=utc_now(),
    )
    refs = {}
    for key, definition in TECHNIQUES.items():
        identity = stable_id("creative-technique", key)
        previous = repository.latest("creative_technique", identity)
        if previous:
            captured = json.loads(repository.entity(previous)["payload_json"])
            if captured["version"] == definition.version and captured != definition.model_dump(
                mode="json"
            ):
                raise StorageIntegrityError(
                    "Creative technique changed without a new definition version"
                )
        ref = _reuse(
            repository,
            "creative_technique",
            identity,
            definition.model_dump(mode="json"),
            provenance_id,
        )
        if json.loads(repository.entity(ref)["payload_json"]) != definition.model_dump(mode="json"):
            raise StorageIntegrityError(
                "Creative technique changed without a new definition version"
            )
        refs[key] = ref
    recipes = metadata.tables["feature_recipes"]
    for key, recipe in RECIPES.items():
        document = {
            "recipe": recipe.model_dump(mode="json"),
            "techniques": [refs[item].model_dump() for item in recipe.techniques],
            "temporal_rule": "interval-algebra-1",
        }
        existing = connection.scalar(select(recipes.c.spec_json).where(recipes.c.id == key))
        if existing is not None and existing != canonical_json(document):
            raise StorageIntegrityError("Creative recipe changed without a new pinned version")
        _put(
            connection,
            "feature_recipes",
            id=key,
            version=recipe.version,
            spec_json=canonical_json(document),
            available_at=utc_now(),
        )
    return refs


def cite_media(connection: Connection, media_id: str, start_ms: int, end_ms: int) -> EvidenceRef:
    repository = EvidenceRepository(connection)
    asset = repository.get("media_assets", media_id)
    interval = MediaInterval(start_ms=start_ms, end_ms=end_ms)
    if end_ms > asset["duration_ms"]:
        raise ConfigurationError("Direct media span exceeds original-media duration")
    locations, sources = (metadata.tables[name] for name in ("media_locations", "source_records"))
    source_id = connection.scalar(
        select(sources.c.id)
        .join(locations, locations.c.source_record_id == sources.c.id)
        .where(locations.c.media_asset_id == media_id, sources.c.content_hash == asset["sha256"])
        .order_by(sources.c.retrieved_at, sources.c.id)
        .limit(1)
    )
    if not source_id:
        raise ConfigurationError(
            "Direct video evidence requires a registered authorized byte source"
        )
    provenance_id = stable_id("direct-media-provenance", source_id, media_id)
    _put(
        connection,
        "provenance_records",
        id=provenance_id,
        source_record_id=source_id,
        method="direct-media-span-1",
        tool_name="socialdna",
        tool_version=__version__,
        config_json="{}",
        created_at=utc_now(),
    )
    media = repository.capture("media", media_id, provenance_id, mode="source_capture")
    ref = repository.save_evidence(
        stable_id("direct-media-span", media.revision_id, str(start_ms), str(end_ms)),
        MediaLocator(
            subject=media, media=media, interval=interval, artifact_id=asset["artifact_id"]
        ),
        provenance_id,
        available_at=repository.entity(media)["available_at"],
    )
    _put(
        connection,
        "direct_media_evidence_bindings",
        evidence_revision_id=ref.revision_id,
        media_id=media_id,
        media_revision_id=media.revision_id,
    )
    return ref


def post_text(
    repository: EvidenceRepository, post: EntityRef, field: str, tag_index: int | None
) -> str:
    if post.kind != "post":
        raise ConfigurationError("Text evidence requires an exact post revision")
    payload = json.loads(repository.entity(post)["payload_json"])
    if field == "caption" and tag_index is None:
        value = payload.get("caption")
    elif field == "hashtag" and tag_index is not None:
        tags = payload.get("hashtags", [])
        value = tags[tag_index] if 0 <= tag_index < len(tags) else None
    else:
        value = None
    if not isinstance(value, str):
        raise ConfigurationError("Requested caption/hashtag was not captured in this revision")
    return value


def cite_post_text(
    connection: Connection,
    post: EntityRef,
    field: Literal["caption", "hashtag"],
    start: int = 0,
    end: int | None = None,
    tag_index: int | None = None,
) -> EvidenceRef:
    repository = EvidenceRepository(connection)
    text = post_text(repository, post, field, tag_index)
    end = len(text) if end is None else end
    if start < 0 or end > len(text) or end <= start:
        raise ConfigurationError("Invalid post text span")
    entity = repository.entity(post)
    locator = PostTextLocator(
        subject=post,
        field=field,
        tag_index=tag_index,
        start_char=start,
        end_char=end,
        quote=text[start:end],
        normalization="hashtag_casefold_strip" if field == "hashtag" else "none",
    )
    ref = repository.save_evidence(
        stable_id("post-text", post.revision_id, field, str(tag_index), str(start), str(end)),
        locator,
        entity["provenance_id"],
        available_at=entity["available_at"],
    )
    _put(
        connection,
        "post_text_evidence_bindings",
        evidence_revision_id=ref.revision_id,
        post_revision_id=post.revision_id,
        field=field,
        tag_index=tag_index,
        start_char=start,
        end_char=end,
    )
    return ref


def _creative_evidence(
    connection: Connection,
    ref: EntityRef,
    media: EntityRef,
    *,
    run_id: str | None = None,
    task_id: str | None = None,
) -> EvidenceRef:
    repository = EvidenceRepository(connection)
    row = repository.entity(ref)
    locator = CreativeEventLocator.model_validate(
        {"kind": ref.kind, "subject": ref, "media": media}
    )
    evidence = repository.save_evidence(
        stable_id("creative-evidence", ref.revision_id),
        locator,
        row["provenance_id"],
        available_at=row["available_at"],
        run_id=run_id,
        task_id=task_id,
    )
    _put(
        connection,
        "creative_evidence_bindings",
        evidence_revision_id=evidence.revision_id,
        event_revision_id=ref.revision_id if ref.kind == "creative_event" else None,
        coverage_revision_id=ref.revision_id if ref.kind == "creative_coverage" else None,
    )
    return evidence


def persist_annotations(
    connection: Connection,
    media_id: str,
    spec: CreativeAnnotationSet,
    provenance_id: str,
    *,
    run_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    from socialdna.application.evidence_service import EvidenceResolver

    repository = EvidenceRepository(connection)
    asset = repository.get("media_assets", media_id)
    probes = metadata.tables["media_probes"]
    probe_json = connection.scalar(
        select(probes.c.probe_json).where(probes.c.media_asset_id == media_id)
    )
    has_audio = bool(probe_json and json.loads(probe_json).get("audio_stream_index") is not None)
    if spec.media_sha256 != asset["sha256"]:
        raise ConfigurationError("Annotation media hash does not match the registered bytes")
    definitions = register_definitions(connection)
    direct = cite_media(connection, media_id, 0, asset["duration_ms"])
    media = EvidenceResolver(connection).resolve(direct, purpose="new_claim").subject
    provenance = repository.get("provenance_records", provenance_id)
    if not provenance["source_record_id"]:
        raise ConfigurationError("Creative annotations require an authorized source")
    set_ref = repository.save_entity(
        "creative_annotation_set",
        stable_id("creative-set", media_id, spec.key),
        {"media": media.model_dump(), "spec": spec.model_dump(mode="json")},
        provenance_id,
        available_at=utc_now(),
    )
    _put(
        connection,
        "creative_annotation_sets",
        revision_id=set_ref.revision_id,
        media_id=media_id,
        key=spec.key,
        available_at=repository.get("entity_revisions", set_ref.revision_id)["available_at"],
        source_id=provenance["source_record_id"],
        producer_run_id=run_id,
        producer_task_id=task_id,
    )
    coverages = []
    for ordinal, coverage in enumerate(spec.coverage):
        if (
            coverage.modality in ("audio", "speech")
            and not has_audio
            and coverage.mode != "unknown"
        ):
            raise ConfigurationError("Audio coverage requires an actual source audio stream")
        if any(item.end_ms > asset["duration_ms"] for item in coverage.intervals) or any(
            t >= asset["duration_ms"] for t in coverage.sample_times_ms
        ):
            raise ConfigurationError("Coverage exceeds the original-media duration")
        payload: dict[str, Any] = {
            "media": media.model_dump(),
            "coverage": coverage.model_dump(mode="json"),
            "protocol": spec.protocol.model_dump(mode="json"),
            "input": direct.model_dump(),
        }
        identity = stable_id(
            "creative-coverage",
            media_id,
            spec.key,
            coverage.modality,
            hash_config({"techniques": sorted(coverage.techniques)}),
        )
        ref = _reuse(repository, "creative_coverage", identity, payload, provenance_id)
        _put(
            connection,
            "creative_coverages",
            revision_id=ref.revision_id,
            media_id=media_id,
            modality=coverage.modality,
            mode=coverage.mode,
        )
        evidence = _creative_evidence(connection, ref, media)
        _put(
            connection,
            "creative_set_coverages",
            annotation_revision_id=set_ref.revision_id,
            coverage_revision_id=ref.revision_id,
            ordinal=ordinal,
        )
        EvidenceResolver(connection).resolve(evidence, purpose="new_claim")
        coverages.append({"ref": ref.model_dump(), "evidence": evidence.model_dump(), **payload})
    events = []
    for ordinal, annotation in enumerate(spec.events):
        if set(annotation.modalities).intersection(("audio", "speech")) and not has_audio:
            raise ConfigurationError("Audio events require an actual source audio stream")
        try:
            for anchor in annotation.anchors:
                anchor.check_duration(asset["duration_ms"])
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        inputs = [item.model_dump(mode="json") for item in annotation.inputs]
        if not inputs:
            if any(a.kind == "untimed" for a in annotation.anchors):
                raise ConfigurationError("Untimed events require exact post-text evidence")
            inputs = [
                {"ref": direct.model_dump(), "modality": modality, "role": "observed"}
                for modality in annotation.modalities
            ]
        observed = set()
        observed_spans: dict[str, list[MediaInterval]] = {}
        for item in inputs:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(item["ref"]), purpose="new_claim"
            )
            if isinstance(resolved.locator, MediaLocator):
                if resolved.locator.media.id != media_id:
                    raise ConfigurationError("Creative input evidence belongs to different media")
                if item["modality"] in ("caption", "hashtag"):
                    raise ConfigurationError("Post text must cite captured post text, not video")
                if resolved.subject.kind == "text_segment":
                    segment = repository.get("text_segments", resolved.subject.id)
                    track = repository.get("text_tracks", segment["track_id"])
                    modality = {"asr": "speech", "asr_aligned": "speech", "ocr": "overlay"}.get(
                        track["track_type"], "subtitle"
                    )
                    if item["modality"] != modality:
                        raise ConfigurationError("Text-track input does not support this modality")
                if resolved.subject.kind in ("frame", "ocr_box") and item["modality"] not in (
                    "visual",
                    "color",
                    "overlay",
                ):
                    raise ConfigurationError("Still-frame evidence does not support this modality")
                if item["role"] == "observed":
                    observed_spans.setdefault(item["modality"], []).append(
                        resolved.locator.interval
                    )
            elif isinstance(resolved.locator, PostTextLocator):
                if (
                    not annotation.post
                    or resolved.locator.subject != annotation.post
                    or item["modality"] not in ("caption", "hashtag")
                    or item["modality"] != resolved.locator.field
                    or any(a.kind != "untimed" for a in annotation.anchors)
                ):
                    raise ConfigurationError(
                        "Untimed text evidence does not match the declared post"
                    )
                links = metadata.tables["post_media"]
                if not connection.scalar(
                    select(links.c.post_id).where(
                        links.c.post_id == annotation.post.id, links.c.media_asset_id == media_id
                    )
                ):
                    raise ConfigurationError("Post-text event does not belong to this media")
            else:
                raise ConfigurationError(
                    "Creative events require literal media or post-text inputs"
                )
            if item["role"] == "observed":
                observed.add(item["modality"])
        if set(annotation.modalities) - observed:
            raise ConfigurationError("Every asserted modality needs an observed source input")
        for modality in set(annotation.modalities) - {"caption", "hashtag"}:
            for anchor in annotation.anchors:
                bounds = anchor.bounds()
                if bounds and not any(
                    interval.start_ms <= bounds[0]
                    and bounds[3] <= interval.end_ms
                    and bounds[1] < interval.end_ms
                    for interval in observed_spans.get(modality, [])
                ):
                    raise ConfigurationError("Observed cue does not cover the event timing bounds")
        payload = {
            "media": media.model_dump(),
            "technique": definitions[annotation.technique].model_dump(),
            "annotation": annotation.model_dump(mode="json"),
            "inputs": inputs,
            "protocol": spec.protocol.model_dump(mode="json"),
        }
        ref = _reuse(
            repository,
            "creative_event",
            stable_id("creative-event", media_id, spec.key, annotation.key),
            payload,
            provenance_id,
        )
        _put(
            connection,
            "creative_events",
            revision_id=ref.revision_id,
            media_id=media_id,
            post_revision_id=annotation.post.revision_id if annotation.post else None,
            technique_revision_id=definitions[annotation.technique].revision_id,
            state=annotation.state,
            verdict=annotation.verdict,
        )
        for index, anchor in enumerate(annotation.anchors):
            values = anchor.model_dump(exclude={"box"})
            _put(
                connection,
                "creative_event_anchors",
                event_revision_id=ref.revision_id,
                ordinal=index,
                **values,
                box_json=canonical_json(anchor.box) if anchor.box is not None else None,
            )
        for index, item in enumerate(inputs):
            _put(
                connection,
                "creative_event_inputs",
                event_revision_id=ref.revision_id,
                ordinal=index,
                evidence_revision_id=item["ref"]["revision_id"],
                modality=item["modality"],
                role=item["role"],
            )
        evidence = _creative_evidence(connection, ref, media, run_id=run_id, task_id=task_id)
        _put(
            connection,
            "creative_annotation_members",
            annotation_revision_id=set_ref.revision_id,
            event_revision_id=ref.revision_id,
            ordinal=ordinal,
        )
        EvidenceResolver(connection).resolve(evidence, purpose="new_claim")
        events.append({"ref": ref.model_dump(), "evidence": evidence.model_dump(), **payload})
    relations = []
    for index, left in enumerate(events):
        for right in events[index + 1 :]:
            for relation in ("precedes", "overlaps", "simultaneous_within_tolerance"):
                for a, b in (
                    ((left, right), (right, left)) if relation == "precedes" else ((left, right),)
                ):
                    statuses = [
                        temporal_relation(
                            MediaAnchor.model_validate(x),
                            MediaAnchor.model_validate(y),
                            relation,
                            spec.tolerance_ms,
                        )
                        for x in a["annotation"]["anchors"]
                        for y in b["annotation"]["anchors"]
                    ]
                    status = (
                        "verified"
                        if statuses and all(s == "verified" for s in statuses)
                        else ("possible" if any(s is not None for s in statuses) else None)
                    )
                    if status is None:
                        continue
                    payload = {
                        "annotation_set": set_ref.model_dump(),
                        "source": a["ref"],
                        "target": b["ref"],
                        "relation": relation,
                        "status": status,
                        "tolerance_ms": spec.tolerance_ms,
                        "rule": "interval-algebra-1",
                        "interpretation": "temporal only, not causation or semantic reinforcement",
                    }
                    identity = stable_id(
                        "creative-relation", set_ref.id, a["ref"]["id"], b["ref"]["id"], relation
                    )
                    ref = repository.save_entity(
                        "creative_relation",
                        identity,
                        payload,
                        provenance_id,
                        available_at=utc_now(),
                    )
                    _put(
                        connection,
                        "creative_event_relations",
                        revision_id=ref.revision_id,
                        annotation_revision_id=set_ref.revision_id,
                        source_revision_id=a["ref"]["revision_id"],
                        target_revision_id=b["ref"]["revision_id"],
                        relation=relation,
                        status=status,
                        tolerance_ms=spec.tolerance_ms,
                    )
                    relations.append({"ref": ref.model_dump(), **payload})
    return {
        "ref": set_ref.model_dump(),
        "media": media.model_dump(),
        "events": events,
        "coverage": coverages,
        "relations": relations,
        "protocol": spec.protocol.model_dump(mode="json"),
        "limitations": [
            "Human/model labels are assertions with provenance, not independently "
            "validated technique accuracy.",
            "Sampling gaps are unknown; timing co-occurrence is not semantic "
            "reinforcement or causation.",
        ],
    }


def validate_projection(
    repository: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]
) -> None:
    """Validate real subtype FK ownership, not merely well-formed JSON references."""
    tables = {
        "creative_annotation_set": "creative_annotation_sets",
        "creative_event": "creative_events",
        "creative_relation": "creative_event_relations",
        "creative_coverage": "creative_coverages",
    }
    binding = repository.get(tables[ref.kind], ref.revision_id, "revision_id")
    if ref.kind == "creative_annotation_set":
        valid = (
            binding["media_id"] == payload["media"]["id"]
            and binding["key"] == payload["spec"]["key"]
        )
    elif ref.kind == "creative_coverage":
        valid = (
            binding["media_id"] == payload["media"]["id"]
            and binding["mode"] == payload["coverage"]["mode"]
            and binding["modality"] == payload["coverage"]["modality"]
        )
    elif ref.kind == "creative_relation":
        valid = (
            binding["annotation_revision_id"] == payload["annotation_set"]["revision_id"]
            and binding["source_revision_id"] == payload["source"]["revision_id"]
            and binding["target_revision_id"] == payload["target"]["revision_id"]
            and all(binding[key] == payload[key] for key in ("relation", "status", "tolerance_ms"))
        )
    else:
        annotation = payload["annotation"]
        valid = (
            binding["media_id"] == payload["media"]["id"]
            and binding["technique_revision_id"] == payload["technique"]["revision_id"]
            and binding["state"] == annotation["state"]
            and binding["verdict"] == annotation["verdict"]
            and binding["post_revision_id"]
            == (annotation["post"]["revision_id"] if annotation["post"] else None)
        )
        anchors = metadata.tables["creative_event_anchors"]
        rows = repository.connection.execute(
            select(anchors)
            .where(anchors.c.event_revision_id == ref.revision_id)
            .order_by(anchors.c.ordinal)
        ).mappings()
        captured = [
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key not in ("event_revision_id", "ordinal", "box_json")
                },
                "box": json.loads(row["box_json"]) if row["box_json"] else None,
            }
            for row in rows
        ]
        valid = valid and captured == annotation["anchors"]
        inputs = metadata.tables["creative_event_inputs"]
        rows = repository.connection.execute(
            select(inputs)
            .where(inputs.c.event_revision_id == ref.revision_id)
            .order_by(inputs.c.ordinal)
        ).mappings()
        valid = valid and [
            (row["evidence_revision_id"], row["modality"], row["role"]) for row in rows
        ] == [
            (item["ref"]["revision_id"], item["modality"], item["role"])
            for item in payload["inputs"]
        ]
    if not valid:
        raise StorageIntegrityError("Creative revision disagrees with its typed projection")


def load_annotations(
    connection: Connection,
    media_id: str,
    *,
    cutoff: str,
    key: str | None = None,
    revision: EntityRef | None = None,
) -> dict[str, Any]:
    repository = EvidenceRepository(connection)
    sets, entities = (
        metadata.tables[name] for name in ("creative_annotation_sets", "entity_revisions")
    )
    query = (
        select(sets, entities.c.entity_id, entities.c.revision_no)
        .join(entities, entities.c.id == sets.c.revision_id)
        .where(sets.c.media_id == media_id, sets.c.available_at <= cutoff)
    )
    if key:
        query = query.where(sets.c.key == key)
    if revision:
        if revision.kind != "creative_annotation_set":
            raise ConfigurationError("Expected an annotation-set revision")
        query = query.where(
            sets.c.revision_id == revision.revision_id, entities.c.entity_id == revision.id
        )
    selected = {}
    for selected_row in connection.execute(query.order_by(entities.c.revision_no)).mappings():
        selected[selected_row["key"]] = dict(selected_row)
    if not selected:
        return {
            "media_id": media_id,
            "events": [],
            "coverage": [],
            "relations": [],
            "reason": "not_detected_with_coverage: no selected annotation set",
        }
    if len(selected) != 1:
        return {
            "media_id": media_id,
            "events": [],
            "coverage": [],
            "relations": [],
            "reason": "ambiguous_annotation_sets: select an explicit key/revision",
        }
    selected_set = next(iter(selected.values()))
    set_ref = repository.ref(repository.get("entity_revisions", selected_set["revision_id"]))
    set_payload = json.loads(repository.entity(set_ref)["payload_json"])
    result: dict[str, Any] = {
        "ref": set_ref.model_dump(),
        "media": set_payload["media"],
        "media_id": media_id,
        "duration_ms": repository.get("media_assets", media_id)["duration_ms"],
        "protocol": set_payload["spec"]["protocol"],
        "source_id": selected_set["source_id"],
        "events": [],
        "coverage": [],
        "relations": [],
        "reason": None,
    }
    for table_name, column_name, output in (
        ("creative_annotation_members", "event_revision_id", "events"),
        ("creative_set_coverages", "coverage_revision_id", "coverage"),
    ):
        table = metadata.tables[table_name]
        identity: str
        for identity in connection.scalars(
            select(table.c[column_name])
            .where(table.c.annotation_revision_id == set_ref.revision_id)
            .order_by(table.c.ordinal)
        ):
            row = repository.get("entity_revisions", identity)
            ref = repository.ref(row)
            payload = json.loads(repository.entity(ref)["payload_json"])
            evidence_table = metadata.tables["evidence_revisions"]
            evidence_rows = list(
                connection.execute(
                    select(evidence_table.c.id, evidence_table.c.evidence_id).where(
                        evidence_table.c.subject_revision_id == identity,
                        evidence_table.c.locator_kind == ref.kind,
                    )
                ).mappings()
            )
            if len(evidence_rows) != 1:
                raise StorageIntegrityError(
                    "Creative revision requires its exact canonical evidence"
                )
            evidence = EvidenceRef(
                id=evidence_rows[0]["evidence_id"], revision_id=evidence_rows[0]["id"]
            )
            result[output].append(
                {
                    "ref": ref.model_dump(),
                    "evidence": evidence.model_dump(),
                    "available_at": row["available_at"],
                    "source_id": row["source_id"],
                    **payload,
                }
            )
    relation_table = metadata.tables["creative_event_relations"]
    for identity in connection.scalars(
        select(relation_table.c.revision_id)
        .where(relation_table.c.annotation_revision_id == set_ref.revision_id)
        .order_by(relation_table.c.revision_id)
    ):
        row = repository.get("entity_revisions", identity)
        ref = repository.ref(row)
        result["relations"].append(
            {"ref": ref.model_dump(), **json.loads(repository.entity(ref)["payload_json"])}
        )
    if len(result["events"]) != len(set_payload["spec"]["events"]) or len(
        result["coverage"]
    ) != len(set_payload["spec"]["coverage"]):
        raise StorageIntegrityError("Annotation set membership is incomplete")
    if [item["annotation"] for item in result["events"]] != set_payload["spec"]["events"] or [
        item["coverage"] for item in result["coverage"]
    ] != set_payload["spec"]["coverage"]:
        raise StorageIntegrityError("Annotation membership disagrees with its frozen specification")
    return result
