"""Explicitly assisted URL/media association; never a platform downloader."""

import json
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.application.image_service import analyze_carousel, analyze_image, link_media
from socialdna.application.import_service import import_local
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageConflict
from socialdna.core.hashing import canonical_json, hash_config, hash_file
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef
from socialdna.domain.images import ImageOptions
from socialdna.domain.workflows import MediaInput, WorkflowPlan, WorkflowRequest
from socialdna.media.images import looks_like_image
from socialdna.reporting.markdown import escape
from socialdna.storage import content_repository as records
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

LIMITATIONS = [
    "Assisted URL-plus-supplied-original analysis; no platform media was downloaded.",
    "URL association and permission are user declarations, not verified platform ownership.",
    "Unknown account/publication metadata stays unknown; API metrics are not imported or reused.",
    "Measurements are sampled craft proxies, not camera intent, psychology or performance effects.",
    "Source text, provider estimates and reviewed annotations retain their separate provenance.",
]


def _bounded_hash(path: Path, limit: int) -> str:
    try:
        return hash_file(path, byte_limit=limit)
    except ValueError:
        raise ConfigurationError("Supplied bytes changed or exceed the configured limit") from None


def inputs(
    settings: Settings, request: WorkflowRequest
) -> tuple[tuple[MediaInput, ...], str | None]:
    result = []
    total_bytes = 0
    for raw in request.media:
        path = Path(raw).expanduser().resolve()
        if not path.is_file() or path.stat().st_size > settings.max_media_bytes:
            raise ConfigurationError("Supply bounded existing local originals, not media URLs")
        total_bytes += path.stat().st_size
        if total_bytes > settings.max_media_bytes:
            raise ConfigurationError("Combined supplied originals exceed max_media_bytes")
        image = looks_like_image(path)
        if image and path.stat().st_size > settings.max_image_bytes:
            raise ConfigurationError("Supplied image exceeds max_image_bytes")
        result.append(
            MediaInput(
                path=str(path),
                sha256=_bounded_hash(path, settings.max_media_bytes),
                media_type="image" if image else "video",
            )
        )
    subtitle_hash = None
    if request.analysis_options.transcribe or request.analysis_options.align:
        if len(result) != 1 or result[0].media_type != "video":
            raise ConfigurationError("ASR/alignment requires a single supplied video")
    if request.subtitles:
        path = Path(request.subtitles).expanduser().resolve()
        if (
            not path.is_file()
            or path.suffix.lower() not in (".srt", ".vtt")
            or (path.stat().st_size > 5_000_000)
        ):
            raise ConfigurationError("Supply a bounded local SRT/VTT track")
        subtitle_hash = _bounded_hash(path, 5_000_000)
        if len(result) != 1 or result[0].media_type != "video":
            raise ConfigurationError("Supplied subtitles require one video")
    return tuple(result), subtitle_hash


def _verify(plan: WorkflowPlan, settings: Settings) -> None:
    total = 0
    for item in plan.media_inputs:
        path = Path(item.path)
        if not path.is_file():
            raise ConfigurationError("A supplied original changed; make a new explicit plan")
        total += path.stat().st_size
        limit = (
            min(settings.max_media_bytes, settings.max_image_bytes)
            if item.media_type == "image"
            else settings.max_media_bytes
        )
        if total > settings.max_media_bytes or path.stat().st_size > limit:
            raise ConfigurationError("Supplied bytes changed or exceed the configured limit")
        if _bounded_hash(path, limit) != item.sha256:
            raise ConfigurationError("A supplied original changed; make a new explicit plan")
    if plan.subtitles_sha256 and (
        not plan.request.subtitles
        or not Path(plan.request.subtitles).is_file()
        or _bounded_hash(Path(plan.request.subtitles), 5_000_000) != plan.subtitles_sha256
    ):
        raise ConfigurationError("The selected subtitle bytes changed; make a new plan")


def _binding(app: Application, identity: str, plan: WorkflowPlan) -> EntityRef:
    from socialdna.memory.documents import entity_active

    with app.database.transaction() as connection:
        for source_input in plan.source_inputs:
            entity_active(connection, source_input)
        old = records.records(connection, identity, "content_binding")
        if old:
            records.active(connection, old[-1])
            return old[-1]
        posts, links = metadata.tables["posts"], metadata.tables["post_media"]
        post_id = connection.scalar(
            select(posts.c.id).where(
                posts.c.platform == plan.platform, posts.c.external_id == plan.external_id
            )
        )
        if post_id:
            existing: dict[int, str] = dict(
                connection.execute(
                    select(links.c.position, links.c.media_asset_id).where(
                        links.c.post_id == post_id
                    )
                ).all()
            )
            expected = {
                i: stable_id("media", item.sha256) for i, item in enumerate(plan.media_inputs)
            }
            if existing and existing != expected and not plan.request.replace_media:
                raise StorageConflict(
                    "Different media is already bound; review and explicitly replace it"
                )
    imported = [
        import_local(app, Path(item.path), copy_media=plan.request.copy_media)
        for item in plan.media_inputs
    ]
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        source = stable_id("content-source", identity)
        provenance = stable_id("content-provenance", identity)
        connection.execute(
            insert(metadata.tables["source_records"]).values(
                id=source,
                source_kind="supplied_original_association",
                source_uri=plan.canonical_url,
                permission_basis=plan.request.permission_basis,
                terms_json=canonical_json(
                    {"association": "user_declared", "media": "independent_original"}
                ),
                content_hash=hash_config([i.model_dump() for i in plan.media_inputs]),
                retrieved_at=utc_now(),
            )
        )
        connection.execute(
            insert(metadata.tables["provenance_records"]).values(
                id=provenance,
                source_record_id=source,
                method="assisted-media-1",
                tool_name="socialdna",
                config_json=canonical_json({"workflow_id": identity}),
                created_at=utc_now(),
            )
        )
        if not post_id:
            from socialdna.application.account_import_service import _identity

            post_id = _identity("post", plan.platform, plan.external_id)
            connection.execute(
                posts.insert().values(
                    id=post_id,
                    platform=plan.platform,
                    external_id=plan.external_id,
                    url=plan.canonical_url,
                    content_type="carousel"
                    if len(imported) > 1
                    else ("photo" if plan.media_inputs[0].media_type == "image" else "video"),
                )
            )
        if plan.request.replace_media:
            connection.execute(links.delete().where(links.c.post_id == post_id))
        media = []
        for i, item in enumerate(imported):
            # Capture this independently supplied source, not a merged API post snapshot.
            ref = repo.capture("media", item["media_id"], provenance, mode="source_capture")
            media.append(ref)
            link_media(connection, post_id, i, ref.id, source)
        analysis_target = imported[0]["media_id"]
        if len(imported) > 1:
            # U1 needs a post-shaped ordered manifest. A local proxy prevents copying
            # restricted API ownership/publication fields into an independent source.
            analysis_target = stable_id("assisted-carousel", identity)
            connection.execute(
                posts.insert().values(
                    id=analysis_target,
                    platform="local",
                    external_id=identity,
                    content_type="carousel",
                    url=plan.canonical_url,
                )
            )
            repo.capture("post", analysis_target, provenance, mode="source_capture")
            for i, ref in enumerate(media):
                link_media(connection, analysis_target, i, ref.id, source)
        payload = {
            "workflow_id": identity,
            "post_id": post_id,
            "canonical_url": plan.canonical_url,
            "target_id": analysis_target,
            "media": [ref.model_dump() for ref in media],
            "entity_inputs": [ref.model_dump() for ref in (*media, *plan.source_inputs)],
            "evidence_inputs": [],
        }
        ref = records.save(connection, "content_binding", identity, "binding", payload, provenance)
        records.cite(connection, ref)
        workflows.bind(connection, identity, "capture", ref, None)
        for item in imported:
            asset = repo.get("media_assets", item["media_id"])
            if asset["artifact_id"]:
                app.artifacts.add_reference(
                    connection,
                    asset["artifact_id"],
                    owner_type="entity_revision",
                    owner_id=ref.revision_id,
                    role="original",
                )
        return ref


def render(document: dict[str, Any]) -> str:
    lines = [
        "# Assisted content analysis",
        "",
        "Source: " + document["canonical_url"],
        "",
        "Coverage: media-enriched-assisted (not a URL-only download).",
        "",
        "Goal: " + escape(document["goal"]),
        "",
    ]
    for item in document["analyses"]:
        lines += [
            f"## Item {item['position']}",
            "",
            f"Run: {item['run_id']}",
            "",
            "Kind: " + item["kind"],
            "",
        ]
        # Existing renderers preserve measurements, native text and model qualifications.
        lines += [item["markdown"], ""]
    lines += ["## Association and evidence limits", ""]
    lines += ["- " + escape(text) for text in document["limitations"]]
    return "\n".join(lines) + "\n"


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    _verify(plan, app.settings)
    with app.database.transaction() as connection:
        saved = records.records(connection, identity, "content_report")
    if saved:
        return {**records.load(app, saved[-1], "json"), "reused": True}
    binding = _binding(app, identity, plan)
    with app.database.transaction() as connection:
        raw = records.active(connection, binding)
        provenance = EvidenceRepository(connection).entity(binding)["provenance_id"]
        previous = records.records(connection, identity, "content_run")
        checkpoints: dict[int, tuple[EntityRef, dict[str, Any]]] = {
            json.loads(EvidenceRepository(connection).entity(ref)["payload_json"])["position"]: (
                ref,
                json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]),
            )
            for ref in previous
        }

    def checkpoint(position: int, run_id: str, target: str) -> None:
        with app.database.transaction() as connection:
            value = {
                "workflow_id": identity,
                "run_id": run_id,
                "target_id": target,
                "position": position,
                "entity_inputs": [binding.model_dump()],
                "evidence_inputs": [],
            }
            ref = records.save(
                connection, "content_run", identity, str(position), value, provenance
            )
            checkpoints[position] = (ref, value)

    from socialdna.application.analysis_service import analyze_video

    analyses, citations = [], []
    carousel = len(plan.media_inputs) > 1
    selected = plan.media_inputs[:1] if carousel else plan.media_inputs
    for position, item in enumerate(selected):
        resume = checkpoints.get(position, (None, {}))[1].get("run_id")
        target = raw["target_id"] if carousel else raw["media"][position]["id"]
        options = plan.request.analysis_options
        if not resume:
            if carousel:
                result = analyze_carousel(
                    app, target, options=ImageOptions(no_ai=options.no_ai, ocr=bool(options.ocr))
                )
            elif item.media_type == "image":
                result = analyze_image(
                    app, target, options=ImageOptions(no_ai=options.no_ai, ocr=bool(options.ocr))
                )
            else:
                result = analyze_video(
                    app,
                    target,
                    options=options,
                    subtitles=Path(plan.request.subtitles) if plan.request.subtitles else None,
                    on_run=partial(checkpoint, position, target=target),
                )
            resume = result["run_id"]
            checkpoint(position, resume, target)
        else:
            with app.database.transaction() as connection:
                state = EvidenceRepository(connection).get("analysis_runs", resume)["status"]
            if state != "succeeded" and item.media_type == "video" and not carousel:
                analyze_video(
                    app,
                    target,
                    options=options,
                    resume=resume,
                    subtitles=Path(plan.request.subtitles) if plan.request.subtitles else None,
                )
        report = generate_report(app, resume, "json")
        markdown = generate_report(app, resume, "markdown")
        document = report["content"]
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            if "timeline" in document:
                for row in document["timeline"]["evidence_items"]:
                    citations.append(repo.media_evidence(row["id"], legacy=False))
            else:
                from socialdna.domain.evidence import EvidenceRef

                citations.append(EvidenceRef.model_validate(document["evidence"]))
        analyses.append(
            {
                "position": position,
                "kind": "carousel" if carousel else item.media_type,
                "run_id": resume,
                "report": document,
                "markdown": markdown["content"],
            }
        )
    fulfilled = plan.request.question_scope == "content_measurements" or (
        plan.request.goal == "Analyze the supplied content with measured evidence."
    )
    document = {
        "schema_version": "1.0",
        "workflow_id": identity,
        "canonical_url": plan.canonical_url,
        "post_id": raw["post_id"],
        "binding": binding.model_dump(),
        "goal": plan.request.goal,
        "request_fulfilled": fulfilled,
        "coverage": "media-enriched-assisted",
        "status": "partial"
        if not fulfilled or any(i["report"]["status"] == "partial" for i in analyses)
        else "success",
        "analyses": analyses,
        "limitations": LIMITATIONS,
        "required_actions": []
        if fulfilled
        else [
            {
                "code": "additional_evidence_required",
                "message": "This report measures supplied content, not performance effects "
                "or account strategy. Narrow the goal or supply additional research evidence.",
            }
        ],
    }
    with app.database.transaction() as connection:
        ref = records.save(
            connection,
            "content_report",
            identity,
            "report",
            {
                "workflow_id": identity,
                "result": document,
                "entity_inputs": [
                    binding.model_dump(),
                    *[r.model_dump() for r, _ in checkpoints.values()],
                ],
                "evidence_inputs": [ref.model_dump() for ref in citations],
            },
            provenance,
        )
        records.cite(connection, ref)
        records.freeze(app, connection, ref, document, render(document))
        workflows.bind(connection, identity, "report", ref, None)
        workflows.state(
            connection, identity, "partial" if document["status"] == "partial" else "completed"
        )
    return records.load(app, ref, "json")
