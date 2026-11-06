"""Atomic canonical imports, separate from media decoding and model execution."""

import hashlib
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.ingestion.tabular import (
    Account,
    Comment,
    Media,
    MetricDefinition,
    MetricSnapshot,
    ParsedImport,
    Post,
    Tag,
    parse_import,
)
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata

STATE_TABLES = ("accounts", "posts", "metric_definitions", "comments", "media_references")


def _identity(kind: str, platform: str, external_id: str) -> str:
    return stable_id(kind, platform, external_id)


def _read_state(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    """A dry run must not initialize, migrate, lock or otherwise write the data directory."""
    path = DataPaths(settings.data_dir).database
    state: dict[str, list[dict[str, Any]]] = {name: [] for name in STATE_TABLES}
    if not path.is_file():
        return state
    try:
        with immutable_snapshot(path) as connection:
            connection.row_factory = sqlite3.Row
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            for name in STATE_TABLES:
                if name in tables:
                    state[name] = [dict(row) for row in connection.execute(f"SELECT * FROM {name}")]
    except sqlite3.Error as exc:
        raise ConfigurationError("Cannot validate against the existing SQLite database") from exc
    return state


def _definition(record: MetricDefinition) -> dict[str, Any]:
    return record.model_dump(exclude={"record_type"})


def validate_references(
    parsed: ParsedImport, state: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    accounts = {row["id"]: row for row in state["accounts"]}
    posts = {row["id"]: row for row in state["posts"]}
    definitions = {row["key"]: row for row in state["metric_definitions"]}
    comments = {row["id"]: row for row in state["comments"]}
    seen: dict[str, dict[str, Any]] = {}
    # Establish identities before checking references, regardless of row ordering.
    for number, record in zip(parsed.rows, parsed.records, strict=True):
        data = record.model_dump()
        identity: str | None = None
        if isinstance(record, Account):
            identity = _identity("account", record.platform, record.external_id)
            accounts[identity] = {**accounts.get(identity, {}), **data, "id": identity}
        elif isinstance(record, Post):
            identity = _identity("post", record.platform, record.external_id)
            previous = posts.get(identity)
            account_id = _identity("account", record.platform, record.account_external_id)
            if previous and (
                previous["account_id"] != account_id
                or (
                    previous["published_at"] is not None
                    and previous["published_at"] != record.published_at
                )
            ):
                errors.append(
                    {"row": number, "message": "Existing post ownership/time is immutable"}
                )
            posts[identity] = {**data, "id": identity, "account_id": account_id}
        elif isinstance(record, MetricDefinition):
            identity = record.key
            new_definition = _definition(record)
            if identity in definitions and definitions[identity] != new_definition:
                errors.append(
                    {"row": number, "message": "Metric definition changed; use a new versioned key"}
                )
            definitions[identity] = new_definition
        elif isinstance(record, Media):
            identity = f"media:{record.platform}:{record.post_external_id}:{record.position}"
        elif isinstance(record, Comment):
            post_id = _identity("post", record.platform, record.post_external_id)
            identity = stable_id("comment", post_id, record.external_id)
            comments[identity] = {**data, "post_id": post_id, "id": identity}
        elif isinstance(record, MetricSnapshot):
            identity = canonical_json(
                {
                    key: data[key]
                    for key in (
                        "record_type",
                        "platform",
                        "subject_type",
                        "subject_external_id",
                        "metric_key",
                        "observed_at",
                        "window_start",
                        "window_end",
                    )
                }
            )
        if identity:
            if identity in seen and seen[identity] != data:
                errors.append(
                    {"row": number, "message": "Conflicting duplicate identity in dataset"}
                )
            seen[identity] = data

    for number, record in zip(parsed.rows, parsed.records, strict=True):
        message: str | None = None
        if isinstance(record, Post):
            if _identity("account", record.platform, record.account_external_id) not in accounts:
                message = "Unknown account_external_id"
        elif isinstance(record, (Tag, Media, Comment)):
            post_id = _identity("post", record.platform, record.post_external_id)
            if post_id not in posts:
                message = "Unknown post_external_id"
            if isinstance(record, Comment) and record.parent_external_id:
                parent = stable_id("comment", post_id, record.parent_external_id)
                if parent not in comments or parent == stable_id(
                    "comment", post_id, record.external_id
                ):
                    message = "Unknown or self-referencing parent comment"
                # Parent cycles cannot be inserted in dependency order.
                visited: set[str] = set()
                while parent in comments:
                    if parent in visited:
                        message = "Comment parent cycle"
                        break
                    visited.add(parent)
                    item = comments[parent]
                    next_external = item.get("parent_external_id")
                    parent = stable_id("comment", post_id, next_external) if next_external else ""
        elif isinstance(record, MetricSnapshot):
            subject_id = _identity(record.subject_type, record.platform, record.subject_external_id)
            subjects = posts if record.subject_type == "post" else accounts
            definition = definitions.get(record.metric_key)
            if subject_id not in subjects:
                message = "Unknown metric subject"
            elif (
                not definition
                or definition["platform"] != record.platform
                or definition["subject_type"] != record.subject_type
            ):
                message = "Unknown or incompatible metric definition"
            elif definition["measurement"] == "period" and record.window_start is None:
                message = "Period metrics require an observation window"
            elif (
                definition["unit"] == "count"
                and record.value is not None
                and float(record.value) != int(record.value)
            ):
                message = "Count metrics require an integer value"
            elif (
                definition["unit"] == "percent" and record.value is not None and record.value > 100
            ):
                message = "Percent metrics cannot exceed 100"
            elif record.value is not None and record.value > 2**53:
                message = "Metric exceeds lossless numeric storage range (2**53)"
            elif record.subject_type == "post":
                published = subjects[subject_id]["published_at"]
                if not published or record.observed_at < published:
                    message = (
                        "Metric observation precedes publication or publication time is absent"
                    )
                elif record.window_start and record.window_start < published:
                    message = "Post observation window starts before publication"
                elif (
                    definition["measurement"] == "cumulative"
                    and record.window_start
                    and record.window_start != published
                ):
                    message = "Cumulative post windows must start at publication"
        if message:
            errors.append({"row": number, "message": message})
    return errors


def import_dataset(
    settings: Settings, path: Path, format_name: Literal["csv", "json"], *, dry_run: bool = False
) -> dict[str, Any]:
    path = path.expanduser().resolve()
    parsed = parse_import(path, format_name)
    errors = parsed.errors + validate_references(parsed, _read_state(settings))
    result: dict[str, Any] = {
        "status": "error" if errors else "success",
        "valid": not errors,
        "dry_run": dry_run,
        "errors": errors,
        "counts": dict(Counter(record.record_type for record in parsed.records)),
        "written": False,
        "limitations": ["validation_failed: No records were written."] if errors else [],
    }
    if errors or dry_run:
        return result
    with open_application(settings) as application:
        # Recheck under the application lock to close the validation/write race.
        with application.database.transaction() as connection:
            state = {
                name: [
                    dict(row)
                    for row in connection.execute(select(metadata.tables[name])).mappings()
                ]
                for name in STATE_TABLES
            }
            errors = validate_references(parsed, state)
            if errors:
                return {
                    **result,
                    "status": "error",
                    "valid": False,
                    "errors": errors,
                    "limitations": ["validation_failed: No records were written."],
                }
            return {**result, **_persist(application, connection, parsed, path)}


def _upsert(connection: Connection, table_name: str, data: dict[str, Any], keys: list[str]) -> None:
    table = metadata.tables[table_name]
    statement = insert(table).values(**data)
    changes = {key: getattr(statement.excluded, key) for key in data if key not in keys}
    connection.execute(
        statement.on_conflict_do_update(index_elements=keys, set_=changes)
        if changes
        else statement.on_conflict_do_nothing()
    )


def persist_records(
    application: Application, connection: Connection, parsed: ParsedImport
) -> dict[str, Any]:
    """Atomic in-memory import for collectors; caller owns the writer lifecycle/transaction.

    Remote collectors cannot sneak local file references through this entrypoint.
    Reuse exactly the v1 reference checks/writer without reopening the application lock.
    """
    if not parsed.source or parsed.errors or any(isinstance(r, Media) for r in parsed.records):
        raise ConfigurationError("Collector imports require validated non-media records")
    state = {
        name: [dict(row) for row in connection.execute(select(metadata.tables[name])).mappings()]
        for name in STATE_TABLES
    }
    if validate_references(parsed, state):
        raise ConfigurationError("Collected metadata conflicts with existing canonical identities")
    return _persist(application, connection, parsed, application.paths.root / "capture.json")


def _persist(
    application: Application, connection: Connection, parsed: ParsedImport, path: Path
) -> dict[str, Any]:
    from socialdna.storage.audience_retention import guard

    for record in parsed.records:
        if isinstance(record, Comment):
            post_id = _identity("post", record.platform, record.post_external_id)
            guard(connection, "comment", stable_id("comment", post_id, record.external_id))
    assert parsed.source is not None
    source = parsed.source
    checksum = hashlib.sha256(parsed.raw).hexdigest()
    # Source metadata participates in identity: consent is never silently inherited.
    batch_id = stable_id("import", source.dataset_id, checksum)
    batches = metadata.tables["import_batches"]
    existing = (
        connection.execute(select(batches).where(batches.c.id == batch_id)).mappings().first()
    )
    if existing:
        return {
            "batch_id": batch_id,
            "source_id": existing["source_id"],
            "idempotent": True,
            "post_ids": sorted(
                {
                    _identity("post", r.platform, r.external_id)
                    for r in parsed.records
                    if isinstance(r, Post)
                }
            ),
            "account_ids": sorted(
                {
                    _identity("account", r.platform, r.external_id)
                    for r in parsed.records
                    if isinstance(r, Account)
                }
            ),
        }
    now = utc_now()
    source_id, provenance_id = stable_id("source", batch_id), stable_id("provenance", batch_id)
    artifact_id = application.artifacts.put_bytes(
        connection, parsed.raw, kind="raw-import", mime_type="application/octet-stream"
    )
    connection.execute(
        metadata.tables["source_records"]
        .insert()
        .values(
            id=source_id,
            source_kind="tabular_export",
            source_uri=source.source_uri,
            permission_basis=source.permission_basis,
            terms_json=canonical_json(source.model_dump()),
            retrieved_at=now,
            content_hash=checksum,
            raw_artifact_id=artifact_id,
        )
    )
    connection.execute(
        metadata.tables["provenance_records"]
        .insert()
        .values(
            id=provenance_id,
            source_record_id=source_id,
            method="versioned_import",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json(
                {"schema_version": parsed.schema_version, "dataset_id": source.dataset_id}
            ),
            created_at=now,
        )
    )
    counts = dict(Counter(record.record_type for record in parsed.records))
    connection.execute(
        batches.insert().values(
            id=batch_id,
            dataset_id=source.dataset_id,
            checksum=checksum,
            source_id=source_id,
            provenance_id=provenance_id,
            counts_json=canonical_json(counts),
            created_at=now,
        )
    )
    account_ids: set[str] = set()
    ordered = sorted(
        parsed.records,
        key=lambda r: {
            "account": 0,
            "post": 1,
            "metric_definition": 2,
            "media": 3,
            "tag": 4,
            "comment": 5,
            "metric_snapshot": 6,
        }[r.record_type],
    )
    pending_comments: list[Comment] = []
    captures: list[tuple[str, str]] = []
    for record in ordered:
        entity_type, entity_id = record.record_type, ""
        if isinstance(record, Account):
            entity_id = _identity("account", record.platform, record.external_id)
            values: dict[str, Any] = {
                "id": entity_id,
                "platform": record.platform,
                "external_id": record.external_id,
            }
            if record.creator_key:
                creator_id = stable_id("creator", record.creator_key)
                connection.execute(
                    insert(metadata.tables["creators"])
                    .values(id=creator_id)
                    .on_conflict_do_nothing()
                )
                values["creator_id"] = creator_id
            for key in ("handle", "niche"):
                if key in record.model_fields_set:
                    values[key] = getattr(record, key)
            if "profile" in record.model_fields_set:
                values["profile_json"] = canonical_json(record.profile)
            _upsert(connection, "accounts", values, ["id"])
            account_ids.add(entity_id)
        elif isinstance(record, Post):
            entity_id = _identity("post", record.platform, record.external_id)
            values = {
                "id": entity_id,
                "account_id": _identity("account", record.platform, record.account_external_id),
                "platform": record.platform,
                "external_id": record.external_id,
                "content_type": record.content_type,
                "published_at": record.published_at,
                "source_timezone": "UTC",
            }
            values.update(
                {
                    key: getattr(record, key)
                    for key in ("title", "caption", "url")
                    if key in record.model_fields_set
                }
            )
            _upsert(connection, "posts", values, ["id"])
        elif isinstance(record, MetricDefinition):
            entity_id = record.key
            connection.execute(
                insert(metadata.tables["metric_definitions"])
                .values(**_definition(record))
                .on_conflict_do_nothing()
            )
        elif isinstance(record, Media):
            post_id = _identity("post", record.platform, record.post_external_id)
            uri = record.uri
            if not urlparse(uri).scheme or Path(uri).is_absolute():
                uri = (path.parent / uri).resolve().as_uri()
            references = metadata.tables["media_references"]
            old_uri = connection.scalar(
                select(references.c.uri).where(
                    references.c.post_id == post_id, references.c.position == record.position
                )
            )
            if old_uri is not None and old_uri != uri:
                links = metadata.tables["post_media"]
                connection.execute(
                    links.delete().where(
                        links.c.post_id == post_id, links.c.position == record.position
                    )
                )
                connection.execute(
                    metadata.tables["post_media_versions"]
                    .insert()
                    .values(
                        id=new_id(),
                        post_id=post_id,
                        position=record.position,
                        media_id=None,
                        source_id=source_id,
                        available_at=now,
                    )
                )
            _upsert(
                connection,
                "media_references",
                {
                    "post_id": post_id,
                    "position": record.position,
                    "uri": uri,
                    "source_id": source_id,
                },
                ["post_id", "position"],
            )
            entity_id = stable_id("media-reference", post_id, str(record.position))
        elif isinstance(record, Tag):
            captures.append(("post", _identity("post", record.platform, record.post_external_id)))
            normalized = record.value.lstrip("#").strip().casefold()
            entity_id = stable_id("tag", record.kind, normalized)
            connection.execute(
                insert(metadata.tables["tags"])
                .values(
                    id=entity_id,
                    kind=record.kind,
                    normalized_value=normalized,
                    display_value=record.value,
                )
                .on_conflict_do_nothing()
            )
            connection.execute(
                insert(metadata.tables["post_tags"])
                .values(
                    post_id=_identity("post", record.platform, record.post_external_id),
                    tag_id=entity_id,
                    source="supplied",
                )
                .on_conflict_do_nothing()
            )
        elif isinstance(record, Comment):
            pending_comments.append(record)
            entity_id = stable_id(
                "comment",
                _identity("post", record.platform, record.post_external_id),
                record.external_id,
            )
        elif isinstance(record, MetricSnapshot):
            entity_id = _persist_snapshot(connection, record, source.dataset_id, provenance_id, now)
        if entity_id:
            # A tabular "media" record is only an unresolved URI reference, not
            # a decoded media asset. Its eventual analyzer registers actual media.
            if entity_type in {
                "account",
                "post",
                "metric_definition",
                "comment",
                "metric_snapshot",
            }:
                captures.append((entity_type, entity_id))
            connection.execute(
                insert(metadata.tables["provenance_links"])
                .values(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    provenance_id=provenance_id,
                    role="imported",
                )
                .on_conflict_do_nothing()
            )
    # Two passes support arbitrary ordering and existing parent references.
    for record in pending_comments:
        from socialdna.storage.audience_retention import guard

        post_id = _identity("post", record.platform, record.post_external_id)
        guard(connection, "comment", stable_id("comment", post_id, record.external_id))
        _upsert(
            connection,
            "comments",
            {
                "id": stable_id("comment", post_id, record.external_id),
                "post_id": post_id,
                "external_id": record.external_id,
                "body": record.body,
                "published_at": record.published_at,
            },
            ["id"],
        )
    for record in pending_comments:
        if record.parent_external_id:
            post_id = _identity("post", record.platform, record.post_external_id)
            table = metadata.tables["comments"]
            connection.execute(
                table.update()
                .where(table.c.id == stable_id("comment", post_id, record.external_id))
                .values(parent_comment_id=stable_id("comment", post_id, record.parent_external_id))
            )
    # Capture after all upserts/parent links, in dependency order and in the same
    # transaction. Citations must never read mutable current text as history.
    repository = EvidenceRepository(connection)
    for kind, identity in captures:
        repository.capture(
            kind,
            identity,
            None if kind == "metric_snapshot" else provenance_id,
            mode="source_capture",
        )
        if kind == "metric_snapshot":
            repository.metric_evidence(identity)
    from socialdna.storage import image_repository

    for record in parsed.records:
        if isinstance(record, Media):
            post_id = _identity("post", record.platform, record.post_external_id)
            post_ref = repository.latest("post", post_id) or repository.capture("post", post_id)
            references = metadata.tables["media_references"]
            captured_uri = connection.scalar(
                select(references.c.uri).where(
                    references.c.post_id == post_id, references.c.position == record.position
                )
            )
            image_repository.save(
                connection,
                "post_media_input",
                f"{post_id}:{record.position}",
                {
                    "post": post_ref.model_dump(),
                    "position": record.position,
                    "uri": captured_uri,
                    "alt_text": record.alt_text,
                    "entity_inputs": [post_ref.model_dump()],
                    "evidence_inputs": [],
                },
                provenance_id,
            )
    return {
        "batch_id": batch_id,
        "source_id": source_id,
        "artifact_id": artifact_id,
        "account_ids": sorted(account_ids),
        "post_ids": sorted(
            {
                _identity("post", r.platform, r.external_id)
                for r in parsed.records
                if isinstance(r, Post)
            }
        ),
        "idempotent": False,
        "written": True,
    }


def _persist_snapshot(
    connection: Connection, record: MetricSnapshot, dataset_id: str, provenance_id: str, now: str
) -> str:
    table = metadata.tables["metric_observations"]
    subject_id = _identity(record.subject_type, record.platform, record.subject_external_id)
    identity = canonical_json({**record.model_dump(), "dataset_id": dataset_id})
    snapshot_id = stable_id("metric-snapshot", identity, provenance_id)
    previous = (
        connection.execute(
            select(table)
            .where(
                table.c.subject_id == subject_id,
                table.c.metric_key == record.metric_key,
                table.c.observed_at == record.observed_at,
                table.c.dataset_id == dataset_id,
                table.c.window_start.is_(None)
                if record.window_start is None
                else table.c.window_start == record.window_start,
                table.c.window_end.is_(None)
                if record.window_end is None
                else table.c.window_end == record.window_end,
            )
            .order_by(table.c.imported_at.desc(), table.c.id.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if previous and all(
        previous[key] == getattr(record, key) for key in ("value", "availability", "reason")
    ):
        return str(previous["id"])
    age: float | None = None
    if record.subject_type == "post":
        posts = metadata.tables["posts"]
        published = connection.scalar(select(posts.c.published_at).where(posts.c.id == subject_id))
        assert isinstance(published, str)
        age = (
            datetime.fromisoformat(record.window_end or record.observed_at)
            - datetime.fromisoformat(published)
        ).total_seconds()
    connection.execute(
        insert(table)
        .values(
            id=snapshot_id,
            subject_type=record.subject_type,
            subject_id=subject_id,
            post_id=subject_id if record.subject_type == "post" else None,
            account_id=subject_id if record.subject_type == "account" else None,
            metric_key=record.metric_key,
            value=record.value,
            availability=record.availability,
            reason=record.reason,
            observed_at=record.observed_at,
            window_start=record.window_start,
            window_end=record.window_end,
            post_age_seconds=age,
            dataset_id=dataset_id,
            imported_at=now,
            supersedes_id=previous["id"] if previous else None,
            provenance_id=provenance_id,
        )
        .on_conflict_do_nothing()
    )
    return snapshot_id
