"""Previewed, terminal erasure of registered audience text and derived copies.

Only active-library canonical fields/managed blobs are covered. External exports,
untracked copies and backup bytes require separately authorized cleanup.
"""

import json
from typing import Any

from sqlalchemy import Connection, inspect, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.config.paths import DataPaths
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.storage.schema import metadata


def is_redacted(connection: Connection, kind: str, identity: str) -> bool:
    # Compatibility fixtures and older released migrations can use this repository
    # before the audience migration exists. Never cache a negative schema check.
    if not connection.info.get("audience_retention_schema"):
        if not inspect(connection).has_table("audience_tombstones"):
            return False
        connection.info["audience_retention_schema"] = True
    table = metadata.tables["audience_tombstones"]
    return (
        connection.scalar(
            select(table.c.target_id).where(
                table.c.target_kind == kind, table.c.target_id == identity
            )
        )
        is not None
    )


def guard(connection: Connection, kind: str, identity: str) -> None:
    if is_redacted(connection, kind, identity):
        raise ConfigurationError(
            "Requested data was erased; terminal audience tombstone blocks reuse"
        )


def _tokens(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_tokens(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_tokens(v) for v in value)) if value else set()
    return set()


def preview(
    connection: Connection, *, comment_id: str | None = None, source_id: str | None = None
) -> dict[str, Any]:
    if bool(comment_id) == bool(source_id):
        raise ConfigurationError("Select exactly one comment identity or audience source")
    entities = [
        dict(r) for r in connection.execute(select(metadata.tables["entity_revisions"])).mappings()
    ]
    evidence = [
        dict(r)
        for r in connection.execute(select(metadata.tables["evidence_revisions"])).mappings()
    ]
    sources = [
        dict(r) for r in connection.execute(select(metadata.tables["source_records"])).mappings()
    ]
    comments = (
        {comment_id}
        if comment_id
        else {
            r["entity_id"]
            for r in entities
            if r["kind"] == "comment" and r["source_id"] == source_id
        }
    )
    if comment_id and not connection.scalar(
        select(metadata.tables["comments"].c.id).where(
            metadata.tables["comments"].c.id == comment_id
        )
    ):
        raise ConfigurationError("Unknown comment identity")
    if source_id and not any(s["id"] == source_id for s in sources):
        raise ConfigurationError("Unknown source identity")
    if (
        source_id
        and not comments
        and not any(
            r["source_id"] == source_id
            and r["kind"]
            in (
                "audience_collection",
                "audience_annotation_set",
                "reaction_annotation",
                "reaction_cluster",
                "content_reaction_link",
                "audience_analysis",
            )
            for r in entities
        )
    ):
        raise ConfigurationError("Selected source has no registered audience content")
    affected = {r["id"] for r in entities if r["kind"] == "comment" and r["entity_id"] in comments}
    affected.update(
        r["id"]
        for r in entities
        if source_id
        and r["source_id"] == source_id
        and r["kind"]
        not in (
            "post",
            "account",
            "media",
            "metric_snapshot",
            "metric_definition",
            "frame",
            "scene",
            "observation",
            "text_segment",
            "audio_segment",
            "ocr_box",
        )
    )
    citations: set[str] = set()
    analysis_ids: set[str] = set()
    runs: set[str] = set()
    while True:
        prior = (len(affected), len(citations), len(analysis_ids))
        citations.update(r["id"] for r in evidence if r["subject_revision_id"] in affected)
        needles = (
            comments
            | affected
            | citations
            | {r["evidence_id"] for r in evidence if r["id"] in citations}
        )
        authored_sources = {
            row["source_id"]
            for row in entities
            if row["id"] in affected
            and any(
                s["id"] == row["source_id"] and s["source_kind"].startswith("audience_")
                for s in sources
            )
        }
        for row in entities:
            if row["kind"] in (
                "post",
                "account",
                "media",
                "comment",
                "metric_snapshot",
                "metric_definition",
                "frame",
                "scene",
                "observation",
                "text_segment",
                "audio_segment",
                "ocr_box",
            ):
                continue
            if row["source_id"] in authored_sources or _tokens(
                json.loads(row["payload_json"])
            ).intersection(needles):
                affected.add(row["id"])
        for analysis in connection.execute(
            select(metadata.tables["statistical_analyses"])
        ).mappings():
            if _tokens(json.loads(analysis["result_json"])).intersection(needles):
                analysis_ids.add(analysis["id"])
                runs.add(analysis["run_id"])
        audience_runs = metadata.tables["audience_analyses"]
        runs.update(
            connection.scalars(
                select(audience_runs.c.run_id).where(audience_runs.c.revision_id.in_(affected))
            )
        )
        if prior == (len(affected), len(citations), len(analysis_ids)):
            break
    source_ids = {r["source_id"] for r in entities if r["id"] in affected and r["source_id"]}
    if source_id:
        source_ids.add(source_id)
    artifacts = {
        s["raw_artifact_id"] for s in sources if s["id"] in source_ids and s["raw_artifact_id"]
    }
    artifacts.update(
        connection.scalars(
            select(metadata.tables["reports"].c.artifact_id).where(
                metadata.tables["reports"].c.run_id.in_(runs)
            )
        )
    )
    refs = metadata.tables["artifact_references"]
    owner_ids = affected | {r["entity_id"] for r in entities if r["id"] in affected} | runs
    artifacts.update(
        connection.scalars(select(refs.c.artifact_id).where(refs.c.owner_id.in_(owner_ids)))
    )
    items = {
        "comment": sorted(comments),
        "entity_revision": sorted(affected),
        "evidence_revision": sorted(citations),
        "artifact": sorted(artifacts),
        "statistical_analysis": sorted(analysis_ids),
        "source": sorted(authored_sources | ({source_id} if source_id else set())),
    }
    # Hash exact current contents as well as identities so stale confirmations fail.
    fingerprints = {r["id"]: r["content_hash"] for r in entities if r["id"] in affected}
    fingerprints.update({r["id"]: r["content_hash"] for r in evidence if r["id"] in citations})
    manifest = {
        "scope_kind": "comment" if comment_id else "source",
        "target_id": comment_id or source_id,
        "items": items,
        "fingerprints": fingerprints,
    }
    return {
        **manifest,
        "confirmation": hash_config(manifest),
        "counts": {k: len(v) for k, v in items.items()},
        "limitations": [
            "Erases active-library registered copies only. Raw mixed-source blobs and whole "
            "dependent reports may be removed; unrelated structured records are retained.",
            "External exports, untracked pasted text and backup bytes require "
            "separate authorized cleanup.",
        ],
    }


def begin(
    connection: Connection, plan: dict[str, Any], *, confirmation: str, reason: str, actor: str
) -> str:
    if confirmation != plan["confirmation"] or not reason.strip() or not actor.strip():
        raise ConfigurationError(
            "Redaction requires the current preview confirmation, reason and actor"
        )
    operation = stable_id("audience-redaction", confirmation)
    connection.execute(
        insert(metadata.tables["audience_redactions"])
        .values(
            id=operation,
            scope_kind=plan["scope_kind"],
            target_id=plan["target_id"],
            reason=reason,
            actor=actor,
            requested_at=utc_now(),
            plan_hash=confirmation,
            status="pending",
        )
        .on_conflict_do_nothing()
    )
    for kind, identities in plan["items"].items():
        for identity in identities:
            connection.execute(
                insert(metadata.tables["audience_tombstones"])
                .values(target_kind=kind, target_id=identity, operation_id=operation)
                .on_conflict_do_nothing()
            )
    return operation


def resume(database: Any, paths: DataPaths) -> None:
    """Roll confirmed journal entries forward before exposing normal library reads."""
    with database.transaction() as connection:
        journal = metadata.tables["audience_redactions"]
        pending = list(
            connection.scalars(select(journal.c.id).where(journal.c.status == "pending"))
        )
    if not pending:
        return
    from socialdna.storage.artifacts import ArtifactStore

    for operation in pending:
        with database.transaction() as connection:
            tombstones = metadata.tables["audience_tombstones"]
            items: dict[str, list[str]] = {}
            for kind, identity in connection.execute(
                select(tombstones.c.target_kind, tombstones.c.target_id).where(
                    tombstones.c.operation_id == operation
                )
            ):
                items.setdefault(kind, []).append(identity)
            connection.exec_driver_sql("PRAGMA secure_delete=ON")
            triggers = list(
                connection.exec_driver_sql(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND "
                    "tbl_name IN ('entity_revisions','evidence_revisions',"
                    "'audience_collection_members') "
                    "AND upper(sql) LIKE '%BEFORE UPDATE%'"
                ).all()
            )
            for name, _ in triggers:
                if not name.isidentifier():
                    raise StorageIntegrityError("Unexpected history trigger; redaction refused")
                connection.exec_driver_sql(f'DROP TRIGGER "{name}"')
            document = {
                "redacted": True,
                "reason": "authorized audience erasure",
                "operation_id": operation,
            }
            for table_name, kind, value_column in (
                ("entity_revisions", "entity_revision", "payload_json"),
                ("evidence_revisions", "evidence_revision", "locator_json"),
            ):
                table = metadata.tables[table_name]
                connection.execute(
                    table.update()
                    .where(table.c.id.in_(items.get(kind, [])))
                    .values(
                        **{
                            value_column: canonical_json(document),
                            "content_hash": hash_config(document),
                        }
                    )
                )
            connection.execute(
                metadata.tables["comments"]
                .update()
                .where(metadata.tables["comments"].c.id.in_(items.get("comment", [])))
                .values(body="[redacted]")
            )
            members = metadata.tables["audience_collection_members"]
            connection.execute(
                members.update()
                .where(
                    members.c.collection_revision_id.in_(items.get("entity_revision", [])),
                    members.c.exclusion_reason.is_not(None),
                )
                .values(exclusion_reason="[redacted]")
            )
            revisions = metadata.tables["entity_revisions"]
            source_ids = set(
                connection.scalars(
                    select(revisions.c.source_id).where(
                        revisions.c.id.in_(items.get("entity_revision", []))
                    )
                )
            )
            for source_id in source_ids - {None}:
                source = metadata.tables["source_records"]
                row = connection.execute(
                    select(source.c.terms_json).where(source.c.id == source_id)
                ).scalar_one()
                terms = {
                    "redacted_metadata": True,
                    "comments_permitted": bool(json.loads(row).get("comments_permitted")),
                }
                connection.execute(
                    source.update()
                    .where(source.c.id == source_id)
                    .values(
                        source_uri="socialdna:redacted-source/" + source_id,
                        terms_json=canonical_json(terms),
                        permission_basis="redacted authority metadata",
                    )
                )
            provenance = metadata.tables["provenance_records"]
            connection.execute(
                provenance.update()
                .where(provenance.c.source_record_id.in_(source_ids - {None}))
                .values(
                    config_json=canonical_json(document),
                    provider_name=None,
                    model_name=None,
                    model_revision=None,
                )
            )
            table = metadata.tables["statistical_analyses"]
            connection.execute(
                table.update()
                .where(table.c.id.in_(items.get("statistical_analysis", [])))
                .values(result_json=canonical_json(document))
            )
            for _, sql in triggers:
                connection.exec_driver_sql(sql)
            objects = metadata.tables["artifact_objects"]
            blobs = list(
                connection.scalars(
                    select(objects.c.relative_path).where(
                        objects.c.id.in_(items.get("artifact", []))
                    )
                )
            )
        for relative in blobs:
            ArtifactStore(paths).path_for(relative).unlink(missing_ok=True)
        # No active read transaction on this dedicated native connection. Secure
        # delete + vacuum/checkpoint removes old text from the active DB/WAL too.
        with database.engine.connect() as connection:
            driver = connection.connection.driver_connection
            assert driver is not None
            if driver.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
                raise StorageIntegrityError("Redaction checkpoint is busy; cleanup remains pending")
            driver.execute("VACUUM")
            if driver.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
                raise StorageIntegrityError("Redaction checkpoint is busy; cleanup remains pending")
        with database.transaction() as connection:
            connection.execute(
                journal.update()
                .where(journal.c.id == operation)
                .values(status="complete", completed_at=utc_now())
            )
