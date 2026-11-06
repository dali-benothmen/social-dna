import json
import subprocess
import sys

import pytest
from PIL import Image
from sqlalchemy import select

from socialdna.application import workflow_service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.profile_audit_service import observe
from socialdna.application.workflow_report_service import generate
from socialdna.core.exceptions import ConfigurationError, SocialDNAError
from socialdna.domain.account_study import AccountStudy
from socialdna.domain.workflows import WorkflowRequest
from socialdna.storage.schema import metadata

URL = "https://www.instagram.com/example/"


def dataset(
    settings, tmp_path, *, revision=1, count=3, handle="example", media=False, remote=False
):
    records = [
        {"record_type": "account", "platform": "instagram", "external_id": "001", "handle": handle}
    ]
    for i in range(count):
        records.append(
            {
                "record_type": "post",
                "platform": "instagram",
                "external_id": f"post-{i}",
                "account_external_id": "001",
                "content_type": "photo",
                "published_at": f"2025-01-{i + 1:02}T00:00:00Z",
                "title": ("Corrected" if revision > 1 and i == 1 else "Ordinary") + f" post {i}",
                "url": f"https://www.instagram.com/p/post-{i}/",
            }
        )
        if media:
            photo = tmp_path / f"photo-{i}.png"
            if not photo.exists():
                Image.new("RGB", (48, 32), (i * 20, 40, 80)).save(photo)
            records.append(
                {
                    "record_type": "media",
                    "platform": "instagram",
                    "post_external_id": f"post-{i}",
                    "uri": "https://example.invalid/original.mp4" if remote else str(photo),
                }
            )
    payload = {
        "schema_version": "1.0",
        "source": {
            "dataset_id": "observed-account",
            "permission_basis": "creator_owned_export",
            "source_uri": "urn:consented:account",
            "terms": {"revision": revision},
        },
        "records": records,
    }
    path = tmp_path / "account.json"
    path.write_text(json.dumps(payload))
    result = import_dataset(settings, path, "json")
    assert result["valid"], result
    return result


def plan(settings, **kwargs):
    return workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="account", url=URL, goal="Study the ordinary and successful content", **kwargs
        ),
    )["workflow_id"]


def test_bounded_ordinary_sample_exact_manifest_c1_and_process_restart(settings, tmp_path):
    dataset(settings, tmp_path)
    snapshot = observe(
        settings,
        URL,
        external_id="001",
        captured_at="2025-03-01T00:00:00Z",
        permission_basis="creator_owned_export",
        source_description="Consented independent observation",
        bio="A concrete observed bio",
    )
    identity = plan(settings, max_posts=2, context_revisions=(snapshot["snapshot"]["revision_id"],))
    result = workflow_service.run(settings, identity)
    study = AccountStudy.model_validate(result["content"])
    assert (
        study.selected_posts_count == 2
        and study.known_posts_count == 3
        and study.omitted_by_limit == 1
    )
    assert [p.fields["title"] for p in study.posts] == ["Ordinary post 2", "Ordinary post 1"]
    assert study.status == "partial" and study.platform_inventory_complete is False
    assert study.contexts[0]["spec"]["bio"]["value"] == "A concrete observed bio"
    assert not result["network_attempted"]
    assert workflow_service.run(settings, identity)["content"] == result["content"]
    alias = workflow_service.plan(settings, WorkflowRequest(mode="report", from_workflow=identity))[
        "workflow_id"
    ]
    assert workflow_service.run(settings, alias)["content"] == result["content"]
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "workflow",
            "report",
            identity,
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 5, process.stdout + process.stderr
    assert json.loads(process.stdout)["data"]["content"] == result["content"]


def test_explicit_refresh_preserves_old_study_and_reuses_real_media(settings, tmp_path):
    dataset(settings, tmp_path, media=True)
    identity = plan(settings, analyze_media=True, permission_basis="creator_owned_original")
    result = workflow_service.run(settings, identity)
    assert all(
        p["status"] == "media_analyzed" and p["media_report"] for p in result["content"]["posts"]
    )
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            before = list(connection.scalars(select(metadata.tables["analysis_runs"].c.id)))
    dataset(settings, tmp_path, revision=2, count=4, media=True)
    with open_application(settings) as app:
        saved = generate(app, identity)
        assert saved["freshness"]["stale"] and saved["content"] == result["content"]
    new = plan(
        settings,
        refresh_from=identity,
        analyze_media=True,
        permission_basis="creator_owned_original",
    )
    refreshed = workflow_service.run(settings, new)["content"]
    assert len(refreshed["changes"]["new"]) == 1 and len(refreshed["changes"]["changed"]) == 1
    assert len(refreshed["changes"]["reobserved"]) == 2
    assert sum(p["status"] == "media_reused" for p in refreshed["posts"]) == 3
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            after = list(connection.scalars(select(metadata.tables["analysis_runs"].c.id)))
        assert len(set(after) - set(before)) == 1
        assert generate(app, identity)["content"] == result["content"]


def test_interruption_resumes_exact_child_without_silent_gap(settings, tmp_path, monkeypatch):
    from socialdna.application import content_workflow_service

    dataset(settings, tmp_path, count=2, media=True)
    identity = plan(settings, analyze_media=True, permission_basis="creator_owned_original")
    original = content_workflow_service.run
    calls = []

    def interrupted(app, child, specification):
        calls.append(child)
        original(app, child, specification)
        raise RuntimeError("Interrupted after child commit")

    monkeypatch.setattr(content_workflow_service, "run", interrupted)
    with pytest.raises(RuntimeError, match="after child commit"):
        workflow_service.run(settings, identity)
    monkeypatch.setattr(content_workflow_service, "run", original)
    result = workflow_service.run(settings, identity)
    assert len(result["content"]["posts"]) == 2
    with open_application(settings) as app:
        from socialdna.storage.content_repository import active, records

        with app.database.transaction() as connection:
            steps = [
                active(connection, ref) for ref in records(connection, identity, "account_dispatch")
            ]
            assert len(steps) == 2 and calls[0] in {s["child_workflow"] for s in steps}


def test_research_registers_actual_draft_without_certifying_mechanism(settings, tmp_path):
    dataset(settings, tmp_path)
    identity = workflow_service.plan(
        settings,
        WorkflowRequest(mode="research", url=URL, goal="Does curiosity cause viral distribution?"),
    )["workflow_id"]
    result = workflow_service.run(settings, identity)
    report = result["content"]
    assert (
        report["research_state"] == "draft"
        and report["research_question"]["kind"] == "research_question"
    )
    assert not report["request_fulfilled"] and report["status"] == "partial"
    with open_application(settings) as app:
        from socialdna.application.research_service import show_research

        question = show_research(app, report["research_question"]["id"])
        assert question
        with app.database.transaction() as connection:
            assert not connection.execute(
                select(metadata.tables["entity_revisions"]).where(
                    metadata.tables["entity_revisions"].c.kind == "research_assessment"
                )
            ).all()


def test_alias_rename_and_ambiguous_identity_are_not_guessed(settings, tmp_path):
    dataset(settings, tmp_path)
    dataset(settings, tmp_path, revision=2, handle="renamed")
    identity = plan(settings)
    assert workflow_service.run(settings, identity)["content"]["account"]
    observe(
        settings,
        URL,
        external_id="002",
        captured_at="2025-01-01T00:00:00Z",
        permission_basis="authorized_export",
        source_description="Observed reassigned alias",
        username="example",
    )
    with pytest.raises(ConfigurationError, match="Ambiguous"):
        plan(settings)
    assert (
        workflow_service.run(settings, plan(settings, account_external_id="001"))["content"][
            "known_posts_count"
        ]
        == 3
    )


def test_missing_remote_and_changed_media_stay_explicit(settings, tmp_path):
    dataset(settings, tmp_path, count=1, media=True, remote=True)
    identity = plan(settings, analyze_media=True, permission_basis="creator_owned_original")
    result = workflow_service.run(settings, identity)
    assert result["content"]["posts"][0]["status"] == "inspected"
    assert "no downloader" in result["content"]["posts"][0]["reason"]
    dataset(settings, tmp_path, revision=2, count=1, media=True)
    identity = plan(settings, analyze_media=True, permission_basis="creator_owned_original")
    Image.new("RGB", (48, 32), "orange").save(tmp_path / "photo-0.png")
    result = workflow_service.run(settings, identity)
    assert result["content"]["posts"][0]["status"] == "failed"


def test_source_withdrawal_withholds_study_and_draft(settings, tmp_path):
    from socialdna.application.evidence_service import withdraw

    dataset_source = dataset(settings, tmp_path)
    identity = plan(settings)
    workflow_service.run(settings, identity)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            withdraw(connection, source_id=dataset_source["source_id"], reason="Consent revoked")
        with pytest.raises(SocialDNAError):
            generate(app, identity)


def test_original_import_withdrawal_also_withholds_dispatched_child(settings, tmp_path):
    from socialdna.application.evidence_service import withdraw
    from socialdna.storage.content_repository import active, records

    source = dataset(settings, tmp_path, count=1, media=True)
    identity = plan(settings, analyze_media=True, permission_basis="creator_owned_original")
    workflow_service.run(settings, identity)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            step = active(connection, records(connection, identity, "account_dispatch")[0])
            child = step["child_workflow"]
            withdraw(connection, source_id=source["source_id"], reason="Original source revoked")
        with pytest.raises(SocialDNAError):
            generate(app, child)


def test_cold_account_dry_run_never_initializes_or_acquires(settings):
    result = workflow_service.plan(
        settings, WorkflowRequest(mode="research", url=URL, goal="Study this creator"), dry_run=True
    )
    assert not settings.data_dir.exists() and not result["plan"]["supported"]
    identity = plan(settings)
    result = workflow_service.run(settings, identity)
    assert result["required_actions"][0]["code"] == "account_observations_required"
    assert not result["network_attempted"]
