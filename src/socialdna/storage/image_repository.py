"""Canonical static records and exact typed asset/ordered-item/region citations."""

import json
from typing import Any

from sqlalchemy import Connection
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef, ImageLocator
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {"image_analysis", "carousel_analysis", "post_media_input"}


def save(
    connection: Connection, kind: str, key: str, payload: dict[str, Any], provenance: str
) -> EntityRef:
    if kind not in KINDS:
        raise ConfigurationError("Unsupported static record kind")
    ref = EvidenceRepository(connection).save_entity(
        kind, stable_id("static", kind, key), payload, provenance, available_at=utc_now()
    )
    connection.execute(
        insert(metadata.tables["static_records"])
        .values(
            revision_id=ref.revision_id,
            run_id=payload.get("run_id"),
            media_revision_id=payload["media"]["revision_id"] if payload.get("media") else None,
            post_revision_id=payload["post"]["revision_id"] if payload.get("post") else None,
        )
        .on_conflict_do_nothing()
    )
    return ref


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    row = repo.get("static_records", ref.revision_id, "revision_id")
    target = EntityRef.model_validate(payload.get("media") or payload["post"])
    if target.kind != ("media" if ref.kind == "image_analysis" else "post"):
        raise StorageIntegrityError("Static record target has the wrong entity kind")
    target_row = repo.entity(target)
    if target.kind == "media" and json.loads(target_row["payload_json"])["media_type"] != "image":
        raise StorageIntegrityError("Static image analysis cannot target video bytes")
    if (row["run_id"], row["media_revision_id"], row["post_revision_id"]) != (
        payload.get("run_id"),
        payload["media"]["revision_id"] if payload.get("media") else None,
        payload["post"]["revision_id"] if payload.get("post") else None,
    ):
        raise StorageIntegrityError("Static record binding mismatch")
    if row["run_id"]:
        run = repo.get("analysis_runs", row["run_id"])
        target = payload.get("media") or payload["post"]
        if (
            run["target_type"] != ("image" if ref.kind == "image_analysis" else "carousel")
            or run["target_id"] != target["id"]
        ):
            raise StorageIntegrityError("Static analysis run targets a different asset/post")


def locator(
    connection: Connection,
    ref: EntityRef,
    field: str = "summary",
    *,
    position: int | None = None,
    box_index: int | None = None,
) -> ImageLocator:
    repo = EvidenceRepository(connection)
    raw = json.loads(repo.entity(ref)["payload_json"])
    media, post, artifact, region, quote = raw.get("media"), raw.get("post"), None, None, None
    image = raw if ref.kind == "image_analysis" else None
    if ref.kind == "media":
        if field != "asset" or raw["media_type"] != "image" or position is not None:
            raise ConfigurationError("Only actual static assets have image asset citations")
        media = ref.model_dump()
        region = (0.0, 0.0, 1.0, 1.0)
    elif ref.kind == "post_media_input":
        if field != "alternative_text" or not raw.get("alt_text"):
            raise ConfigurationError("Alternative text was not supplied")
        position, quote = raw["position"], raw["alt_text"]
    elif ref.kind == "carousel_analysis":
        if field not in ("summary", "item", "ocr", "alternative_text"):
            raise ConfigurationError("Unsupported carousel citation field")
        if field == "summary":
            if position is not None:
                raise ConfigurationError("Summary cannot select a carousel item")
        else:
            item = next((i for i in raw["items"] if i["position"] == position), None)
            if item is None:
                raise ConfigurationError("Carousel position is outside this frozen manifest")
            if field == "alternative_text":
                source = json.loads(
                    repo.entity(EntityRef.model_validate(item["input"]))["payload_json"]
                )
                quote = source.get("alt_text")
            elif item.get("image"):
                image = json.loads(
                    repo.entity(EntityRef.model_validate(item["image"]))["payload_json"]
                )
                media = image["media"]
    elif ref.kind != "image_analysis":
        raise ConfigurationError("Wrong static evidence subject kind")
    elif field not in ("summary", "ocr") or position is not None:
        raise ConfigurationError("Standalone image evidence has no carousel position")
    if image is not None:
        artifact, region = image["artifact_id"], (0.0, 0.0, 1.0, 1.0)
        if field == "ocr":
            if box_index is None or box_index >= len(image["ocr"]["boxes"]):
                raise ConfigurationError("OCR region is outside the captured analysis")
            box = image["ocr"]["boxes"][box_index]
            xs, ys = zip(*box["points"], strict=True)
            region, quote = (min(xs), min(ys), max(xs), max(ys)), box["text"]
    elif field == "ocr":
        raise ConfigurationError("No OCR was produced for this item")
    return ImageLocator.model_validate(
        dict(
            subject=ref.model_dump(),
            field=field,
            position=position,
            box_index=box_index,
            media=media,
            post=post,
            artifact_id=artifact,
            region=region,
            quote=quote,
        )
    )


def cite(
    connection: Connection,
    ref: EntityRef,
    field: str = "summary",
    *,
    position: int | None = None,
    box_index: int | None = None,
) -> EvidenceRef:
    repo = EvidenceRepository(connection)
    target = locator(connection, ref, field, position=position, box_index=box_index)
    row = repo.entity(ref)
    raw = json.loads(row["payload_json"])
    citation = repo.save_evidence(
        stable_id("static-evidence", ref.revision_id, field, str(position), str(box_index)),
        target,
        row["provenance_id"],
        run_id=raw.get("run_id"),
        available_at=row["available_at"],
    )
    connection.execute(
        insert(metadata.tables["static_evidence_bindings"])
        .values(
            evidence_revision_id=citation.revision_id,
            subject_revision_id=ref.revision_id,
        )
        .on_conflict_do_nothing()
    )
    return citation
