import json
from typing import Any

from sqlalchemy import select

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
    return result
