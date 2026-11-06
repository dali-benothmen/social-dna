"""Extend the existing erasure journal to content-bound video caches and text."""

import json
from typing import Any

from sqlalchemy import Connection, inspect, select

from socialdna.core.hashing import canonical_json
from socialdna.storage.schema import metadata


def tasks_for(connection: Connection, runs: set[str]) -> set[str]:
    table = metadata.tables["analysis_tasks"]
    rows = connection.execute(
        select(table.c.id, table.c.reused_from_task_id).where(table.c.run_id.in_(runs))
    ).all()
    return {value for row in rows for value in row if value}


def expand(
    connection: Connection, affected: set[str], runs: set[str], entities: list[dict[str, Any]]
) -> set[str]:
    if not inspect(connection).has_table("content_records"):
        return set()
    table = metadata.tables["content_records"]
    content_runs: set[str] = set(
        connection.scalars(
            select(table.c.run_id).where(
                table.c.revision_id.in_(affected), table.c.run_id.is_not(None)
            )
        )
    )
    runs.update(content_runs)
    tasks = tasks_for(connection, content_runs)
    if tasks:
        affected.update(
            row["id"] for row in entities if json.loads(row["payload_json"]).get("task_id") in tasks
        )
    return tasks


def scrub(connection: Connection, items: dict[str, list[str]]) -> None:
    if not inspect(connection).has_table("content_records"):
        return
    table = metadata.tables["content_records"]
    rows = list(
        connection.execute(
            select(table).where(table.c.revision_id.in_(items.get("entity_revision", [])))
        ).mappings()
    )
    if not rows:
        return
    runs = {row["run_id"] for row in rows if row["run_id"]}
    tasks = tasks_for(connection, runs)
    tracks, segments = metadata.tables["text_tracks"], metadata.tables["text_segments"]
    segment_ids = select(segments.c.id).where(
        segments.c.track_id.in_(select(tracks.c.id).where(tracks.c.task_id.in_(tasks)))
    )
    connection.execute(
        metadata.tables["text_words"]
        .update()
        .where(metadata.tables["text_words"].c.segment_id.in_(segment_ids))
        .values(text="[redacted]")
    )
    connection.execute(
        segments.update().where(segments.c.id.in_(segment_ids)).values(text="[redacted]")
    )
    evidence = metadata.tables["evidence_items"]
    connection.execute(evidence.update().where(evidence.c.task_id.in_(tasks)).values(excerpt=None))
    results = metadata.tables["analysis_task_results"]
    connection.execute(
        results.update()
        .where(results.c.task_id.in_(tasks))
        .values(result_json=canonical_json({"redacted": True}))
    )
    connection.execute(
        metadata.tables["workflow_sessions"]
        .update()
        .where(metadata.tables["workflow_sessions"].c.id.in_({row["workflow_id"] for row in rows}))
        .values(state="partial", action_code="source_erased")
    )
