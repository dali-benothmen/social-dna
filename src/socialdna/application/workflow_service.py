"""Resumable source-report orchestration; no network under the writer lock."""

import os
import sqlite3
from typing import Any

import httpx
from sqlalchemy import select

from socialdna.application import workflow_maintenance
from socialdna.application.bootstrap import open_application
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import (
    ConfigurationError,
    DependencyUnavailable,
    StorageConflict,
    StoragePermissionError,
)
from socialdna.domain.acquisition import POLICY_VERSION, CaptureFailure
from socialdna.domain.workflows import RequiredAction, WorkflowPlan, WorkflowRequest
from socialdna.ingestion.connectors import youtube
from socialdna.ingestion.urls import parse_url
from socialdna.storage import workflow_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata


def _reference_plan(settings: Settings, identity: str) -> WorkflowPlan:
    path = DataPaths(settings.data_dir).database
    if not path.is_file():
        raise ConfigurationError("No saved workflow library exists")
    try:
        with immutable_snapshot(path) as connection:
            row = connection.execute(
                "SELECT plan_json FROM workflow_sessions WHERE id=?", (identity,)
            ).fetchone()
        if row is None:
            raise ConfigurationError("Unknown saved workflow reference")
        return WorkflowPlan.model_validate_json(row[0])
    except sqlite3.Error:
        raise ConfigurationError("Cannot inspect the saved workflow in this library") from None


def plan(settings: Settings, request: WorkflowRequest, *, dry_run: bool = False) -> dict[str, Any]:
    if request.mode == "ingest":
        assert request.url is not None
        target = parse_url(request.url)
        request = request.model_copy(update={"url": target.canonical_url})
        platform, kind, external_id, url = (
            target.platform,
            target.kind,
            target.external_id,
            target.canonical_url,
        )
    else:
        assert request.from_workflow is not None
        previous = _reference_plan(settings, request.from_workflow)
        platform, kind, external_id, url = (
            previous.platform,
            previous.target_kind,
            previous.external_id,
            previous.canonical_url,
        )
    supported = platform == "youtube" and kind == "post"
    specification = WorkflowPlan(
        request=request,
        platform=platform,
        target_kind=kind,
        external_id=external_id,
        canonical_url=url,
        supported=supported,
        policy_version=POLICY_VERSION,
        response_byte_limit=settings.workflow_response_byte_limit,
        request_timeout_seconds=settings.workflow_request_timeout_seconds,
        retention_days=settings.workflow_retention_days,
        operations=("capture_native_metadata", "canonical_identity_import", "compose_native_report")
        if request.mode == "ingest"
        else ("compose_saved_native_report",),
        limitations=(
            "Source-only: no audiovisual analysis, private analytics or derived research.",
            "Only one YouTube post is collectable; "
            "recognized profiles/other platforms remain planned.",
            "Live capture requires an API key and verified scheduled retention maintenance.",
        ),
    )
    if dry_run:
        return {"dry_run": True, "written": False, "plan": specification.model_dump(mode="json")}
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            identity = repository.create(connection, specification)
    return {
        "workflow_id": identity,
        "state": "planned",
        "plan": specification.model_dump(mode="json"),
        "network_attempted": False,
        "written": True,
    }


def show(settings: Settings, identity: str) -> dict[str, Any]:
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            row, specification = repository.get(connection, identity)
            attempts = metadata.tables["workflow_attempts"]
            history = [
                dict(item)
                for item in connection.execute(
                    select(attempts)
                    .where(attempts.c.workflow_id == identity)
                    .order_by(attempts.c.attempt_no)
                ).mappings()
            ]
            bound = repository.bindings(connection, identity)
    return {
        "workflow_id": identity,
        "state": row["state"],
        "action_code": row["action_code"],
        "plan": specification.model_dump(mode="json"),
        "attempts": history,
        "bindings": bound,
    }


def _await(settings: Settings, identity: str, code: str, message: str) -> dict[str, Any]:
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            repository.state(connection, identity, "awaiting_action", code)
    return {
        "workflow_id": identity,
        "state": "awaiting_action",
        "status": "partial",
        "required_actions": [RequiredAction(code=code, message=message).model_dump()],
        "network_attempted": False,
        "limitations": [message],
    }


def run(settings: Settings, identity: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    from socialdna.application.workflow_report_service import generate

    with open_application(settings) as application:
        with application.database.transaction() as connection:
            _, specification = repository.get(connection, identity)
            bound = repository.bindings(connection, identity)
        if any(item["role"] == "capture" for item in bound):
            result = generate(application, identity)
            with application.database.transaction() as connection:
                repository.state(
                    connection,
                    identity,
                    "partial" if result["status"] == "partial" else "completed",
                )
            return {
                **result,
                "state": "partial" if result["status"] == "partial" else "completed",
                "network_attempted": False,
                "reused": True,
            }
        if specification.request.mode == "report":
            with application.database.transaction() as connection:
                parent = specification.request.from_workflow
                assert parent is not None
                repository.get(connection, parent)
                previous = repository.bindings(connection, parent)
                selected = [
                    item for item in previous if item["role"] in {"capture", "account", "post"}
                ]
                if not any(item["role"] == "capture" for item in selected):
                    raise ConfigurationError(
                        "The saved input has no committed capture; no network request was made"
                    )
                repo = EvidenceRepository(connection)
                for item in selected:
                    ref = repo.ref(repo.get("entity_revisions", item["revision_id"]))
                    repository.bind(connection, identity, item["role"], ref, item["capture_id"])
            result = generate(application, identity)
            with application.database.transaction() as connection:
                repository.state(
                    connection,
                    identity,
                    "partial" if result["status"] == "partial" else "completed",
                )
            return {**result, "network_attempted": False}
    if not specification.supported:
        _await(
            settings,
            identity,
            "source_not_implemented",
            "Only a YouTube post's native metadata is collectable in this release.",
        )
        raise DependencyUnavailable(
            "The recognized platform/target has no implemented acquisition route"
        )
    if specification.policy_version != POLICY_VERSION:
        return _await(
            settings,
            identity,
            "policy_changed",
            "Create a new plan under the current source policy.",
        )
    if settings.offline:
        return _await(
            settings,
            identity,
            "offline",
            "This plan requires network access; --offline prevented acquisition.",
        )
    key = os.environ.get(settings.youtube_api_key_env, "")
    if not key or len(key) > 512 or any(ord(character) < 33 for character in key):
        return _await(
            settings,
            identity,
            "api_key_required",
            "Configure a valid YouTube Data API key in the local secret environment variable "
            + settings.youtube_api_key_env
            + "; never paste it in a prompt or CLI argument.",
        )
    if not workflow_maintenance.verified(settings):
        return _await(
            settings,
            identity,
            "maintenance_required",
            "Export workflow maintenance units and explicitly install/activate the matching "
            "systemd user timer before retaining API data. No host settings were changed.",
        )
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            _, fresh_plan = repository.get(connection, identity)
            if fresh_plan != specification:
                raise StorageConflict("The acquisition plan changed before its reservation")
            if any(item["role"] == "capture" for item in repository.bindings(connection, identity)):
                raise StorageConflict("Another worker committed this capture; resume the workflow.")
            token = repository.claim(
                connection, identity, specification, specification.request_timeout_seconds
            )
    try:
        # No application context/SQLite/vector handle survives this network interval.
        captured = youtube.fetch(
            specification.external_id,
            key,
            retention_days=specification.retention_days,
            max_bytes=specification.response_byte_limit,
            timeout=specification.request_timeout_seconds,
            client=client,
        )
        if not workflow_maintenance.verified(settings):
            raise CaptureFailure(
                "maintenance_changed", "Retention maintenance changed during acquisition."
            )
        with open_application(settings) as application:
            with application.database.transaction() as connection:
                repository.commit_capture(application, connection, identity, token, captured)
            result = generate(application, identity)
            with application.database.transaction() as connection:
                repository.state(
                    connection,
                    identity,
                    "partial" if result["status"] == "partial" else "completed",
                )
        return {**result, "network_attempted": True, "reused": False}
    except CaptureFailure as exc:
        with open_application(settings) as application:
            with application.database.transaction() as connection:
                repository.fail(connection, identity, token, exc.code, retry_after=exc.retry_after)
        if exc.permission:
            raise StoragePermissionError(exc.message) from None
        return {
            "workflow_id": identity,
            "state": "awaiting_action",
            "status": "partial",
            "network_attempted": True,
            "required_actions": [RequiredAction(code=exc.code, message=exc.message).model_dump()],
            "limitations": [exc.message],
        }
    except BaseException as exc:
        with open_application(settings) as application:
            with application.database.transaction() as connection:
                repository.fail(
                    connection,
                    identity,
                    token,
                    "interrupted"
                    if isinstance(exc, KeyboardInterrupt)
                    else "capture_not_committed",
                    cancelled=isinstance(exc, KeyboardInterrupt),
                )
        raise
