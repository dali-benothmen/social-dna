"""Authorized annotation import and current/pinned views over creative evidence."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.evidence_service import (
    EvidenceResolver,
    assert_active_inputs,
    assert_media_active,
)
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.production import ProductionAnnotationSet
from socialdna.ingestion.tabular import timestamp
from socialdna.storage.creative_repository import (
    load_annotations,
    persist_annotations,
    register_definitions,
)
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def _cutoff(value: str | None) -> str:
    try:
        cutoff = timestamp(value) if value else utc_now()
    except ValueError as exc:
        raise ConfigurationError("Invalid creative knowledge cutoff") from exc
    if cutoff > utc_now():
        raise ConfigurationError("Creative cutoff cannot be in the future")
    return cutoff


def read_annotations(path: Path) -> CreativeAnnotationSet | ProductionAnnotationSet:
    try:
        with path.open("rb") as stream:
            raw = stream.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Annotation document exceeds 2 MB")
        document = json.loads(raw)
        if isinstance(document, dict) and document.get("schema_version") == "2.0":
            return ProductionAnnotationSet.model_validate(document)
        return CreativeAnnotationSet.model_validate(document)
    except (OSError, ValueError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid creative annotations: {exc}") from exc


def assert_bundle_active(
    connection: Connection, bundle: dict[str, Any], *, cutoff: str | None = None
) -> None:
    if bundle.get("source_id"):
        assert_active_inputs(connection, source_ids=(bundle["source_id"],))
    for item in bundle["events"] + bundle["coverage"]:
        EvidenceResolver(connection).resolve(
            EvidenceRef.model_validate(item["evidence"]), purpose="new_claim", as_of=cutoff
        )


def import_annotations(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    specification = read_annotations(path)
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "dry_run": True,
            "media_sha256": specification.media_sha256,
            "event_count": len(specification.events),
            "limitations": [
                "Schema-only validation; real source ownership, duration and evidence "
                "are checked on import."
            ],
        }
    with open_application(settings) as application:
        return import_into_application(application, specification)


def import_into_application(
    application: Application, specification: CreativeAnnotationSet | ProductionAnnotationSet
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        assets = metadata.tables["media_assets"]
        media_id = connection.scalar(
            select(assets.c.id).where(assets.c.sha256 == specification.media_sha256)
        )
        if not media_id:
            raise ConfigurationError("Import the authorized video bytes before its annotations")
        assert_media_active(connection, media_id)
        document = specification.model_dump(mode="json")
        digest = hash_config(document)
        source_id, provenance_id = (
            stable_id("creative-import-source", digest),
            stable_id("creative-import-provenance", digest),
        )
        assert_active_inputs(connection, source_ids=(source_id,))
        artifact_id = application.artifacts.put_bytes(
            connection,
            canonical_json(document).encode(),
            kind="creative-annotations",
            mime_type="application/json",
        )
        application.artifacts.add_reference(
            connection,
            artifact_id,
            owner_type="creative_source",
            owner_id=source_id,
            role="annotation",
        )
        connection.execute(
            insert(metadata.tables["source_records"])
            .values(
                id=source_id,
                source_kind="creative_annotation_import",
                source_uri="socialdna:creative-source/" + digest,
                permission_basis=specification.permission_basis,
                terms_json=canonical_json(
                    {"protocol": specification.protocol.model_dump(mode="json")}
                ),
                retrieved_at=utc_now(),
                content_hash=digest,
                raw_artifact_id=artifact_id,
            )
            .on_conflict_do_nothing()
        )
        provider = specification.protocol.provider
        connection.execute(
            insert(metadata.tables["provenance_records"])
            .values(
                id=provenance_id,
                source_record_id=source_id,
                method="imported-creative-annotations-1",
                tool_name="socialdna",
                tool_version=__version__,
                provider_name=provider.provider if provider else None,
                model_name=provider.model if provider else None,
                model_revision=provider.revision if provider else None,
                config_json=canonical_json(
                    {
                        "external_annotation": True,
                        "protocol": specification.protocol.model_dump(mode="json"),
                    }
                ),
                created_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        result = persist_annotations(connection, str(media_id), specification, provenance_id)
        result.update(source_id=source_id, artifact_id=artifact_id, valid=True, written=True)
        return result


def creative_timeline(
    application: Application,
    media_id: str,
    *,
    cutoff: str | None = None,
    key: str | None = None,
    revision: EntityRef | None = None,
) -> dict[str, Any]:
    cutoff = _cutoff(cutoff)
    with application.database.transaction() as connection:
        EvidenceRepository(connection).get("media_assets", media_id)
        bundle = load_annotations(connection, media_id, cutoff=cutoff, key=key, revision=revision)
        try:
            assert_media_active(connection, media_id)
            assert_bundle_active(connection, bundle)
        except ConfigurationError as exc:
            return {
                "media_id": media_id,
                "ref": bundle.get("ref"),
                "events": [],
                "coverage": [],
                "relations": [],
                "eligible": False,
                "limitations": [str(exc)],
                "reason": "withdrawn_or_ineligible_inputs",
            }
        return {
            **bundle,
            "eligible": True,
            "limitations": [
                *bundle.get("limitations", []),
                "Temporal relations do not prove semantic reinforcement or "
                "psychological mechanisms.",
            ],
        }


def definitions(application: Application) -> dict[str, Any]:
    from socialdna.analyzers.creative import RECIPES, TECHNIQUES
    from socialdna.analyzers.production import RECIPES as PRODUCTION_RECIPES
    from socialdna.analyzers.production import TECHNIQUES as PRODUCTION_TECHNIQUES

    with application.database.transaction() as connection:
        refs = register_definitions(connection)
    return {
        "techniques": [
            {"ref": refs[key].model_dump(), **definition.model_dump(mode="json")}
            for key, definition in {**TECHNIQUES, **PRODUCTION_TECHNIQUES}.items()
        ],
        "recipes": [
            recipe.model_dump(mode="json")
            for recipe in (*RECIPES.values(), *PRODUCTION_RECIPES.values())
        ],
    }


def materialize(
    application: Application,
    media_id: str,
    recipes: list[str],
    *,
    cutoff: str | None = None,
    key: str | None = None,
    post: EntityRef | None = None,
) -> dict[str, Any]:
    from socialdna.analytics.features import materialize_creative_value
    from socialdna.storage.creative_repository import cite_media

    if not recipes or len(recipes) > 10 or len(set(recipes)) != len(recipes):
        raise ConfigurationError("Select one to ten unique pinned recipes")
    cutoff = _cutoff(cutoff)
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        asset = repository.get("media_assets", media_id)
        assert_media_active(connection, media_id)
        bundle = load_annotations(connection, media_id, cutoff=cutoff, key=key)
        assert_bundle_active(connection, bundle, cutoff=cutoff)
        media = (
            EvidenceResolver(connection)
            .resolve(cite_media(connection, media_id, 0, asset["duration_ms"]), purpose="new_claim")
            .subject
        )
        subject, post_payload = media, None
        if post:
            if post.kind != "post":
                raise ConfigurationError("Expected a captured post revision")
            entity = repository.entity(post)
            links = metadata.tables["post_media"]
            if not connection.scalar(
                select(links.c.post_id).where(
                    links.c.post_id == post.id, links.c.media_asset_id == media_id
                )
            ):
                raise ConfigurationError("Post is not associated with this media")
            subject, post_payload = post, json.loads(entity["payload_json"])
        values = {
            recipe: materialize_creative_value(
                connection,
                recipe,
                feature_key=recipe.rsplit(".v", 1)[0],
                subject=subject.model_dump(),
                bundle=bundle,
                post_payload=post_payload,
                cutoff=cutoff,
            )
            for recipe in recipes
        }
        return {
            "media_id": media_id,
            "annotation_ref": bundle.get("ref"),
            "subject": subject.model_dump(),
            "values": values,
            "limitations": [
                "Prespecified recipe views, not an outcome-guided search or psychological finding."
            ],
        }


def automatic_annotation(
    application: Application, media_id: str, run_id: str
) -> tuple[CreativeAnnotationSet, list[str]]:
    """Literal track/caption candidates with real source clocks; never visual semantics."""
    from socialdna.analyzers.creative import literal_proposals
    from socialdna.media.timeline import timeline
    from socialdna.storage.creative_repository import cite_post_text

    data = timeline(application, media_id, run_id=run_id)
    evidence = {item["subject_id"]: item for item in data["evidence_items"]}
    segments, input_ids = [], []
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        asset = repository.get("media_assets", media_id)
        for segment in data["text_segments"]:
            original = evidence.get(segment["id"])
            if not original:
                continue
            ref = EvidenceResolver(connection).resolve(original["id"], purpose="new_claim").ref
            modality = (
                "speech"
                if segment["track_type"] in ("asr", "asr_aligned")
                else ("overlay" if segment["track_type"] == "ocr" else "subtitle")
            )
            segments.append(
                {
                    **segment,
                    "modality": modality,
                    "inputs": [{"ref": ref.model_dump(), "modality": modality, "role": "observed"}],
                }
            )
            input_ids.append(original["id"])
        posts, links = (metadata.tables[name] for name in ("posts", "post_media"))
        post_id: str
        for post_id in connection.scalars(
            select(posts.c.id)
            .join(links, links.c.post_id == posts.c.id)
            .where(links.c.media_asset_id == media_id)
        ):
            post = repository.latest("post", post_id)
            if not post:
                continue
            payload = json.loads(repository.entity(post)["payload_json"])
            if payload.get("caption"):
                ref = cite_post_text(connection, post, "caption")
                EvidenceResolver(connection).resolve(ref, purpose="new_claim")
                segments.append(
                    {
                        "id": post.id,
                        "text": payload["caption"],
                        "modality": "caption",
                        "post": post.model_dump(),
                        "inputs": [
                            {"ref": ref.model_dump(), "modality": "caption", "role": "observed"}
                        ],
                    }
                )
        proposals = literal_proposals(segments)
        coverage = [
            {
                "modality": "visual",
                "techniques": ["finished_dish", "ingredient_display", "preparation_instruction"],
                "mode": "sampled",
                "sample_times_ms": [frame["timestamp_ms"] for frame in data["frames"]],
                "limitation": "Sampled frame evidence has no semantic classifier "
                "and cannot establish absence.",
            }
        ]
        spec = CreativeAnnotationSet.model_validate(
            {
                "key": "automatic-cooking-opening-v1",
                "media_sha256": asset["sha256"],
                "permission_basis": "derived only from the registered authorized media "
                "and captured post inputs",
                "protocol": {
                    "origin": "deterministic",
                    "author": "SocialDNA literal-cues-1",
                    "procedure": "Pinned literal wording regex, no object/psychological inference",
                    "outcome_access": "blinded",
                    "label_frozen_before_outcomes": True,
                },
                "coverage": coverage,
                "events": proposals,
            }
        )
        return spec, input_ids
