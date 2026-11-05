"""Bounded import, review, analysis and redaction over the shared audience engine."""

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.audience.annotations import RUBRIC, RUBRIC_VERSION, AnnotationSet, literal_candidates
from socialdna.audience.collections import CollectionSpec
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef
from socialdna.ingestion.tabular import timestamp
from socialdna.storage import audience_repository as repository
from socialdna.storage.audience_retention import begin, preview, resume
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

Spec = TypeVar("Spec", bound=BaseModel)


def read_spec(path: Path, model: type[Spec]) -> Spec:
    try:
        with path.open("rb") as stream:
            raw = stream.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Audience document exceeds the 2 MB import budget")
        return model.model_validate_json(raw)
    except (OSError, ValueError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid audience document: {exc}") from exc


def import_document(
    settings: Settings, path: Path, kind: str, *, dry_run: bool = False
) -> dict[str, Any]:
    model = (
        CollectionSpec if kind == "collection" else AnnotationSet if kind == "annotations" else None
    )
    if model is None:
        raise ConfigurationError("Unknown audience document type")
    spec: CollectionSpec | AnnotationSet = (
        read_spec(path, CollectionSpec)
        if model is CollectionSpec
        else read_spec(path, AnnotationSet)
    )
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "dry_run": True,
            "limitations": [
                "Schema-only validation. Actual source ownership, exact spans and links "
                "are checked on import."
            ],
        }
    with open_application(settings) as application:
        return import_into_application(application, spec)


def import_into_application(
    application: Application, spec: CollectionSpec | AnnotationSet
) -> dict[str, Any]:
    document = spec.model_dump(mode="json")
    digest = hash_config(document)
    source, provenance = (
        stable_id("audience-source", digest),
        stable_id("audience-provenance", digest),
    )
    from socialdna.storage.audience_retention import guard

    with application.database.transaction() as connection:
        guard(connection, "source", source)
        protocol = spec.protocol if isinstance(spec, AnnotationSet) else None
        provider = protocol.provider if protocol else None
        repository.put(
            connection,
            "source_records",
            id=source,
            source_kind="audience_annotation_import" if protocol else "audience_collection_import",
            source_uri=spec.source_uri
            if isinstance(spec, CollectionSpec)
            else "socialdna:audience-source/" + digest,
            permission_basis=spec.permission_basis,
            terms_json=canonical_json(
                {"protocol": protocol.model_dump(mode="json") if protocol else None}
            ),
            retrieved_at=utc_now(),
            content_hash=digest,
        )
        repository.put(
            connection,
            "provenance_records",
            id=provenance,
            source_record_id=source,
            method="audience-import-1",
            tool_name="socialdna",
            tool_version=__version__,
            provider_name=provider.provider if provider else None,
            model_name=provider.model if provider else None,
            model_revision=provider.revision if provider else None,
            config_json=canonical_json(
                {"protocol": protocol.model_dump(mode="json") if protocol else None}
            ),
            created_at=utc_now(),
        )
        # Validate and write canonical references BEFORE retaining raw text blobs;
        # failed imports cannot leave forbidden orphaned quote artifacts behind.
        result = (
            repository.persist_collection(connection, spec, provenance)
            if isinstance(spec, CollectionSpec)
            else repository.persist_annotations(connection, spec, provenance)
        )
        artifact = application.artifacts.put_bytes(
            connection,
            canonical_json(document).encode(),
            kind="audience-source",
            mime_type="application/json",
        )
        application.artifacts.add_reference(
            connection, artifact, owner_type="audience_source", owner_id=source, role="raw"
        )
        connection.execute(
            metadata.tables["source_records"]
            .update()
            .where(metadata.tables["source_records"].c.id == source)
            .values(raw_artifact_id=artifact)
        )
        return {
            **result,
            "valid": True,
            "written": True,
            "source_id": source,
            "artifact_id": artifact,
        }


def _cutoff(value: str | None) -> str:
    try:
        result = timestamp(value) if value else utc_now()
    except ValueError as exc:
        raise ConfigurationError("Invalid audience knowledge cutoff") from exc
    if result > utc_now():
        raise ConfigurationError("Audience knowledge cutoff cannot be in the future")
    return result


def collection_ref(
    connection: Any, identity: str, cutoff: str, revision: str | None = None
) -> EntityRef:
    repo = EvidenceRepository(connection)
    if revision:
        ref = EntityRef(kind="audience_collection", id=identity, revision_id=revision)
        row = repo.get("entity_revisions", revision)
        if row["entity_id"] != identity or row["kind"] != ref.kind or row["available_at"] > cutoff:
            raise ConfigurationError("Collection revision does not match identity/as-of scope")
        return ref
    table = metadata.tables["entity_revisions"]
    row = (
        connection.execute(
            select(table)
            .where(
                table.c.kind == "audience_collection",
                table.c.entity_id == identity,
                table.c.available_at <= cutoff,
            )
            .order_by(table.c.revision_no.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not row:
        raise ConfigurationError("No audience collection revision is known by this cutoff")
    return repo.ref(dict(row))


def _bundle(connection: Any, collection: EntityRef, cutoff: str, key: str | None) -> dict[str, Any]:
    resolver, repo = EvidenceResolver(connection), EvidenceRepository(connection)
    resolver.resolve(
        repository.evidence_ref(connection, collection), purpose="new_claim", as_of=cutoff
    )
    document = repo.entity(collection)
    sets, revisions = (
        metadata.tables["audience_annotation_sets"],
        metadata.tables["entity_revisions"],
    )
    query = (
        select(sets, revisions.c.entity_id, revisions.c.revision_no)
        .join(revisions, revisions.c.id == sets.c.revision_id)
        .where(
            sets.c.collection_revision_id == collection.revision_id,
            revisions.c.available_at <= cutoff,
        )
    )
    if key:
        query = query.where(sets.c.key == key)
    selected = {}
    for row in connection.execute(query.order_by(revisions.c.revision_no)).mappings():
        selected[row["key"]] = row
    if len(selected) > 1:
        raise ConfigurationError(
            "Multiple annotation keys exist; choose an explicit --annotation-key"
        )
    result: dict[str, Any] = {
        "collection_ref": collection.model_dump(),
        "collection": json.loads(document["payload_json"]),
        "annotation_set_ref": None,
        "reactions": [],
        "clusters": [],
        "links": [],
    }
    if not selected:
        return result
    selected_row = next(iter(selected.values()))
    set_ref = repo.ref(repo.get("entity_revisions", selected_row["revision_id"]))
    resolver.resolve(
        repository.evidence_ref(connection, set_ref), purpose="new_claim", as_of=cutoff
    )
    result["annotation_set_ref"] = set_ref.model_dump()
    for plural in ("reactions", "clusters", "links"):
        table = metadata.tables["audience_set_" + plural]
        identities: list[str] = list(
            connection.scalars(
                select(table.c.member_revision_id)
                .where(table.c.set_revision_id == set_ref.revision_id)
                .order_by(table.c.ordinal)
            )
        )
        result[plural] = [
            {
                "ref": (ref := repo.ref(repo.get("entity_revisions", identity))).model_dump(),
                "evidence": repository.evidence_ref(connection, ref).model_dump(),
                **json.loads(repo.entity(ref)["payload_json"]),
            }
            for identity in identities
        ]
    return result


def show(
    application: Application,
    identity: str,
    *,
    revision: str | None = None,
    as_of: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    cutoff = _cutoff(as_of)
    with application.database.transaction() as connection:
        ref = collection_ref(connection, identity, cutoff, revision)
        try:
            return {
                **_bundle(connection, ref, cutoff, key),
                "eligible": True,
                "knowledge_cutoff": cutoff,
            }
        except ConfigurationError as exc:
            return {
                "collection_ref": ref.model_dump(),
                "eligible": False,
                "reactions": [],
                "clusters": [],
                "links": [],
                "limitations": [str(exc)],
            }


def propose_literal(application: Application, collection: EntityRef) -> dict[str, Any]:
    with application.database.transaction() as connection:
        data = _bundle(connection, collection, utc_now(), "literal-en-v1")
        annotations = []
        for member in data["collection"]["spec"]["members"]:
            comment = repository.entity_active(
                connection, EntityRef.model_validate(member["comment"])
            )
            labels, negated = literal_candidates(comment["body"], member["language"])
            annotations.append(
                {
                    "key": "literal-" + member["comment"]["id"],
                    "comment": member["comment"],
                    "start_char": 0,
                    "end_char": len(comment["body"]),
                    "quote": comment["body"],
                    "labels": labels,
                    "language": member["language"],
                    "negated": negated,
                    "ironic": None,
                    "ambiguous": True if labels == ("ambiguous",) else None,
                    "rationale": "Literal English candidate only; intention meaning, attribution "
                    "and irony require human review.",
                }
            )
    spec = AnnotationSet.model_validate(
        {
            "key": "literal-en-v1",
            "collection": collection.model_dump(),
            "permission_basis": "Derived only from eligible registered audience inputs",
            "protocol": {
                "origin": "deterministic",
                "author": "socialdna",
                "procedure": "literal-en-1",
                "outcome_access": "blinded",
            },
            "annotations": annotations,
        }
    )
    return import_into_application(application, spec)


def _summarize(connection: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle["collection"]["spec"]
    groups: dict[str, list[str]] = {}
    excluded = {"declared_exclusions": 0, "known_creator_replies": 0, "duplicate_comment_ids": 0}
    creator_unknown = 0
    for member in spec["members"]:
        comment = repository.entity_active(connection, EntityRef.model_validate(member["comment"]))
        if not member["eligible"]:
            excluded["declared_exclusions"] += 1
            continue
        if spec["creator_policy"] == "exclude_known" and member["creator_authored"] is True:
            excluded["known_creator_replies"] += 1
            continue
        creator_unknown += int(member["creator_authored"] is None)
        group = (
            hash_config({"text": comment["body"]})
            if spec["duplicate_policy"] == "collapse_exact_text"
            else member["comment"]["id"]
        )
        groups.setdefault(group, []).append(member["comment"]["revision_id"])
    eligible_ids = {identity for members in groups.values() for identity in members}
    annotations = [
        item["annotation"]
        for item in bundle["reactions"]
        if item["annotation"]["comment"]["revision_id"] in eligible_ids
    ]
    excluded["duplicate_comment_ids"] = sum(len(members) - 1 for members in groups.values())
    rates, fully_reviewed = {}, set()
    for label in RUBRIC:
        confirmed, uncertain, disagreements = set(), set(), set()
        for group, members in groups.items():
            matching = [a for a in annotations if a["comment"]["revision_id"] in members]
            positive, ambiguous, negative = False, False, False
            for annotation in matching:
                if annotation["state"] == "reviewed" and annotation["complete_rubric_review"]:
                    fully_reviewed.add(group)
                clear = (
                    annotation["state"] == "reviewed"
                    and all(
                        annotation[flag] is False for flag in ("negated", "ironic", "ambiguous")
                    )
                    and "ambiguous" not in annotation["labels"]
                )
                if clear and annotation["complete_rubric_review"]:
                    negative = negative or label not in annotation["labels"]
                if label in annotation["labels"]:
                    positive = positive or clear
                    ambiguous = ambiguous or not clear
            if positive and (negative or ambiguous):
                disagreements.add(group)
            if ambiguous or (positive and negative):
                uncertain.add(group)
            elif positive:
                confirmed.add(group)
        rates[label] = {
            "confirmed_reviewed_annotation_count": len(confirmed),
            "uncertain_or_proposed_count": len(uncertain),
            "disagreement_count": len(disagreements),
            "denominator": len(groups),
            "observed_annotation_fraction": len(confirmed) / len(groups)
            if groups and any(a["state"] == "reviewed" for a in annotations)
            else None,
            "population_prevalence": None,
            "unit": "eligible collected comment groups"
            if spec["duplicate_policy"] == "collapse_exact_text"
            else "eligible collected comment identities",
        }
    return {
        "counts": {
            "declared_supplied_rows": spec["supplied_count"],
            "unique_comment_identities": len(spec["members"]),
            "unrepresented_declared_rows": spec["supplied_count"] - len(spec["members"]),
            "eligible_comment_identities": len(eligible_ids),
            "eligible_text_groups": len(groups),
            "fully_reviewed_groups": len(fully_reviewed),
            "not_fully_reviewed_groups": len(groups) - len(fully_reviewed),
            "unknown_creator_authorship": creator_unknown,
            **excluded,
        },
        "rates": rates,
    }


def analyze(
    application: Application,
    identity: str,
    *,
    revision: str | None = None,
    as_of: str | None = None,
    key: str | None = None,
    literal: bool = False,
) -> dict[str, Any]:
    cutoff = _cutoff(as_of)
    with application.database.transaction() as connection:
        collection = collection_ref(connection, identity, cutoff, revision)
    if literal:
        if as_of:
            raise ConfigurationError("New proposals cannot be backdated into a historical cutoff")
        propose_literal(application, collection)
        cutoff, key = utc_now(), key or "literal-en-v1"
    with application.database.transaction() as connection:
        bundle = _bundle(connection, collection, cutoff, key)
        rubrics = repository.register_rubric(connection)
        inputs = {
            "method": "audience-summary-1",
            "collection": collection.model_dump(),
            "annotations": bundle["annotation_set_ref"],
            "rubrics": [r.model_dump() for r in rubrics],
            "requested_cutoff": as_of,
        }
        fingerprint = hash_config(inputs)
        table = metadata.tables["audience_analyses"]
        cached = connection.scalar(
            select(table.c.revision_id).where(table.c.fingerprint == fingerprint)
        )
        if cached:
            ref = EvidenceRepository(connection).ref(
                EvidenceRepository(connection).get("entity_revisions", cached)
            )
            EvidenceResolver(connection).resolve(
                repository.evidence_ref(connection, ref), purpose="new_claim"
            )
            return {
                **json.loads(EvidenceRepository(connection).entity(ref)["payload_json"])["report"],
                "cached": True,
                "ref": ref.model_dump(),
                "evidence": repository.evidence_ref(connection, ref).model_dump(),
            }
        summary = _summarize(connection, bundle)
        run = new_id()
        report = {
            "schema_version": "1.0",
            "report_type": "audience",
            "run_id": run,
            "collection_ref": collection.model_dump(),
            "annotation_set_ref": bundle["annotation_set_ref"],
            "knowledge_cutoff": cutoff,
            "collection": bundle["collection"]["spec"],
            "rubric_version": RUBRIC_VERSION,
            "reactions": bundle["reactions"],
            "clusters": bundle["clusters"],
            "links": bundle["links"],
            **summary,
            "limitations": [
                "Counts describe eligible collected comments, not viewers or "
                "unbiased audience prevalence.",
                "Expressed intention is not verified preparation, saving, following or conversion.",
                "Content links are qualified references/interpretations, not causal mechanisms. "
                "A textual timestamp is not reaction/watch time.",
                "Unreviewed, negated, ironic, ambiguous and disputed labels are not "
                "confirmed positive reactions.",
                "Missing annotations are unknown, not reviewed negatives. Duplicate text groups "
                "are not necessarily independent people.",
                *bundle["collection"]["spec"]["limitations"],
            ],
        }
        provenance = stable_id("audience-analysis-provenance", fingerprint)
        source = EvidenceRepository(connection).entity(collection)["source_id"]
        repository.put(
            connection,
            "provenance_records",
            id=provenance,
            source_record_id=source,
            method="audience-summary-1",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json(inputs),
            created_at=utc_now(),
        )
        connection.execute(
            metadata.tables["analysis_runs"]
            .insert()
            .values(
                id=run,
                target_type="audience",
                target_id=collection.id,
                depth="standard",
                profile_version="audience-summary-1",
                config_json=canonical_json(inputs),
                config_hash=fingerprint,
                status="succeeded",
                created_at=utc_now(),
                started_at=utc_now(),
                finished_at=utc_now(),
            )
        )
        citations = [repository.evidence_ref(connection, collection)]
        if bundle["annotation_set_ref"]:
            citations.append(
                repository.evidence_ref(
                    connection, EntityRef.model_validate(bundle["annotation_set_ref"])
                )
            )
        ref = repository.save(
            connection,
            "audience_analysis",
            stable_id("audience-analysis", fingerprint),
            {"collection": collection.model_dump(), "fingerprint": fingerprint, "report": report},
            provenance,
            entity_inputs=[collection, *rubrics],
            evidence_inputs=citations,
            collection_revision_id=collection.revision_id,
            set_revision_id=(bundle["annotation_set_ref"] or {}).get("revision_id"),
            run_id=run,
            fingerprint=fingerprint,
        )
        citation = repository.cite(connection, ref, collection, run_id=run)
        return {
            **report,
            "ref": ref.model_dump(),
            "evidence": citation.model_dump(),
            "cached": False,
        }


def load_analysis(application: Application, run_id: str) -> dict[str, Any]:
    with application.database.transaction() as connection:
        table = metadata.tables["audience_analyses"]
        identity = connection.scalar(select(table.c.revision_id).where(table.c.run_id == run_id))
        if not identity:
            raise ConfigurationError("Unknown audience analysis run")
        repo = EvidenceRepository(connection)
        ref = repo.ref(repo.get("entity_revisions", identity))
        EvidenceResolver(connection).resolve(
            repository.evidence_ref(connection, ref), purpose="new_claim"
        )
        return {
            **json.loads(repo.entity(ref)["payload_json"])["report"],
            "ref": ref.model_dump(),
            "evidence": repository.evidence_ref(connection, ref).model_dump(),
        }


def comments(
    application: Application, post_id: str, *, limit: int = 1000, after: str = ""
) -> dict[str, Any]:
    if not 1 <= limit <= 2000:
        raise ConfigurationError("Audience comment page limit must be between 1 and 2000")
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        repo.get("posts", post_id)
        table = metadata.tables["comments"]
        rows = list(
            connection.execute(
                select(table)
                .where(table.c.post_id == post_id, table.c.id > after)
                .order_by(table.c.id)
                .limit(limit + 1)
            ).mappings()
        )
        result = []
        for row in rows[:limit]:
            ref = repo.latest("comment", row["id"])
            if not ref:
                raise ConfigurationError("Comment has no captured revision")
            try:
                payload = repository.entity_active(connection, ref)
                result.append(
                    {
                        "ref": ref.model_dump(),
                        "eligible": True,
                        **{
                            k: payload[k]
                            for k in ("body", "published_at", "post_ref", "parent_comment_id")
                        },
                    }
                )
            except ConfigurationError:
                result.append({"ref": ref.model_dump(), "eligible": False, "body": None})
        return {
            "comments": result,
            "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
            "limitations": [
                "This is a page of retained records, not a claim of complete collection coverage."
            ],
        }


def media_links(application: Application, media_id: str) -> dict[str, Any]:
    """Opt-in context lane. Inferred links never receive playback positions."""
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        repo.get("media_assets", media_id)
        posts: set[str] = set(
            connection.scalars(
                select(metadata.tables["post_media"].c.post_id).where(
                    metadata.tables["post_media"].c.media_asset_id == media_id
                )
            )
        )
        table = metadata.tables["entity_revisions"]
        current: dict[str, Any] = {}
        for row in connection.execute(
            select(table).where(table.c.kind == "audience_collection").order_by(table.c.revision_no)
        ).mappings():
            current[row["entity_id"]] = row
        if len(current) > 200:
            raise ConfigurationError(
                "Audience overlay exceeds 200 collections; inspect a collection directly"
            )
        result, withheld = [], []
        for row in current.values():
            ref = repo.ref(dict(row))
            try:
                document = repository.entity_active(connection, ref)
                if not posts.intersection(p["id"] for p in document["spec"]["posts"]):
                    continue
                sets = metadata.tables["audience_annotation_sets"]
                keys: set[str] = set(
                    connection.scalars(
                        select(sets.c.key).where(sets.c.collection_revision_id == ref.revision_id)
                    )
                )
                for key in sorted(keys):
                    bundle = _bundle(connection, ref, utc_now(), key)
                    reactions = {r["ref"]["revision_id"]: r for r in bundle["reactions"]}
                    for link in bundle["links"]:
                        if (
                            link["target_context"].get("media_id") == media_id
                            or link["link"]["target"]["id"] in posts
                        ):
                            result.append(
                                {
                                    **link,
                                    "collection_ref": ref.model_dump(),
                                    "annotation_set_ref": bundle["annotation_set_ref"],
                                    "reaction": reactions[link["reaction"]["revision_id"]],
                                }
                            )
            except ConfigurationError:
                withheld.append(ref.model_dump())
        if len(result) > 1000:
            raise ConfigurationError(
                "Audience overlay exceeds 1000 links; inspect a collection directly"
            )
        return {
            "links": result,
            "withheld_collections": withheld,
            "limitations": [
                "Context links are not retention events or causal explanations. "
                "Publication time is not playback time; inferred links remain untimed."
            ],
        }


def redact(
    application: Application,
    *,
    comment_id: str | None = None,
    source_id: str | None = None,
    confirmation: str | None = None,
    reason: str = "",
    actor: str = "local-user",
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        plan = preview(connection, comment_id=comment_id, source_id=source_id)
        if not confirmation:
            return {**plan, "written": False, "requires_confirmation": True}
        operation = begin(connection, plan, confirmation=confirmation, reason=reason, actor=actor)
    application.vectors.close()
    application.vectors.__enter__()
    resume(application.database, application.paths)
    backups = sorted(str(path) for path in (application.paths.root / "backups").glob("*"))
    return {
        "operation_id": operation,
        "written": True,
        "active_library_redacted": True,
        "status": "partial" if backups else "success",
        "counts": plan["counts"],
        "backups_requiring_separate_cleanup": backups,
        "limitations": plan["limitations"],
    }
