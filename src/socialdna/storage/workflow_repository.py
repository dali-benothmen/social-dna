"""Operational checkpoints and cited native captures, committed under the existing lock."""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import ConfigurationError, StorageConflict, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import format_utc, utc_now
from socialdna.domain.acquisition import CaptureManifest
from socialdna.domain.evidence import EntityRef
from socialdna.domain.workflows import WorkflowPlan
from socialdna.ingestion.tabular import Account, ImportRecord, ParsedImport, Post, Source
from socialdna.storage import context_repository as context
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

NATIVE_KINDS = {"acquisition_capture", "workflow_report"}


def get(connection: Connection, identity: str) -> tuple[dict[str, Any], WorkflowPlan]:
    table = metadata.tables["workflow_sessions"]
    row = connection.execute(select(table).where(table.c.id == identity)).mappings().first()
    if row is None:
        raise ConfigurationError("Unknown workflow identity; use the ID returned by workflow plan.")
    plan = WorkflowPlan.model_validate_json(row["plan_json"])
    stored = json.loads(row["plan_json"])
    if hash_config(stored) != row["plan_hash"] or (
        json.loads(row["request_json"]) != stored["request"]
    ):
        raise StorageIntegrityError("Stored workflow request/plan fingerprint mismatch")
    return dict(row), plan


def create(connection: Connection, plan: WorkflowPlan) -> str:
    identity, now = new_id(), utc_now()
    connection.execute(
        metadata.tables["workflow_sessions"]
        .insert()
        .values(
            id=identity,
            request_json=canonical_json(plan.request.model_dump(mode="json")),
            plan_json=canonical_json(plan.model_dump(mode="json")),
            plan_hash=hash_config(plan.model_dump(mode="json")),
            state="planned",
            created_at=now,
            updated_at=now,
        )
    )
    connection.execute(
        metadata.tables["workflow_targets"]
        .insert()
        .values(
            workflow_id=identity,
            platform=plan.platform,
            target_kind=plan.target_kind,
            external_id=plan.external_id,
            canonical_url=plan.canonical_url,
        )
    )
    return identity


def state(connection: Connection, identity: str, value: str, action: str | None = None) -> None:
    table = metadata.tables["workflow_sessions"]
    connection.execute(
        table.update()
        .where(table.c.id == identity)
        .values(
            state=value,
            action_code=action,
            updated_at=utc_now(),
        )
    )


def bind(
    connection: Connection, identity: str, role: str, ref: EntityRef, capture_id: str | None
) -> None:
    EvidenceRepository(connection).entity(ref)
    connection.execute(
        insert(metadata.tables["workflow_bindings"])
        .values(
            workflow_id=identity,
            role=role,
            revision_id=ref.revision_id,
            capture_id=capture_id,
        )
        .on_conflict_do_nothing()
    )


def bindings(connection: Connection, identity: str) -> list[dict[str, Any]]:
    table = metadata.tables["workflow_bindings"]
    return [
        dict(row)
        for row in connection.execute(
            select(table)
            .where(table.c.workflow_id == identity)
            .order_by(table.c.role, table.c.revision_id)
        ).mappings()
    ]


def claim(connection: Connection, identity: str, plan: WorkflowPlan, timeout: float) -> str:
    table = metadata.tables["workflow_attempts"]
    rows = list(
        connection.execute(
            select(table).where(table.c.workflow_id == identity).order_by(table.c.attempt_no)
        ).mappings()
    )
    now = utc_now()
    if rows and rows[-1]["state"] == "running":
        if rows[-1]["deadline_at"] > now:
            raise StorageConflict("This workflow already has a live reserved acquisition attempt.")
        connection.execute(
            table.update()
            .where(table.c.id == rows[-1]["id"])
            .values(
                state="interrupted",
                finished_at=now,
                error_code="interrupted_attempt",
            )
        )
    if rows and rows[-1]["retry_at"] and rows[-1]["retry_at"] > now:
        raise StorageConflict(
            "The saved retry-after checkpoint has not elapsed; no request was made."
        )
    if len(rows) >= plan.request.max_attempts:
        raise ConfigurationError(
            "This workflow exhausted its acquisition attempts; no request was made."
        )
    identity_token = new_id()
    deadline = format_utc(datetime.fromisoformat(now) + timedelta(seconds=timeout + 30))
    connection.execute(
        table.insert().values(
            id=identity_token,
            workflow_id=identity,
            attempt_no=len(rows) + 1,
            state="running",
            started_at=now,
            deadline_at=deadline,
        )
    )
    state(connection, identity, "running")
    return identity_token


def fail(
    connection: Connection,
    identity: str,
    token: str,
    code: str,
    *,
    retry_after: int | None = None,
    cancelled: bool = False,
) -> None:
    table = metadata.tables["workflow_attempts"]
    now = utc_now()
    result = connection.execute(
        table.update()
        .where(table.c.id == token, table.c.workflow_id == identity, table.c.state == "running")
        .values(
            state="interrupted" if cancelled else "failed",
            error_code=code,
            finished_at=now,
            retry_at=format_utc(datetime.fromisoformat(now) + timedelta(seconds=retry_after))
            if retry_after
            else None,
        )
    )
    if result.rowcount:
        state(connection, identity, "cancelled" if cancelled else "awaiting_action", code)


def commit_capture(
    application: Application,
    connection: Connection,
    identity: str,
    token: str,
    manifest: CaptureManifest,
) -> str:
    from socialdna.application.account_import_service import persist_records

    session, plan = get(connection, identity)
    attempt = metadata.tables["workflow_attempts"]
    row = connection.execute(select(attempt).where(attempt.c.id == token)).mappings().first()
    if (
        row is None
        or row["workflow_id"] != identity
        or row["state"] != "running"
        or row["deadline_at"] <= utc_now()
        or session["state"] != "running"
        or manifest.external_id != plan.external_id
        or manifest.expires_at <= utc_now()
    ):
        raise StorageConflict("Acquisition claim/input is stale; captured data was not imported.")
    capture_id = stable_id("source-capture", token)
    channel = manifest.fields["snippet/channelId"]
    published = manifest.fields["snippet/publishedAt"]
    assert channel is not None and published is not None
    source = Source(
        dataset_id="capture-" + capture_id,
        permission_basis="public_permitted",
        source_uri=manifest.source_url,
        terms={
            "provider": manifest.provider,
            "policy_version": manifest.policy_version,
            "expires_at": manifest.expires_at,
            "allowed_operations": list(manifest.allowed_operations),
        },
    )
    # Only identity/publication bindings enter the legacy stores. API titles/counts
    # stay in this qualified capture, never silently become generic analytical metrics.
    records: list[ImportRecord] = [
        Account(record_type="account", platform="youtube", external_id=channel),
        Post(
            record_type="post",
            platform="youtube",
            external_id=manifest.external_id,
            account_external_id=channel,
            published_at=published,
            url=manifest.source_url,
        ),
    ]
    payload = {
        "schema_version": "1.0",
        "source": source.model_dump(),
        "records": [record.model_dump(exclude_unset=True) for record in records],
    }
    parsed = ParsedImport(
        source=source, records=records, rows=[1, 2], raw=canonical_json(payload).encode()
    )
    imported = persist_records(application, connection, parsed)
    repo = EvidenceRepository(connection)
    account = repo.latest("account", imported["account_ids"][0])
    post = repo.latest("post", imported["post_ids"][0])
    assert account is not None and post is not None
    provenance = repo.get("import_batches", imported["batch_id"])["provenance_id"]
    ref = context.save(
        connection,
        "acquisition_capture",
        capture_id,
        {
            "clock": {"captured_at": manifest.captured_at},
            "manifest": manifest.model_dump(mode="json"),
        },
        provenance,
        account=account,
        post=post,
    )
    connection.execute(
        metadata.tables["acquisition_captures"]
        .insert()
        .values(
            id=capture_id,
            attempt_id=token,
            source_id=imported["source_id"],
            revision_id=ref.revision_id,
            expires_at=manifest.expires_at,
            policy_version=manifest.policy_version,
            state="active",
        )
    )
    blob = application.artifacts.put_bytes(
        connection,
        canonical_json(manifest.model_dump(mode="json")).encode(),
        kind="source-capture",
        mime_type="application/json",
    )
    application.artifacts.add_reference(
        connection,
        blob,
        owner_type="entity_revision",
        owner_id=ref.revision_id,
        role="native-capture",
    )
    for role, entity in (("account", account), ("post", post), ("capture", ref)):
        bind(connection, identity, role, entity, capture_id)
    connection.execute(
        attempt.update()
        .where(attempt.c.id == token, attempt.c.state == "running")
        .values(
            state="committed",
            finished_at=utc_now(),
        )
    )
    state(connection, identity, "partial", "report_pending")
    context.cite(connection, ref)
    return capture_id


def load_capture(connection: Connection, capture_id: str) -> tuple[EntityRef, CaptureManifest]:
    from socialdna.ingestion.access_policy import assert_operation
    from socialdna.storage.audience_retention import guard

    table = metadata.tables["acquisition_captures"]
    row = connection.execute(select(table).where(table.c.id == capture_id)).mappings().first()
    if row is None:
        raise ConfigurationError("Unknown capture identity")
    assert_operation(connection, row["source_id"], "native_report")
    guard(connection, "source", row["source_id"])
    repo = EvidenceRepository(connection)
    ref = repo.ref(repo.get("entity_revisions", row["revision_id"]))
    payload = json.loads(repo.entity(ref)["payload_json"])
    manifest = CaptureManifest.model_validate(payload["spec"]["manifest"])
    if manifest.expires_at != row["expires_at"] or manifest.policy_version != row["policy_version"]:
        raise StorageIntegrityError("Capture policy/projection fingerprint mismatch")
    from socialdna.application.evidence_service import EvidenceResolver

    EvidenceResolver(connection).resolve(context.cite(connection, ref), purpose="native_report")
    return ref, manifest
