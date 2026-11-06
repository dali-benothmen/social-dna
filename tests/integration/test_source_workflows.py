import json
import subprocess

import httpx
import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from socialdna.application import workflow_maintenance, workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, assert_active_inputs
from socialdna.application.workflow_report_service import generate
from socialdna.cli.app import app
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, DependencyUnavailable, StorageConflict
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.workflows import WorkflowRequest
from socialdna.ingestion.connectors import youtube
from socialdna.storage import workflow_repository as repository
from socialdna.storage.schema import metadata

VIDEO = "EaYRjrQuxEk"
URL = "https://www.youtube.com/shorts/" + VIDEO


def response() -> dict:
    return {
        "items": [
            {
                "id": VIDEO,
                "snippet": {
                    "channelId": "UC" + "a" * 22,
                    "channelTitle": "A creator",
                    "title": "A <script> story",
                    "description": "Untrusted; do not execute me",
                    "publishedAt": "2026-01-01T12:00:00Z",
                    "categoryId": "22",
                },
                "contentDetails": {"duration": "PT25S"},
                "statistics": {"viewCount": "100", "likeCount": "0"},
            }
        ]
    }


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIALDNA_YOUTUBE_API_KEY", "local-test-secret")
    monkeypatch.setattr(workflow_maintenance, "verified", lambda _: True)


def make_plan(settings: Settings, **kwargs) -> str:
    return workflow_service.plan(settings, WorkflowRequest(url=URL, **kwargs))["workflow_id"]


def capture(settings: Settings, identity: str) -> dict:
    def handler(request: httpx.Request) -> httpx.Response:
        # A complete second application can open while the request is in progress.
        # This detects accidentally doing HTTP under the process writer lock.
        with open_application(settings):
            pass
        assert str(request.url).startswith(youtube.ENDPOINT + "?")
        assert request.headers["X-Goog-Api-Key"] == "local-test-secret"
        assert "local-test-secret" not in str(request.url)
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return workflow_service.run(settings, identity, client=client)


def test_capture_canonical_citations_reopen_and_frozen_report(settings: Settings, enabled) -> None:
    identity = make_plan(settings)
    result = capture(settings, identity)
    assert result["status"] == "success" and result["network_attempted"]
    assert result["coverage"] == "source-only"
    fields = {item["path"]: item for item in result["content"]["fields"]}
    assert fields["statistics/likeCount"]["value"] == "0"
    assert fields["statistics/commentCount"]["availability"] == "not_returned"
    assert fields["statistics/commentCount"]["value"] is None
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            for item in fields.values():
                ref = EvidenceRef.model_validate(item["evidence"])
                resolved = EvidenceResolver(connection).resolve(ref, purpose="native_report")
                assert resolved.eligible
                with pytest.raises(ConfigurationError):
                    EvidenceResolver(connection).resolve(ref, purpose="new_claim")
            post = metadata.tables["posts"]
            assert connection.scalar(select(func.count()).select_from(post)) == 1
            metric = metadata.tables["metric_observations"]
            assert connection.scalar(select(func.count()).select_from(metric)) == 0
            source_id = connection.scalar(
                select(metadata.tables["acquisition_captures"].c.source_id)
            )
            with pytest.raises(ConfigurationError):
                assert_active_inputs(connection, source_ids=(source_id,))
        markdown = generate(application, identity, "markdown")
        assert "source-only" in markdown["content"] and "<script>" not in markdown["content"]
    offline = settings.model_copy(update={"offline": True})
    again = workflow_service.run(offline, identity)
    assert again["reused"] and not again["network_attempted"]
    assert again["content"] == result["content"]
    shown = workflow_service.show(settings, identity)
    assert len(shown["attempts"]) == 1 and shown["attempts"][0]["state"] == "committed"
    assert {item["role"] for item in shown["bindings"]} == {"capture", "post", "account", "report"}
    assert "local-test-secret" not in json.dumps(shown)


def test_unanswered_goal_stays_partial_and_report_mode_never_fetches(settings, enabled) -> None:
    identity = make_plan(settings, goal="Explain why this video went viral")
    result = capture(settings, identity)
    assert result["status"] == "partial" and not result["content"]["request_fulfilled"]
    offline = settings.model_copy(update={"offline": True})
    report_task = workflow_service.plan(
        offline, WorkflowRequest(mode="report", from_workflow=identity)
    )["workflow_id"]
    saved = workflow_service.run(offline, report_task)
    assert not saved["network_attempted"]
    assert saved["content"]["capture_id"] == result["content"]["capture_id"]
    assert len(workflow_service.show(settings, report_task)["attempts"]) == 0


@pytest.mark.parametrize("missing", ["offline", "key", "maintenance"])
def test_required_actions_do_not_claim_or_contact_source(settings, monkeypatch, missing) -> None:
    monkeypatch.setenv("SOCIALDNA_YOUTUBE_API_KEY", "local-test-secret")
    monkeypatch.setattr(workflow_maintenance, "verified", lambda _: missing != "maintenance")
    if missing == "offline":
        settings.offline = True
    if missing == "key":
        monkeypatch.delenv("SOCIALDNA_YOUTUBE_API_KEY")
    identity = make_plan(settings)
    result = workflow_service.run(settings, identity)
    assert result["status"] == "partial" and not result["network_attempted"]
    assert workflow_service.show(settings, identity)["attempts"] == []


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/example/",
        "https://www.tiktok.com/@creator/video/123",
        "https://www.youtube.com/@creator",
    ],
)
def test_unsupported_targets_are_durable_and_honest(settings, url) -> None:
    identity = workflow_service.plan(settings, WorkflowRequest(url=url))["workflow_id"]
    with pytest.raises(DependencyUnavailable):
        workflow_service.run(settings, identity)
    shown = workflow_service.show(settings, identity)
    assert shown["action_code"] == "source_not_implemented" and not shown["attempts"]


def test_rate_limit_checkpoint_and_concurrent_claim(settings, enabled) -> None:
    identity = make_plan(settings)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                429, headers={"Retry-After": "300"}, text="secret-provider-body"
            )
        )
    ) as client:
        result = workflow_service.run(settings, identity, client=client)
    assert result["status"] == "partial"
    assert "secret-provider-body" not in json.dumps(result)
    with pytest.raises(StorageConflict, match="retry-after"):
        workflow_service.run(settings, identity)
    shown = workflow_service.show(settings, identity)
    assert len(shown["attempts"]) == 1 and not shown["bindings"]
    other = make_plan(settings)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            _, plan = repository.get(connection, other)
            repository.claim(connection, other, plan, 20)
            with pytest.raises(StorageConflict, match="live reserved"):
                repository.claim(connection, other, plan, 20)


def test_commit_failure_rolls_back_canonical_import(settings, enabled, monkeypatch) -> None:
    from socialdna.application import account_import_service

    original = account_import_service.persist_records

    def failing(*args):
        original(*args)
        raise RuntimeError("injected after canonical import")

    monkeypatch.setattr(account_import_service, "persist_records", failing)
    identity = make_plan(settings)
    with pytest.raises(RuntimeError, match="injected"):
        capture(settings, identity)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            for name in ("accounts", "posts", "acquisition_captures", "workflow_bindings"):
                assert (
                    connection.scalar(select(func.count()).select_from(metadata.tables[name])) == 0
                )
    monkeypatch.setattr(account_import_service, "persist_records", original)
    assert capture(settings, identity)["status"] == "success"


def test_expiry_deny_first_scrubs_native_copies_and_prevents_report(settings, enabled) -> None:
    from socialdna.storage.workflow_retention import expire

    identity = make_plan(settings)
    result = capture(settings, identity)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            captures = metadata.tables["acquisition_captures"]
            connection.execute(captures.update().values(expires_at="2000-01-01T00:00:00Z"))
            with pytest.raises(ConfigurationError):
                repository.load_capture(connection, result["content"]["capture_id"])
        assert expire(application.database, application.paths) == 1
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            assert (
                connection.scalar(select(metadata.tables["acquisition_captures"].c.state))
                == "erased"
            )
            rows = connection.execute(select(metadata.tables["entity_revisions"])).mappings()
            assert all("Untrusted; do not execute me" not in row["payload_json"] for row in rows)
            assert connection.scalar(select(metadata.tables["posts"].c.published_at)) is None
        with pytest.raises(ConfigurationError):
            generate(application, identity)
    assert workflow_service.show(settings, identity)["action_code"] == "source_erased"


def test_cli_dry_run_saved_report_and_nonoverwriting_export(settings, tmp_path, enabled) -> None:
    runner = CliRunner()
    absent = tmp_path / "absent"
    result = runner.invoke(
        app,
        [
            "--data-dir",
            str(absent),
            "--offline",
            "--no-ai",
            "--format",
            "json",
            "workflow",
            "plan",
            "--url",
            URL,
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert not absent.exists() and json.loads(result.stdout)["data"]["dry_run"]
    identity = make_plan(settings)
    capture(settings, identity)
    destination = tmp_path / "report.md"
    args = [
        "--data-dir",
        str(settings.data_dir),
        "--offline",
        "--no-ai",
        "workflow",
        "report",
        identity,
        "--format",
        "markdown",
        "--output",
        str(destination),
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["schema_version"] == "1.0"
    assert destination.read_text().startswith("# YouTube")
    assert runner.invoke(app, args).exit_code == 2
    # An actual fresh process can read the saved canonical bindings without any key.
    import sys

    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--offline",
            "--no-ai",
            "workflow",
            "report",
            identity,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout)["data"]["content"]["coverage"] == "source-only"


def test_source_withdrawal_withholds_saved_report(settings, enabled) -> None:
    from socialdna.application.evidence_service import withdraw

    identity = make_plan(settings)
    capture(settings, identity)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            source = connection.scalar(select(metadata.tables["acquisition_captures"].c.source_id))
            withdraw(connection, source_id=source, reason="Permission revoked")
        with pytest.raises(ConfigurationError):
            generate(application, identity)


def test_report_crash_resumes_committed_capture_without_http(settings, enabled, monkeypatch):
    from socialdna.application import workflow_report_service

    identity = make_plan(settings)
    original = workflow_report_service.generate

    def fail(*args, **kwargs):
        raise RuntimeError("interrupted report composition")

    monkeypatch.setattr(workflow_report_service, "generate", fail)
    with pytest.raises(RuntimeError, match="interrupted report"):
        capture(settings, identity)
    shown = workflow_service.show(settings, identity)
    assert shown["state"] == "partial" and shown["action_code"] == "report_pending"
    assert shown["attempts"][0]["state"] == "committed"
    monkeypatch.setattr(workflow_report_service, "generate", original)
    result = workflow_service.run(settings.model_copy(update={"offline": True}), identity)
    assert result["status"] == "success" and not result["network_attempted"]
    assert len(workflow_service.show(settings, identity)["attempts"]) == 1


def test_lifetime_attempt_limit_and_expired_worker_token(settings, enabled):
    identity = make_plan(settings, max_attempts=1)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        assert workflow_service.run(settings, identity, client=client)["status"] == "partial"
    with pytest.raises(ConfigurationError, match="exhausted"):
        workflow_service.run(settings, identity)
    other = make_plan(settings)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response()))
    ) as c:
        manifest = youtube.fetch(VIDEO, "test", client=c)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            _, plan = repository.get(connection, other)
            stale = repository.claim(connection, other, plan, 20)
            table = metadata.tables["workflow_attempts"]
            connection.execute(
                table.update().where(table.c.id == stale).values(deadline_at="2000-01-01T00:00:00Z")
            )
            current = repository.claim(connection, other, plan, 20)
            assert current != stale
            with pytest.raises(StorageConflict, match="stale"):
                repository.commit_capture(application, connection, other, stale, manifest)
            repository.commit_capture(application, connection, other, current, manifest)


def test_restore_reapplies_expiry_before_exposing_source(settings, enabled, tmp_path, monkeypatch):
    from socialdna.storage import workflow_retention
    from socialdna.storage.backup import backup_library, restore_library

    identity = make_plan(settings)
    capture(settings, identity)
    backup = tmp_path / "snapshot"
    backup_library(settings, backup)
    restored = tmp_path / "restored"
    restore_library(backup, restored, withdrawals_from=settings.data_dir)
    monkeypatch.setattr(workflow_retention, "utc_now", lambda: "2099-01-01T00:00:00Z")
    reopened = settings.model_copy(update={"data_dir": restored, "offline": True})
    with open_application(reopened) as application:
        with application.database.transaction() as connection:
            assert (
                connection.scalar(select(metadata.tables["acquisition_captures"].c.state))
                == "erased"
            )
        with pytest.raises(ConfigurationError):
            generate(application, identity)


def test_native_api_sources_do_not_enter_research_memory(settings, enabled):
    from socialdna.memory.lexical import reconcile

    identity = make_plan(settings)
    capture(settings, identity)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            reconcile(connection, limit=5000)
            for name in ("graph_nodes", "graph_edges", "vector_documents"):
                assert (
                    connection.scalar(select(func.count()).select_from(metadata.tables[name])) == 0
                )
            assert connection.exec_driver_sql("SELECT count(*) FROM memory_fts").scalar() == 0


def test_explicit_new_capture_after_erasure_does_not_resurrect_old_report(settings, enabled):
    from socialdna.storage.audience_retention import begin, preview, resume

    first = make_plan(settings)
    old = capture(settings, first)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            source = connection.scalar(select(metadata.tables["acquisition_captures"].c.source_id))
            request = preview(connection, source_id=source)
            begin(
                connection,
                request,
                confirmation=request["confirmation"],
                reason="Explicit source deletion",
                actor="test-user",
            )
        resume(application.database, application.paths)
    second = make_plan(settings)
    fresh = capture(settings, second)
    assert fresh["content"]["capture_id"] != old["content"]["capture_id"]
    assert len(workflow_service.show(settings, second)["attempts"]) == 1
    with open_application(settings) as application:
        with pytest.raises(ConfigurationError):
            generate(application, first)
