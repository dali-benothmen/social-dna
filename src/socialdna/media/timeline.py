import json
from typing import Any

from sqlalchemy import or_, select

from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import InvalidMedia
from socialdna.storage.schema import metadata


def effective_task_ids(application: Application, run_id: str) -> list[str]:
    table = metadata.tables["analysis_tasks"]
    with application.database.transaction() as connection:
        rows = connection.execute(
            select(table).where(table.c.run_id == run_id, table.c.status == "succeeded")
        ).mappings()
        return list({row["reused_from_task_id"] or row["id"] for row in rows})


def timeline(
    application: Application,
    media_id: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    *,
    run_id: str | None = None,
    include_creative: bool = False,
    include_audience: bool = False,
    include_behavioral: bool = False,
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        assets, runs = metadata.tables["media_assets"], metadata.tables["analysis_runs"]
        asset = connection.execute(select(assets).where(assets.c.id == media_id)).mappings().first()
        if asset is None:
            raise InvalidMedia("Unknown media ID.")
        if run_id is None:
            run_id = connection.scalar(
                select(runs.c.id)
                .where(runs.c.target_id == media_id)
                .order_by(runs.c.created_at.desc())
                .limit(1)
            )
        if run_id is None:
            raise InvalidMedia("This media has no analysis run.")
        owned = connection.scalar(
            select(runs.c.id).where(runs.c.id == run_id, runs.c.target_id == media_id)
        )
        if owned is None:
            raise InvalidMedia("Run does not belong to this media.")
        end_ms = asset["duration_ms"] if end_ms is None else min(end_ms, asset["duration_ms"])
    if start_ms < 0 or end_ms <= start_ms:
        raise InvalidMedia("Timeline interval must be non-negative and have end > start.")
    producers = effective_task_ids(application, run_id)
    result: dict[str, Any] = {
        "media_id": media_id,
        "run_id": run_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
    with application.database.transaction() as connection:
        for name in ("scenes", "frames", "audio_segments", "observations", "evidence_items"):
            table = metadata.tables[name]
            query = select(table).where(
                table.c.media_asset_id == media_id, table.c.task_id.in_(producers)
            )
            if name == "frames":
                query = query.where(
                    table.c.timestamp_ms >= start_ms, table.c.timestamp_ms < end_ms
                ).order_by(table.c.timestamp_ms)
            else:
                query = query.where(table.c.start_ms < end_ms, table.c.end_ms > start_ms).order_by(
                    table.c.start_ms, table.c.id
                )
            rows = [dict(row) for row in connection.execute(query).mappings()]
            if name == "observations":
                for row in rows:
                    row["value"] = (
                        row["numeric_value"]
                        if row["numeric_value"] is not None
                        else json.loads(row["json_value"])
                    )
            result[name] = rows
        tracks, segments = metadata.tables["text_tracks"], metadata.tables["text_segments"]
        query = (
            select(segments, tracks.c.track_type, tracks.c.source, tracks.c.language)
            .join(tracks)
            .where(
                tracks.c.media_asset_id == media_id,
                tracks.c.task_id.in_(producers),
                segments.c.start_ms < end_ms,
                segments.c.end_ms > start_ms,
            )
            .order_by(segments.c.start_ms)
        )
        result["text_segments"] = [dict(row) for row in connection.execute(query).mappings()]
        segment_ids = [row["id"] for row in result["text_segments"]]
        words, boxes = metadata.tables["text_words"], metadata.tables["ocr_boxes"]
        result["text_words"] = [
            dict(row)
            for row in connection.execute(
                select(words)
                .where(
                    words.c.segment_id.in_(segment_ids),
                    or_(
                        words.c.start_ms.is_(None),
                        (words.c.start_ms < end_ms) & (words.c.end_ms > start_ms),
                    ),
                )
                .order_by(words.c.segment_id, words.c.ordinal)
            ).mappings()
        ]
        result["ocr_boxes"] = [
            dict(row)
            for row in connection.execute(
                select(boxes)
                .where(
                    boxes.c.text_segment_id.in_(segment_ids),
                    boxes.c.frame_id.in_([frame["id"] for frame in result["frames"]]),
                )
                .order_by(boxes.c.id)
            ).mappings()
        ]
        for box in result["ocr_boxes"]:
            box["points"] = json.loads(box["points_json"])
        inputs = metadata.tables["inference_inputs"]
        result["inference_inputs"] = [
            dict(row)
            for row in connection.execute(
                select(inputs)
                .where(inputs.c.task_id.in_(producers))
                .order_by(inputs.c.task_id, inputs.c.evidence_id)
            ).mappings()
        ]
        tasks, calls = metadata.tables["analysis_tasks"], metadata.tables["provider_calls"]
        audit_ids = set(producers) | set(
            connection.scalars(select(tasks.c.id).where(tasks.c.run_id == run_id))
        )
        result["provider_calls"] = [
            dict(row)
            for row in connection.execute(
                select(calls)
                .where(calls.c.task_id.in_(audit_ids))
                .order_by(calls.c.created_at, calls.c.id)
            ).mappings()
        ]
    if include_creative:
        from socialdna.application.creative_service import creative_timeline
        from socialdna.domain.evidence import EntityRef

        with application.database.transaction() as connection:
            tasks, task_results = (
                metadata.tables[name] for name in ("analysis_tasks", "analysis_task_results")
            )
            task = (
                connection.execute(
                    select(tasks).where(
                        tasks.c.run_id == run_id, tasks.c.task_key == "creative.events"
                    )
                )
                .mappings()
                .first()
            )
            creative_ref = None
            if task and task["status"] == "succeeded":
                raw = connection.scalar(
                    select(task_results.c.result_json).where(
                        task_results.c.task_id == (task["reused_from_task_id"] or task["id"])
                    )
                )
                creative_ref = json.loads(raw).get("creative_annotation_ref") if raw else None
        if task and not creative_ref:
            result["creative"] = {
                "events": [],
                "coverage": [],
                "relations": [],
                "eligible": True,
                "reason": "creative_task_has_no_committed_annotation",
                "limitations": ["No successful creative annotation output for this run."],
            }
        else:
            result["creative"] = creative_timeline(
                application,
                media_id,
                revision=EntityRef.model_validate(creative_ref) if creative_ref else None,
            )
    if include_audience:
        from socialdna.application.audience_service import media_links

        result["audience"] = media_links(application, media_id)
    if include_behavioral:
        from socialdna.application.behavioral_service import media_overlay

        result["behavioral"] = media_overlay(application, media_id)
    return result
