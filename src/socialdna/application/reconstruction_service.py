"""Compose actual selected finished-video tracks without acquisition or invention."""

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef, EvidenceRef, MediaLocator
from socialdna.domain.reconstruction import (
    CueLane,
    CueQualification,
    ReconstructionCue,
    TextTrackSnapshot,
    TrackDisagreement,
    VideoReconstruction,
    WordTiming,
)
from socialdna.domain.workflows import ReconstructionOptions, RequiredAction, WorkflowPlan
from socialdna.media.timeline import effective_task_ids, timeline
from socialdna.reporting.reconstruction import render
from socialdna.storage import content_repository as records
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata

LIMITATIONS = (
    "Reconstruction of the finished clip, not the creator's original writing document.",
    "Original-presentation milliseconds; overlapping source spans are not clipped or word-aligned.",
    "ASR, alignment, OCR and their confidences are model estimates, not verified ground truth.",
    "Supplied subtitles are source text, not independently verified speech or on-screen text.",
    "Missing ASR/empty detection does not prove silence; no audio stream is a separate probe fact.",
    "Sampled frames and measured color/motion/audio proxies do not establish camera intent, "
    "off-screen actions, music identity, speaker identity or exhaustive visual coverage.",
    "Track hashes pin actual task/segment/word snapshots; native segment/region citations "
    "are not independently reviewed word-level timing annotations.",
    "Differing overlapping tracks are candidate disagreements, not adjudicated errors.",
    "Reviewed creative times retain declared uncertain/nominal anchors; they are not "
    "automatically precise measurements or exhaustive review.",
    "No translation, new model inference, causal finding or virality guarantee is produced.",
    "Permission and URL association are user declarations, not verified ownership or a license.",
)
NativeCitation = Callable[[str, str, dict[str, Any]], tuple[EvidenceRef, EntityRef, int, int]]


def parent_report(settings: Settings, identity: str) -> EntityRef | None:
    """Pin an existing exact output without opening/migrating the library during planning."""
    with immutable_snapshot(DataPaths(settings.data_dir).database) as connection:
        row = connection.execute(
            "SELECT e.* FROM workflow_bindings b JOIN entity_revisions e "
            "ON e.id=b.revision_id WHERE b.workflow_id=? AND b.role='report' "
            "AND e.kind='content_report' ORDER BY e.recorded_at DESC,e.id DESC LIMIT 1",
            (identity,),
        ).fetchone()
        if row is None:
            return None
        if hash_config(json.loads(row["payload_json"])) != row["content_hash"]:
            raise StorageIntegrityError("Saved parent report fingerprint mismatch")
        return EntityRef(kind=row["kind"], id=row["entity_id"], revision_id=row["id"])


def _partial(app: Application, identity: str, code: str, message: str) -> dict[str, Any]:
    with app.database.transaction() as connection:
        workflows.state(connection, identity, "awaiting_action", code)
    return {
        "workflow_id": identity,
        "status": "partial",
        "network_attempted": False,
        "required_actions": [{"code": code, "message": message}],
        "limitations": [message],
    }


def _text_rows(
    data: dict[str, Any],
    tracks: list[dict[str, Any]],
    allow: bool,
    citation: NativeCitation,
) -> tuple[list[ReconstructionCue], list[TextTrackSnapshot]]:
    rows, snapshots = [], []
    segments, words = data["text_segments"], data["text_words"]
    for track in sorted(tracks, key=lambda t: t["id"]):
        members = [s for s in segments if s["track_id"] == track["id"]]
        tokens = [w for w in words if w["segment_id"] in {s["id"] for s in members}]
        snapshots.append(
            TextTrackSnapshot(
                id=track["id"],
                producer_task_id=track["task_id"],
                track_type=track["track_type"],
                source=track["source"],
                language=track["language"],
                content_hash=hash_config({"track": track, "segments": members, "words": tokens}),
            )
        )
        for segment in members:
            ref, subject, begin, end = citation("text_segment", segment["id"], segment)
            lanes: dict[str, CueLane] = {
                "asr": "speech",
                "asr_aligned": "speech",
                "supplied_subtitle": "supplied_subtitle",
                "ocr": "visible_text",
            }
            lane = lanes.get(track["track_type"])
            if lane is None:
                raise ConfigurationError("Selected text track type is not supported")
            regions = [box for box in data["ocr_boxes"] if box["text_segment_id"] == segment["id"]]
            evidence = [ref]
            for box in regions:
                evidence.append(citation("ocr_box", box["id"], box)[0])
            rows.append(
                ReconstructionCue(
                    id=segment["id"],
                    lane=lane,
                    subject=subject,
                    evidence=tuple(evidence),
                    producer_task_id=track["task_id"],
                    track_id=track["id"],
                    start_ms=begin,
                    end_ms=end,
                    text=segment["text"] if allow else None,
                    text_withheld=not allow,
                    words=tuple(
                        WordTiming(
                            text=w["text"],
                            start_ms=w["start_ms"],
                            end_ms=w["end_ms"],
                            confidence=w["confidence"],
                        )
                        for w in tokens
                        if w["segment_id"] == segment["id"]
                    )
                    if allow
                    else (),
                    values={
                        "track_type": track["track_type"],
                        "source": track["source"],
                        "language": track["language"],
                        "confidence": segment["confidence"],
                        "regions": [
                            {
                                "frame_id": b["frame_id"],
                                "points": b["points"],
                                "confidence": b["confidence"],
                            }
                            for b in regions
                        ],
                    },
                    qualification="supplied_text"
                    if lane == "supplied_subtitle"
                    else "model_estimate",
                )
            )
    return rows, snapshots


def _measured_rows(
    data: dict[str, Any], citation: NativeCitation, model_provenance: set[str]
) -> list[ReconstructionCue]:
    rows = []
    specifications: tuple[tuple[str, str, CueLane], ...] = (
        ("scenes", "scene", "shot"),
        ("frames", "frame", "frame"),
        ("observations", "observation", "visual_measurement"),
    )
    for table, kind, lane in specifications:
        for item in data[table]:
            values: dict[str, Any]
            actual_lane = lane
            qualification: CueQualification = "measured_proxy"
            if table == "observations":
                key = item["feature_key"]
                if not key.startswith(("visual.", "motion.", "audio.")):
                    continue
                actual_lane = "audio_measurement" if key.startswith("audio.") else lane
                qualification = (
                    "model_estimate" if item["provenance_id"] in model_provenance else qualification
                )
                values = {"feature_key": key, "value": item["value"]}
            elif table == "frames":
                values = {
                    "timestamp_ms": item["timestamp_ms"],
                    "artifact_id": item["artifact_id"],
                    "selection_reason": item["selection_reason"],
                    "sampling": "sampled_frame",
                }
            else:
                values = {
                    "ordinal": item["ordinal"],
                    "detector": item["detector"],
                    "meaning": "detected shot interval, not a named transition",
                }
            evidence, subject, begin, end = citation(kind, item["id"], item)
            rows.append(
                ReconstructionCue(
                    id=item["id"],
                    lane=actual_lane,
                    subject=subject,
                    evidence=(evidence,),
                    producer_task_id=item["task_id"],
                    start_ms=begin,
                    end_ms=end,
                    values=values,
                    qualification=qualification,
                )
            )
    return rows


def _creative_rows(
    app: Application,
    media_id: str,
    revision: str,
    allow: bool,
    start: int,
    end: int,
) -> tuple[list[ReconstructionCue], EntityRef]:
    from socialdna.application.creative_service import creative_timeline

    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        ref = repo.ref(repo.get("entity_revisions", revision))
        if ref.kind != "creative_annotation_set":
            raise ConfigurationError("Select an exact creative annotation-set revision")
        payload = json.loads(repo.entity(ref)["payload_json"])
        if payload["media"]["id"] != media_id:
            raise ConfigurationError("Creative annotations belong to different media")
    bundle = creative_timeline(app, media_id, revision=ref)
    if not bundle["eligible"]:
        raise ConfigurationError("Selected creative annotations are ineligible")
    rows = []
    for event in bundle["events"]:
        annotation = event["annotation"]
        if annotation["state"] != "reviewed":
            continue
        with app.database.transaction() as connection:
            EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(event["evidence"]),
                purpose="new_claim",
                media_id=media_id,
            )
        for index, anchor in enumerate(annotation["anchors"]):
            low, high = anchor["start_min_ms"], anchor["end_max_ms"] or anchor["start_max_ms"]
            if (
                low is not None
                and high is not None
                and (
                    low >= end or (high <= start if anchor["kind"] == "interval" else high < start)
                )
            ):
                continue
            begin = anchor["nominal_start_ms"]
            if begin is None and anchor["start_min_ms"] == anchor["start_max_ms"]:
                begin = anchor["start_min_ms"]
            finish = anchor["nominal_end_ms"]
            if finish is None and anchor["end_min_ms"] == anchor["end_max_ms"]:
                finish = anchor["end_min_ms"]
            if begin is None:
                finish = None
            values = {
                "technique": annotation["technique"],
                "anchors": [anchor],
                "reviewer": annotation["reviewer"],
                "reliability": annotation["reliability"],
                "verdict": annotation["verdict"],
                "modalities": annotation["modalities"],
            }
            rows.append(
                ReconstructionCue(
                    id=stable_id("reconstruction-anchor", event["ref"]["revision_id"], str(index)),
                    lane="reviewed_creative",
                    subject=EntityRef.model_validate(event["ref"]),
                    evidence=(EvidenceRef.model_validate(event["evidence"]),),
                    start_ms=begin,
                    end_ms=finish,
                    text=annotation["description"] if allow else None,
                    text_withheld=not allow,
                    values=values,
                    qualification="reviewed_annotation",
                )
            )
    return rows, ref


def _differences(rows: list[ReconstructionCue]) -> tuple[list[TrackDisagreement], bool]:
    """Bound overlap work even for dense/long subtitle and ASR tracks."""
    selected = sorted(
        (
            row
            for row in rows
            if row.lane in ("speech", "supplied_subtitle")
            and row.start_ms is not None
            and row.end_ms is not None
        ),
        key=lambda row: (row.start_ms or 0, row.id),
    )
    result, pairs = [], 0
    for index, left in enumerate(selected):
        for other in range(index + 1, len(selected)):
            right = selected[other]
            assert left.end_ms is not None and right.start_ms is not None
            if right.start_ms >= left.end_ms:
                break
            pairs += 1
            if left.track_id != right.track_id and " ".join(
                (left.text or "").casefold().split()
            ) != " ".join((right.text or "").casefold().split()):
                result.append(TrackDisagreement(left=left.id, right=right.id))
            if len(result) >= 100 or pairs >= 10_000:
                return result, True
    return result, False


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    if plan.media_inputs:
        from socialdna.application.content_workflow_service import _verify

        _verify(plan, app.settings)
    with app.database.transaction() as connection:
        saved = records.records(connection, identity, "video_reconstruction")
    if saved:
        return {**records.load(app, saved[-1], "json"), "reused": True}
    if not plan.supported:
        return _partial(
            app,
            identity,
            "analyzed_video_required",
            "Supply one authorized video "
            "with its post URL, or select a completed assisted video workflow with --from. "
            "Cold media download, caption-only acquisition and profile scope are unavailable.",
        )
    parent = plan.parent_report
    if plan.media_inputs:
        from socialdna.application.content_workflow_service import run as analyze_content

        analysis_plan = plan.model_copy(
            update={
                "request": plan.request.model_copy(
                    update={
                        "mode": "analyze",
                        "goal": "Analyze the supplied content with measured evidence.",
                        "question_scope": "content_measurements",
                        "reconstruction": ReconstructionOptions(),
                    }
                )
            }
        )
        parent = EntityRef.model_validate(analyze_content(app, identity, analysis_plan)["report"])
    if parent is None:
        return _partial(
            app,
            identity,
            "analyzed_video_required",
            "The pinned input has no saved "
            "content report. Complete a video analysis, then make a new reconstruction plan.",
        )
    content = records.load(app, parent, "json")["content"]
    videos = [item for item in content["analyses"] if item["kind"] == "video"]
    if len(videos) != 1:
        return _partial(
            app,
            identity,
            "single_video_required",
            "Select one analyzed video, not a photo or a static/mixed carousel.",
        )
    run_id = videos[0]["run_id"]
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        producer = records.active(connection, parent)
        parent_row = repo.entity(parent)
        analysis_record = next(
            EntityRef.model_validate(raw)
            for raw in producer["entity_inputs"]
            if raw["kind"] == "content_run"
        )
        checkpoint = records.active(connection, analysis_record)
        if checkpoint["run_id"] != run_id:
            raise StorageIntegrityError("Saved analysis checkpoint disagrees with its video report")
        binding = records.active(
            connection, EntityRef.model_validate(checkpoint["entity_inputs"][0])
        )
        media_ref = EntityRef.model_validate(binding["media"][0])
        asset = repo.get("media_assets", media_ref.id)
        captured_asset = json.loads(repo.entity(media_ref)["payload_json"])
        probe = json.loads(repo.get("media_probes", media_ref.id, "media_asset_id")["probe_json"])
        if bool(probe["audio_stream_index"] is not None) != any(
            stream.get("codec_type") == "audio"
            for stream in json.loads(captured_asset["streams_json"])
        ):
            raise StorageIntegrityError("Probe audio stream disagrees with the captured asset")
    options = plan.request.reconstruction
    end = options.end_ms if options.end_ms is not None else asset["duration_ms"]
    if not 0 <= options.start_ms < end <= asset["duration_ms"]:
        raise ConfigurationError("Reconstruction window is outside the original media duration")
    data = timeline(app, media_ref.id, options.start_ms, end, run_id=run_id)
    producers = effective_task_ids(app, run_id)
    with app.database.transaction() as connection:
        table = metadata.tables["text_tracks"]
        tracks = [
            dict(t)
            for t in connection.execute(
                select(table).where(
                    table.c.media_asset_id == media_ref.id, table.c.task_id.in_(producers)
                )
            ).mappings()
        ]
        # Keep all words of each overlapping original segment, not invented
        # word-level clipping of a requested time window.
        words = metadata.tables["text_words"]
        data["text_words"] = [
            dict(row)
            for row in connection.execute(
                select(words)
                .where(words.c.segment_id.in_([s["id"] for s in data["text_segments"]]))
                .order_by(words.c.segment_id, words.c.ordinal)
            ).mappings()
        ]
        provenance = metadata.tables["provenance_records"]
        model_provenance = {
            row["id"]
            for row in connection.execute(
                select(provenance).where(
                    provenance.c.id.in_([item["provenance_id"] for item in data["observations"]])
                )
            ).mappings()
            if row["provider_name"] or row["model_name"] or row["model_revision"]
        }
    if set(options.track_ids) - {track["id"] for track in tracks}:
        raise ConfigurationError("Selected tracks do not belong to the exact analyzed video/run")
    if options.track_ids:
        tracks = [track for track in tracks if track["id"] in options.track_ids]
    if options.output == "transcript":
        if options.track_ids and any(track["track_type"] == "ocr" for track in tracks):
            raise ConfigurationError(
                "OCR is visible text; select audiovisual output, not speech transcript"
            )
        tracks = [track for track in tracks if track["track_type"] != "ocr"]
    by_subject = {(e["subject_type"], e["subject_id"]): e for e in data["evidence_items"]}

    def citation(
        kind: str, key: str, actual: dict[str, Any]
    ) -> tuple[EvidenceRef, EntityRef, int, int]:
        native = by_subject.get((kind, key))
        if native is None:
            raise StorageIntegrityError("An actual reconstruction cue has no source evidence")
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            ref = repo.media_evidence(native["id"], legacy=False)
            resolved = EvidenceResolver(connection).resolve(
                ref, purpose="new_claim", run_id=run_id, media_id=media_ref.id
            )
            locator = resolved.locator
            if not isinstance(locator, MediaLocator):
                raise StorageIntegrityError("Expected a native media-span citation")
            snapshot = json.loads(repo.entity(locator.subject)["payload_json"])
            # OCR's decoded convenience points are not a stored table column.
            if any(
                snapshot.get(k) != v
                for k, v in actual.items()
                if k in snapshot and k not in ("track_type", "source", "language")
            ):
                raise StorageIntegrityError(
                    "Selected native cue differs from its captured revision"
                )
            return ref, locator.subject, locator.interval.start_ms, locator.interval.end_ms

    rows, snapshots = _text_rows(data, tracks, options.allow_verbatim, citation)
    if options.output != "transcript":
        rows += _measured_rows(data, citation, model_provenance)
    creative = None
    if options.creative_revision and options.output != "transcript":
        reviewed, creative = _creative_rows(
            app,
            media_ref.id,
            options.creative_revision,
            options.allow_verbatim,
            options.start_ms,
            end,
        )
        rows += reviewed
    rows.sort(key=lambda row: (row.start_ms is None, row.start_ms or 0, row.lane, row.id))
    speech = [row for row in rows if row.lane == "speech"]
    captions = [row for row in rows if row.lane == "supplied_subtitle"]
    differences, comparison_limited = _differences(rows) if options.allow_verbatim else ([], False)
    has_audio = probe["audio_stream_index"] is not None
    actions = []
    if not options.allow_verbatim:
        actions.append(
            RequiredAction(
                code="reproduction_permission_required",
                message="Structural cues only. Use --allow-verbatim to declare permission "
                "to reproduce source words; this declaration does not verify a license.",
            )
        )
    if has_audio and not speech:
        actions.append(
            RequiredAction(
                code="speech_unavailable",
                message="No selected ASR segments. Supplied subtitles are not verified speech. "
                "Explicitly prepare/request a local ASR provider in a new analysis if permitted.",
            )
        )
    if options.creative_revision and not creative:
        actions.append(
            RequiredAction(
                code="creative_not_applicable",
                message="Reviewed creative cues apply to audiovisual, not transcript-only output.",
            )
        )
    supported_goal = plan.request.goal == "Reconstruct the finished video from available evidence."
    if not supported_goal:
        actions.append(
            RequiredAction(
                code="unsupported_goal",
                message="This producer reconstructs available finished-video evidence only; "
                "it does not recover original intentions, translate or explain performance.",
            )
        )
    if not rows and (has_audio or options.output != "transcript"):
        actions.append(
            RequiredAction(
                code="selected_evidence_missing",
                message="No selected cues overlap this window; broaden it or supply evidence.",
            )
        )
    document = VideoReconstruction(
        workflow_id=identity,
        canonical_url=content["canonical_url"],
        post_id=content["post_id"],
        parent_report=parent,
        analysis_record=analysis_record,
        media=media_ref,
        run_id=run_id,
        goal=plan.request.goal,
        request_fulfilled=not actions,
        status="partial" if actions else "success",
        options=options,
        duration_ms=asset["duration_ms"],
        media_clock={
            "basis": "original_presentation_ms",
            "origin_seconds": probe["origin_seconds"],
            "time_base": probe["time_base"],
            "audio_stream_index": probe["audio_stream_index"],
            "probe_hash": hash_config(probe),
        },
        window_start_ms=options.start_ms,
        window_end_ms=end,
        verbatim_permission_basis=(
            "user_declared_permitted_reproduction" if options.allow_verbatim else None
        ),
        source_tracks=tuple(snapshots),
        rows=tuple(rows),
        transcript_row_ids=tuple(
            row.id for row in rows if row.lane in ("speech", "supplied_subtitle")
        ),
        audiovisual_row_ids=tuple(row.id for row in rows) if options.output != "transcript" else (),
        modality_coverage={
            "speech": "model_estimate"
            if speech
            else "no_audio_stream"
            if not has_audio
            else "unknown_not_silence",
            "supplied_subtitles": "available_unverified" if captions else "not_selected_or_missing",
            "visible_text": "sampled_ocr_estimate"
            if any(row.lane == "visible_text" for row in rows)
            else "not_selected_or_unavailable",
            "visual": "sampled_measurements"
            if any(row.lane == "frame" for row in rows)
            else "not_selected_or_unavailable",
            "reviewed_creative": "explicit_selected_revision" if creative else "not_selected",
            "track_comparison": "bounded_screen_truncated"
            if comparison_limited
            else "selected_overlap_screen"
            if options.allow_verbatim
            else "text_withheld",
        },
        disagreements=tuple(differences),
        limitations=LIMITATIONS,
        required_actions=tuple(actions),
    )
    value = document.model_dump(mode="json")
    with app.database.transaction() as connection:
        ref = records.save(
            connection,
            "video_reconstruction",
            identity,
            "reconstruction",
            {
                "workflow_id": identity,
                "run_id": run_id,
                "target_id": media_ref.id,
                "result": value,
                "entity_inputs": [
                    parent.model_dump(),
                    *([creative.model_dump()] if creative else []),
                ],
                "evidence_inputs": [
                    ref.model_dump()
                    for ref in sorted(
                        {e for row in rows for e in row.evidence}, key=lambda e: e.revision_id
                    )
                ],
            },
            parent_row["provenance_id"],
        )
        records.cite(connection, ref)
        records.freeze(app, connection, ref, value, render(document))
        workflows.bind(connection, identity, "report", ref, None)
        workflows.state(connection, identity, "partial" if actions else "completed")
    return records.load(app, ref, "json")
