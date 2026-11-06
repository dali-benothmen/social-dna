"""Deny-first expiry and source erasure for native capture/report copies."""

import json
from typing import Any

from sqlalchemy import Connection, inspect, select

from socialdna.config.paths import DataPaths
from socialdna.core.hashing import canonical_json
from socialdna.core.time import utc_now
from socialdna.storage.schema import metadata


def native_source(connection: Connection, source_id: str) -> bool:
    if not inspect(connection).has_table("acquisition_captures"):
        return False
    table = metadata.tables["acquisition_captures"]
    return connection.scalar(select(table.c.id).where(table.c.source_id == source_id)) is not None


def scrub(connection: Connection, items: dict[str, list[str]]) -> None:
    """Called inside the existing confirmed-erasure journal before history triggers return."""
    if not inspect(connection).has_table("acquisition_captures"):
        return
    revisions = metadata.tables["entity_revisions"]
    erased = set(items.get("entity_revision", []))
    captures = metadata.tables["acquisition_captures"]
    native_sources: set[str] = set(
        connection.scalars(
            select(captures.c.source_id).where(captures.c.source_id.in_(items.get("source", [])))
        )
    )
    if not native_sources:
        return
    # Restore a prior independently sourced current identity when possible. Never
    # overwrite a later independent edit with an older API observation.
    rows = [
        dict(row)
        for row in connection.execute(
            select(revisions)
            .where(revisions.c.kind.in_(("account", "post")))
            .order_by(revisions.c.revision_no)
        ).mappings()
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["kind"], row["entity_id"]), []).append(row)
    for (kind, identity), history in groups.items():
        latest = history[-1]
        if latest["id"] not in erased or latest["source_id"] not in native_sources:
            continue
        previous = next(
            (
                row
                for row in reversed(history[:-1])
                if row["id"] not in erased
                and row["source_id"] not in native_sources
                and not json.loads(row["payload_json"]).get("redacted")
            ),
            None,
        )
        payload = json.loads(previous["payload_json"]) if previous else {}
        if kind == "account":
            values = {
                "external_id": payload.get("external_id", "expired-" + identity),
                "handle": payload.get("handle"),
                "niche": payload.get("niche"),
                "profile_json": payload.get("profile_json", canonical_json({})),
            }
            table = metadata.tables["accounts"]
        else:
            values = {
                "published_at": payload.get("published_at"),
                "title": payload.get("title"),
                "caption": payload.get("caption"),
            }
            table = metadata.tables["posts"]
        connection.execute(table.update().where(table.c.id == identity).values(**values))
    connection.execute(
        captures.update().where(captures.c.source_id.in_(native_sources)).values(state="erased")
    )
    bindings = metadata.tables["workflow_bindings"]
    sessions = metadata.tables["workflow_sessions"]
    connection.execute(
        sessions.update()
        .where(
            sessions.c.id.in_(
                select(bindings.c.workflow_id).where(bindings.c.revision_id.in_(erased))
            )
        )
        .values(state="partial", action_code="source_erased", updated_at=utc_now())
    )


def expire(database: Any, paths: DataPaths) -> int:
    """Continue restartable redaction before normal library access."""
    from socialdna.storage.audience_retention import begin, preview, resume

    with database.transaction() as connection:
        table = metadata.tables["acquisition_captures"]
        due = list(
            connection.scalars(
                select(table.c.source_id)
                .where(
                    table.c.state.in_(("active", "purge_pending")), table.c.expires_at <= utc_now()
                )
                .limit(100)
            )
        )
        for source_id in due:
            plan = preview(connection, source_id=source_id)
            begin(
                connection,
                plan,
                confirmation=plan["confirmation"],
                reason="Source-native API retention expired",
                actor="source-retention-policy",
            )
            connection.execute(
                table.update().where(table.c.source_id == source_id).values(state="purge_pending")
            )
    if due:
        resume(database, paths)
    return len(due)
