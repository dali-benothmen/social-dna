"""Resumable source-report orchestration; no network under the writer lock."""

import json
import os
import sqlite3
from pathlib import Path
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
from socialdna.domain.workflows import MediaInput, RequiredAction, WorkflowPlan, WorkflowRequest
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
                "SELECT plan_json,request_json,plan_hash FROM workflow_sessions WHERE id=?",
                (identity,),
            ).fetchone()
        if row is None:
            raise ConfigurationError("Unknown saved workflow reference")
        from socialdna.core.hashing import hash_config

        raw = json.loads(row[0])
        if hash_config(raw) != row[2] or raw["request"] != json.loads(row[1]):
            from socialdna.core.exceptions import StorageIntegrityError

            raise StorageIntegrityError("Saved workflow request/plan fingerprint mismatch")
        return WorkflowPlan.model_validate(raw)
    except sqlite3.Error:
        raise ConfigurationError("Cannot inspect the saved workflow in this library") from None


def plan(settings: Settings, request: WorkflowRequest, *, dry_run: bool = False) -> dict[str, Any]:
    if request.mode in ("ingest", "analyze") or (request.mode == "reconstruct" and request.url):
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
    media_inputs: tuple[MediaInput, ...] = ()
    subtitle_hash: str | None = None
    if request.mode == "analyze" or (request.mode == "reconstruct" and request.url):
        from socialdna.application.content_workflow_service import inputs

        media_inputs, subtitle_hash = inputs(settings, request)
        request = request.model_copy(
            update={
                "goal": "Analyze the supplied content with measured evidence."
                if request.mode == "analyze"
                and request.goal == "Capture the source's native public metadata."
                else request.goal,
                "media": tuple(item.path for item in media_inputs),
                "subtitles": str(Path(request.subtitles).expanduser().resolve())
                if request.subtitles
                else None,
            }
        )
        supported = kind == "post" and request.scope == "content" and bool(media_inputs)
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
        media_inputs=media_inputs,
        subtitles_sha256=subtitle_hash,
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
    if request.mode == "analyze":
        specification = specification.model_copy(
            update={
                "operations": (
                    "bind_supplied_originals",
                    "analyze_content",
                    "compose_assisted_report",
                ),
                "retention_days": None,
                "policy_version": "supplied-original-association-v1",
                "limitations": (
                    "Assisted originals only; no URL media acquisition or profile auditing.",
                    "Association/permission is declared, not verified publisher ownership.",
                ),
            }
        )
    if request.mode == "reconstruct":
        from socialdna.application.reconstruction_service import parent_report

        pinned = parent_report(settings, request.from_workflow) if request.from_workflow else None
        request = request.model_copy(
            update={
                "goal": "Reconstruct the finished video from available evidence."
                if request.goal == "Capture the source's native public metadata."
                else request.goal
            }
        )
        specification = specification.model_copy(
            update={
                "request": request,
                "parent_report": pinned,
                "supported": kind == "post"
                and request.scope == "content"
                and (
                    pinned is not None
                    or (len(media_inputs) == 1 and media_inputs[0].media_type == "video")
                ),
                "operations": (
                    ("bind_supplied_originals", "analyze_content") if media_inputs else ()
                )
                + ("select_actual_tracks", "compose_finished_video_reconstruction"),
                "retention_days": None,
                "policy_version": "supplied-original-reconstruction-v1",
                "limitations": (
                    "Assisted original-media evidence only; no cold media/caption access.",
                    "Finished-clip reconstruction, not original intent or script recovery.",
                ),
            }
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
        if specification.request.mode == "analyze":
            if not specification.supported:
                with application.database.transaction() as connection:
                    repository.state(
                        connection, identity, "awaiting_action", "authorized_media_required"
                    )
                return {
                    "workflow_id": identity,
                    "status": "partial",
                    "network_attempted": False,
                    "required_actions": [
                        {
                            "code": "authorized_media_required",
                            "message": "Supply authorized original media and declare permission. "
                            "Cold URL acquisition and profile scope are not implemented.",
                        }
                    ],
                }
            from socialdna.application.content_workflow_service import run as run_content

            with application.database.transaction() as connection:
                repository.state(connection, identity, "running")
            try:
                return run_content(application, identity, specification)
            except BaseException:
                with application.database.transaction() as connection:
                    repository.state(connection, identity, "partial", "content_interrupted")
                raise
        if specification.request.mode == "reconstruct":
            from socialdna.application.reconstruction_service import run as reconstruct

            with application.database.transaction() as connection:
                repository.state(connection, identity, "running")
            try:
                return reconstruct(application, identity, specification)
            except BaseException:
                with application.database.transaction() as connection:
                    repository.state(connection, identity, "partial", "reconstruction_interrupted")
                raise
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
                _, parent_plan = repository.get(connection, parent)
                previous = repository.bindings(connection, parent)
                if parent_plan.request.mode == "reconstruct" and not any(
                    item["role"] == "report"
                    and EvidenceRepository(connection).get("entity_revisions", item["revision_id"])[
                        "kind"
                    ]
                    == "video_reconstruction"
                    for item in previous
                ):
                    raise ConfigurationError(
                        "The saved reconstruction has no finished script; resume it first"
                    )
                selected = [
                    item for item in previous if item["role"] in {"capture", "account", "post"}
                ]
                if not any(item["role"] == "capture" for item in selected):
                    raise ConfigurationError(
                        "The saved input has no committed capture; no network request was made"
                    )
                repo = EvidenceRepository(connection)
                parent_records = [
                    item
                    for item in previous
                    if item["role"] == "report"
                    and repo.get("entity_revisions", item["revision_id"])["kind"]
                    in ("content_report", "video_reconstruction")
                ]
                if parent_records:
                    selected += parent_records
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
        assert specification.retention_days is not None
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
