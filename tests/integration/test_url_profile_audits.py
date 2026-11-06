import json
import subprocess
import sys

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.profile_audit_service import observe
from socialdna.application.workflow_report_service import generate
from socialdna.core.exceptions import ConfigurationError, SocialDNAError
from socialdna.domain.profile_audit import ProfileAuditProposal
from socialdna.domain.workflows import WorkflowRequest
from socialdna.storage.schema import metadata

URL = "https://www.instagram.com/example/"


def observation(settings, **kwargs):
    return observe(
        settings,
        URL,
        external_id="stable-123",
        captured_at="2025-01-01T00:00:00Z",
        permission_basis="authorized_export",
        source_description="Consented independent profile observation",
        **kwargs,
    )


def audit(settings, snapshot, **kwargs):
    identity = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="analyze",
            scope="profile",
            url=URL,
            profile_revision=snapshot["snapshot"]["revision_id"],
            **kwargs,
        ),
    )["workflow_id"]
    return identity, workflow_service.run(settings, identity)


@pytest.mark.parametrize("focus", ["balanced", "strengths", "improvements"])
def test_exact_cited_profile_checks_reopen_no_crawl_and_separate_conversion(
    settings, tmp_path, focus
):
    photo = tmp_path / "profile.png"
    Image.new("RGB", (80, 60), "red").save(photo)
    source = observation(
        settings, username="example", display_name="Creator", bio="", photo=photo, links_empty=True
    )
    identity, result = audit(
        settings, source, audit_focus=focus, goal="Find strengths and weaknesses"
    )
    report = ProfileAuditProposal.model_validate(result["content"])
    assert report.status == "partial" and not result["network_attempted"]
    assert report.review_state == "unreviewed_proposal" and report.conversion_effect is None
    assert report.photo_measurements["width"] == 80
    fields = {f.field: f for f in report.findings}
    assert fields["display_name"].direction == "strength"
    assert fields["bio"].direction == "weakness"
    assert fields["pins"].direction == "unknown"
    with open_application(settings) as app:
        from socialdna.application.evidence_service import EvidenceResolver

        with app.database.transaction() as connection:
            for finding in report.findings:
                assert (
                    EvidenceResolver(connection)
                    .resolve(finding.evidence[0], purpose="new_claim")
                    .subject
                    == report.snapshot
                )
            assert connection.execute(select(metadata.tables["posts"])).all() == []
        assert generate(app, identity)["content"] == result["content"]
        assert "Unreviewed" in generate(app, identity, "markdown")["content"]
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
    with pytest.raises(ValidationError):
        ProfileAuditProposal.model_validate({**result["content"], "review_state": "human_reviewed"})


def test_refresh_is_explicit_preserves_history_and_reports_staleness(settings):
    old = observation(settings, bio="Original")
    identity, result = audit(settings, old)
    changed = observe(
        settings,
        URL,
        external_id="stable-123",
        captured_at="2025-02-01T00:00:00Z",
        permission_basis="authorized_export",
        source_description="New permitted observation",
        bio="Changed",
    )
    with open_application(settings) as app:
        saved = generate(app, identity)
        assert saved["content"] == result["content"] and saved["freshness"]["stale"]
    other, new_result = audit(settings, changed)
    assert other != identity and new_result["content"]["snapshot"] != result["content"]["snapshot"]


def test_withdrawal_and_erasure_withhold_proposals_and_managed_photo(settings, tmp_path):
    from socialdna.storage.audience_retention import begin, preview, resume

    photo = tmp_path / "photo.png"
    Image.new("RGB", (40, 40), "blue").save(photo)
    source = observation(settings, bio="Erase exact biography", photo=photo)
    identity, _ = audit(settings, source)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            plan = preview(connection, source_id=source["source_id"])
            begin(
                connection,
                plan,
                confirmation=plan["confirmation"],
                reason="Owner deletion",
                actor="test-owner",
            )
        resume(app.database, app.paths)
        with pytest.raises(SocialDNAError):
            generate(app, identity)
        with app.database.transaction() as connection:
            rows = list(
                connection.scalars(select(metadata.tables["entity_revisions"].c.payload_json))
            )
            assert not any("Erase exact biography" in text for text in rows)
    assert photo.is_file()  # External originals remain the operator's responsibility.


def test_uncollected_not_empty_wrong_subject_and_cold_profile(settings):
    empty = observation(settings, bio="")
    _, report = audit(settings, empty)
    assert (
        next(f for f in report["content"]["findings"] if f["field"] == "category")["direction"]
        == "unknown"
    )
    with pytest.raises(ConfigurationError):
        observe(
            settings,
            "https://www.youtube.com/channel/UC" + "a" * 22,
            external_id="different",
            captured_at="2025-01-01T00:00:00Z",
            permission_basis="public_permitted",
            source_description="Observed",
        )
    wrong = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="analyze",
            scope="profile",
            url="https://www.instagram.com/other/",
            profile_revision=empty["snapshot"]["revision_id"],
        ),
    )["workflow_id"]
    with pytest.raises(ConfigurationError, match="another URL"):
        workflow_service.run(settings, wrong)
    cold = workflow_service.plan(
        settings, WorkflowRequest(mode="analyze", scope="profile", url=URL)
    )["workflow_id"]
    assert (
        workflow_service.run(settings, cold)["required_actions"][0]["code"]
        == "profile_observation_required"
    )
