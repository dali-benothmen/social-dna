"""Offline static analysis and bounded ordered carousels over existing media contracts."""

import json
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from urllib.request import url2pathname

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.analyzers.visual import visual_features
from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import (
    EvidenceResolver,
    assert_media_active,
)
from socialdna.application.import_service import import_local
from socialdna.application.task_runner import TaskRunner
from socialdna.core.exceptions import (
    DependencyUnavailable,
    InvalidMedia,
    ProviderFailure,
    SocialDNAError,
)
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.images import ImageOptions
from socialdna.media.frames import ImageArray
from socialdna.media.images import decode
from socialdna.memory.documents import entity_active
from socialdna.providers.registry import ProviderRegistry
from socialdna.storage import image_repository as repository
from socialdna.storage.creative_repository import cite_post_text
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

METHOD = "static-image-1"
CAROUSEL_METHOD = "carousel-appearance-1"


def provenance(connection: Any, source: str, key: str, config: dict[str, Any]) -> str:
    identity = stable_id("static-provenance", key)
    connection.execute(
        insert(metadata.tables["provenance_records"])
        .values(
            id=identity,
            source_record_id=source,
            method=METHOD,
            tool_name="socialdna",
            config_json=canonical_json(config),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    return identity


def resolve_image(app: Application, target: str, *, copy_media: bool = False) -> tuple[str, Path]:
    if Path(target).expanduser().is_file():
        path = Path(target).expanduser().resolve()
        decode(path, app.settings)  # Reject video/unsafe input before registering it as an image.
        target = import_local(app, path, copy_media=copy_media)["media_id"]
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        asset = repo.get("media_assets", target)
        if asset["media_type"] != "image":
            raise InvalidMedia("This asset is not a static image")
        assert_media_active(connection, target)
        paths: list[str] = list(
            connection.scalars(
                select(metadata.tables["media_locations"].c.local_path).where(
                    metadata.tables["media_locations"].c.media_asset_id == target
                )
            )
        )
        if asset["artifact_id"]:
            artifact = app.artifacts.get(connection, asset["artifact_id"])
            paths.insert(0, str(app.artifacts.path_for(artifact["relative_path"])))
    for candidate in paths:
        path = Path(candidate)
        if (
            path.is_file()
            and path.stat().st_size
            <= min(app.settings.max_media_bytes, app.settings.max_image_bytes)
            and hash_file(path) == asset["sha256"]
        ):
            return target, path
    raise InvalidMedia(
        "Registered image is missing or its bytes changed; supply the original or re-import"
    )


def _run(
    app: Application,
    target_type: str,
    target: str,
    config: dict[str, Any],
    resume: str | None = None,
) -> str:
    runs = metadata.tables["analysis_runs"]
    with app.database.transaction() as connection:
        if resume:
            old = EvidenceRepository(connection).get("analysis_runs", resume)
            if (old["target_type"], old["target_id"], old["config_hash"]) != (
                target_type,
                target,
                hash_config(config),
            ):
                raise InvalidMedia(
                    "Resume requires the same static asset, options and library versions"
                )
            connection.execute(
                runs.update().where(runs.c.id == resume).values(status="running", finished_at=None)
            )
            return resume
        identity = new_id()
        connection.execute(
            runs.insert().values(
                id=identity,
                target_type=target_type,
                target_id=target,
                depth="standard",
                profile_version=config["method"],
                config_json=canonical_json(config),
                config_hash=hash_config(config),
                status="running",
                created_at=utc_now(),
                started_at=utc_now(),
            )
        )
        return identity


def _finish(app: Application, run_id: str, partial: bool) -> None:
    with app.database.transaction() as connection:
        runs = metadata.tables["analysis_runs"]
        connection.execute(
            runs.update()
            .where(runs.c.id == run_id)
            .values(status="failed" if partial else "succeeded", finished_at=utc_now())
        )


def _archive(
    app: Application, connection: Any, ref: EntityRef, artifacts: tuple[str, ...] = ()
) -> None:
    payload = EvidenceRepository(connection).entity(ref)["payload_json"]
    archive = app.artifacts.put_bytes(
        connection, payload.encode(), kind="static-record", mime_type="application/json"
    )
    for artifact in (archive, *artifacts):
        app.artifacts.add_reference(
            connection,
            artifact,
            owner_type="static_record",
            owner_id=ref.revision_id,
            role="evidence",
        )


def analyze_image(
    app: Application,
    target: str,
    *,
    options: ImageOptions | None = None,
    copy_media: bool = False,
    resume: str | None = None,
) -> dict[str, Any]:
    options = options or ImageOptions()
    media_id, path = resolve_image(app, target, copy_media=copy_media)
    provider, unavailable = None, None
    enabled = options.ocr and not options.no_ai
    if enabled:
        try:
            provider = ProviderRegistry(app.settings).resolve(app.settings.ocr_model, "ocr")
        except DependencyUnavailable as exc:
            unavailable = str(exc)
    config = {
        "method": METHOD,
        "result_encoding": "opaque-ocr-json-1",
        "options": options.model_dump(),
        "max_image_pixels": app.settings.max_image_pixels,
        "libraries": {
            name: version(name) for name in ("Pillow", "numpy", "opencv-python-headless")
        },
        "ocr": {
            "enabled": enabled,
            "unavailable": unavailable,
            "identity": provider.identity.model_dump() if provider else None,
            "manifest": hash_config(provider.manifest.model_dump()) if provider else None,
            "runtime": provider.versions if provider else None,
            "threads": app.settings.inference_threads,
            "timeout": app.settings.inference_timeout_seconds,
        },
    }
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        media = repo.latest("media", media_id) or repo.capture("media", media_id)
        asset_citation = repository.cite(connection, media, "asset")
        EvidenceResolver(connection).resolve(asset_citation, purpose="new_claim")
    if resume:
        with app.database.transaction() as connection:
            old_run = EvidenceRepository(connection).get("analysis_runs", resume)
            completed = (
                old_run["status"] == "succeeded"
                and old_run["config_hash"] == hash_config(config)
                and old_run["target_id"] == media_id
            )
        if completed:
            return load_analysis(app, resume)
    run_id = _run(app, "image", media_id, config, resume)
    runner = TaskRunner(app, run_id, media_id)
    with tempfile.TemporaryDirectory(prefix="image-", dir=app.paths.root / "cache") as directory:
        work = Path(directory)

        def compute(context: TaskContext) -> TaskOutput:
            info, display = decode(path, app.settings, options.max_side)
            normalized = work / "display.png"
            display.save(normalized, format="PNG")
            array = cv2.cvtColor(np.array(display), cv2.COLOR_RGB2BGR)
            ocr: dict[str, Any] = {"status": "disabled", "boxes": [], "reason": None}
            context.output.input_citations = [asset_citation]
            if enabled and provider:
                context.output.provider = provider.identity
                try:
                    results = provider.read_text(
                        {
                            "frames": [{"id": media_id, "path": str(normalized)}],
                            "options": {"threads": app.settings.inference_threads},
                        }
                    )
                    if len(results) != 1 or results[0].frame_id != media_id:
                        raise ProviderFailure("OCR must return exactly the requested static asset")
                    boxes = [b.model_dump() for b in results[0].boxes]
                    for box in boxes:
                        xs, ys = zip(*box["points"], strict=True)
                        if min(xs) >= max(xs) or min(ys) >= max(ys):
                            raise ProviderFailure("OCR returned an empty image region")
                    ocr.update(status="available", boxes=boxes)
                except Exception as exc:
                    ocr.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
                    context.output.skipped = "OCR failed; deterministic appearance retained"
            elif enabled:
                ocr.update(status="unavailable", reason=unavailable)
                context.output.skipped = "Requested OCR is unavailable; appearance retained"
            context.output.blobs["display"] = (normalized, "image-display", "image/png")
            context.output.result = {
                "metadata": info.model_dump(),
                "display_size": list(display.size),
                "artifact_id": "@artifact:display",
                # Keep arbitrary recognized text opaque to internal artifact substitution.
                "ocr_json": canonical_json(ocr),
                "features": visual_features(cast(ImageArray, array), options.palette_bins),
                "interpretation": "Deterministic appearance proxies, "
                "not aesthetic quality, camera intent or performance.",
            }
            return context.output

        runner.run("image.appearance", config, [], compute)
    result = runner.results["image.appearance"]
    if "artifact_id" not in result:
        _finish(app, run_id, True)
        raise InvalidMedia(
            "Static analysis task failed: "
            + str(runner.tasks["image.appearance"].get("error", "unknown"))
        )
    result = {**result, "ocr": json.loads(result["ocr_json"])}
    result.pop("ocr_json")
    partial = result["ocr"]["status"] in ("unavailable", "failed")
    _finish(app, run_id, partial)
    with app.database.transaction() as connection:
        EvidenceResolver(connection).resolve(asset_citation, purpose="new_claim")
        repo = EvidenceRepository(connection)
        source_id = repo.entity(media)["source_id"]
        prov = provenance(connection, source_id, run_id, config)
        payload = {
            "run_id": run_id,
            "media": media.model_dump(),
            "method": METHOD,
            "status": "partial" if partial else "success",
            "configuration": config,
            **{k: v for k, v in result.items() if k not in ("artifacts", "reason")},
            "task": runner.tasks["image.appearance"],
            "entity_inputs": [media.model_dump()],
            "evidence_inputs": [asset_citation.model_dump()],
            "limitations": [
                "Static images have no playback duration or inferred viewing order/time.",
                "Measurements use a bounded orientation-corrected RGB display; "
                "transparency is composited on white.",
                "EXIF/GPS/ICC metadata is excluded from display derivatives; "
                "optional retained originals are unmodified.",
                "OCR is a model estimate, not supplied alternative text or a verified transcript.",
                "No research registration, psychological claim "
                "or performance inference is performed.",
            ],
        }
        inputs = metadata.tables["task_citation_inputs"]
        citations = metadata.tables["evidence_revisions"]
        for original in connection.execute(
            select(citations.c.evidence_id, citations.c.id)
            .join(inputs, inputs.c.evidence_revision_id == citations.c.id)
            .where(inputs.c.task_id == result["producer_task_id"])
        ):
            pinned = EvidenceRef(id=original.evidence_id, revision_id=original.id).model_dump()
            if pinned not in payload["evidence_inputs"]:
                payload["evidence_inputs"].append(pinned)
        ref = repository.save(connection, "image_analysis", run_id, payload, prov)
        repository.cite(connection, ref)
        for i in range(len(payload["ocr"]["boxes"])):
            repository.cite(connection, ref, "ocr", box_index=i)
        _archive(app, connection, ref, (payload["artifact_id"],))
    return load_analysis(app, run_id)


def link_media(
    connection: Any, post_id: str, position: int, media_id: str, source: str | None
) -> None:
    links, versions = metadata.tables["post_media"], metadata.tables["post_media_versions"]
    old = connection.scalar(
        select(links.c.media_asset_id).where(
            links.c.post_id == post_id, links.c.position == position
        )
    )
    connection.execute(
        insert(links)
        .values(
            post_id=post_id,
            position=position,
            media_asset_id=media_id,
            role="primary" if position == 0 else "additional",
        )
        .on_conflict_do_update(
            index_elements=[links.c.post_id, links.c.position], set_={"media_asset_id": media_id}
        )
    )
    if old != media_id:
        connection.execute(
            versions.insert().values(
                id=new_id(),
                post_id=post_id,
                position=position,
                media_id=media_id,
                source_id=source,
                available_at=utc_now(),
            )
        )


def analyze_carousel(
    app: Application, post_id: str, *, options: ImageOptions | None = None, max_items: int = 20
) -> dict[str, Any]:
    if not 1 <= max_items <= 100:
        raise InvalidMedia("max_items must be between 1 and 100")
    options = options or ImageOptions()
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        post = repo.latest("post", post_id) or repo.capture("post", post_id)
        raw = json.loads(entity_active(connection, post)["payload_json"])
        if raw["content_type"] != "carousel":
            raise InvalidMedia("Carousel analysis requires an actual carousel post")
        refs = metadata.tables["media_references"]
        entries = {
            r["position"]: dict(r)
            for r in connection.execute(select(refs).where(refs.c.post_id == post_id)).mappings()
        }
        links = metadata.tables["post_media"]
        for row in connection.execute(select(links).where(links.c.post_id == post_id)).mappings():
            entries.setdefault(
                row["position"], {"position": row["position"], "media_id": row["media_asset_id"]}
            )
        if not entries or len(entries) > 1000:
            raise InvalidMedia(
                "Carousel needs 1–1000 declared items; analysis is separately budgeted"
            )
        inputs = []
        for position, entry in sorted(entries.items()):
            key = f"{post_id}:{position}"
            existing = repo.latest("post_media_input", stable_id("static", "post_media_input", key))
            captured = json.loads(repo.entity(existing)["payload_json"]) if existing else {}
            if (
                not existing
                or captured.get("uri") != entry.get("uri")
                or ("uri" not in entry and captured.get("linked_media_id") != entry.get("media_id"))
            ):
                source_id = entry.get("source_id") or repo.entity(post)["source_id"]
                prov = provenance(
                    connection,
                    source_id,
                    new_id(),
                    {"capture": "current local binding; no historical exposure inferred"},
                )
                existing = repository.save(
                    connection,
                    "post_media_input",
                    key,
                    {
                        "post": post.model_dump(),
                        "position": position,
                        "uri": entry.get("uri"),
                        "alt_text": None,
                        "linked_media_id": entry.get("media_id"),
                        "entity_inputs": [post.model_dump()],
                        "evidence_inputs": [],
                    },
                    prov,
                )
            inputs.append(existing)
            entity_active(connection, existing)
        text = {"caption": raw.get("caption"), "hashtags": raw.get("hashtags", []), "evidence": []}
        if text["caption"]:
            text["evidence"].append(cite_post_text(connection, post, "caption").model_dump())
        for i in range(len(text["hashtags"])):
            text["evidence"].append(
                cite_post_text(connection, post, "hashtag", tag_index=i).model_dump()
            )
    config = {
        "method": CAROUSEL_METHOD,
        "post": post.model_dump(),
        "inputs": [r.model_dump() for r in inputs],
        "options": options.model_dump(),
        "max_items": max_items,
    }
    run_id = _run(app, "carousel", post_id, config)
    items: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for ordinal, (position, entry) in enumerate(sorted(entries.items())):
        item: dict[str, Any] = {
            "position": position,
            "input": inputs[ordinal].model_dump(),
            "image": None,
            "status": "budget_skipped",
            "message": "max_items budget",
            "duplicate_of": None,
        }
        if ordinal < max_items:
            try:
                target = entry.get("media_id")
                if "uri" in entry:
                    uri = urlparse(entry["uri"])
                    if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
                        raise InvalidMedia("Remote media is reference-only; no download attempted")
                    target = str(Path(url2pathname(uri.path)))
                analyzed = analyze_image(app, str(target), options=options)
                item.update(status=analyzed["status"], image=analyzed["ref"], message=None)
                media_id = analyzed["media"]["id"]
                item["duplicate_of"] = seen.get(media_id)
                seen.setdefault(media_id, position)
                with app.database.transaction() as connection:
                    link_media(connection, post_id, position, media_id, entry.get("source_id"))
            except SocialDNAError as exc:
                item.update(status="unavailable", message=str(exc))
        items.append(item)
    partial = any(i["status"] != "success" for i in items)
    _finish(app, run_id, partial)
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        prov = provenance(connection, repo.entity(post)["source_id"], run_id, config)
        payload = {
            "run_id": run_id,
            "post": post.model_dump(),
            "method": CAROUSEL_METHOD,
            "status": "partial" if partial else "success",
            "configuration": config,
            "items": items,
            "text": text,
            "entity_inputs": [
                post.model_dump(),
                *[r.model_dump() for r in inputs],
                *[i["image"] for i in items if i["image"]],
            ],
            "evidence_inputs": text["evidence"],
            "limitations": [
                "Manifest reflects supplied items, "
                "not verified platform completeness or viewer behavior.",
                "Supplied zero-based positions are preserved; missing positions are not invented.",
                "Only static raster items are analyzed; "
                "videos/remote/missing items remain explicit unavailable entries.",
                "Available-item means are position-weighted descriptions, "
                "not whole-post performance or independent samples.",
            ],
        }
        ref = repository.save(connection, "carousel_analysis", run_id, payload, prov)
        repository.cite(connection, ref)
        for item in items:
            repository.cite(connection, ref, "item", position=item["position"])
        _archive(app, connection, ref)
    return load_analysis(app, run_id)


def load_analysis(app: Application, run_id: str) -> dict[str, Any]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        table = metadata.tables["static_records"]
        entities = metadata.tables["entity_revisions"]
        revision = connection.scalar(
            select(table.c.revision_id)
            .join(entities, entities.c.id == table.c.revision_id)
            .where(table.c.run_id == run_id)
            .order_by(entities.c.revision_no.desc())
        )
        if not revision:
            raise InvalidMedia("No committed static report for this run")
        ref = repo.ref(repo.get("entity_revisions", revision))
        citation = repository.cite(connection, ref)
        EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        payload = json.loads(repo.entity(ref)["payload_json"])
        report = {
            **payload,
            "schema_version": "1.0",
            "report_type": "image" if ref.kind == "image_analysis" else "carousel",
            "ref": ref.model_dump(),
            "evidence": citation.model_dump(),
        }
        if ref.kind == "image_analysis":
            artifact = app.artifacts.get(connection, payload["artifact_id"])
            if not app.artifacts.verify(artifact):
                raise InvalidMedia(
                    "Retained image derivative is missing or corrupt; reanalyze the original"
                )
            report["ocr"]["evidence"] = [
                repository.cite(connection, ref, "ocr", box_index=i).model_dump()
                for i in range(len(payload["ocr"]["boxes"]))
            ]
        else:
            brightness = []
            for item in report["items"]:
                item["evidence"] = repository.cite(
                    connection, ref, "item", position=item["position"]
                ).model_dump()
                source = json.loads(
                    repo.entity(EntityRef.model_validate(item["input"]))["payload_json"]
                )
                item["alternative_text"] = {
                    "value": source.get("alt_text"),
                    "origin": "source_supplied",
                    "evidence": None,
                }
                if source.get("alt_text"):
                    item["alternative_text"]["evidence"] = repository.cite(
                        connection, ref, "alternative_text", position=item["position"]
                    ).model_dump()
                if item["image"]:
                    image = json.loads(
                        repo.entity(EntityRef.model_validate(item["image"]))["payload_json"]
                    )
                    if not app.artifacts.verify(
                        app.artifacts.get(connection, image["artifact_id"])
                    ):
                        raise InvalidMedia(
                            "Carousel image derivative is missing/corrupt; reanalyze the original"
                        )
                    item["appearance"] = image["features"]
                    item["ocr"] = image["ocr"]
                    brightness.append(image["features"]["brightness"])
            report["aggregate"] = {
                "method": CAROUSEL_METHOD,
                "declared_items": len(report["items"]),
                "available_images": len(brightness),
                "coverage": len(brightness) / len(report["items"]),
                "unique_images": len(
                    {
                        i["image"]["id"]
                        for i in report["items"]
                        if i["image"] and i["duplicate_of"] is None
                    }
                ),
                "available_item_mean_brightness": float(np.mean(brightness))
                if brightness
                else None,
                "position_weighted": True,
            }
        return report
