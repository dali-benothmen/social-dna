import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.workflow_report_service import generate
from socialdna.core.exceptions import ConfigurationError, StorageConflict
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.workflows import WorkflowRequest
from socialdna.storage.schema import metadata

URL = "https://www.youtube.com/shorts/EaYRjrQuxEk"


def request(*paths: Path, **kwargs) -> WorkflowRequest:
    return WorkflowRequest(
        mode="analyze",
        url=URL,
        media=tuple(str(p) for p in paths),
        permission_basis="creator_owned_original",
        analysis_options=AnalysisOptions(no_ai=True, max_frames=4, depth="quick"),
        **kwargs,
    )


def test_assisted_video_subtitles_persistence_cache_and_report_task(settings, video, subtitles):
    settings.offline = True
    identity = workflow_service.plan(settings, request(video, subtitles=str(subtitles)))[
        "workflow_id"
    ]
    result = workflow_service.run(settings, identity)
    assert result["coverage"] == "media-enriched-assisted" and not result["network_attempted"]
    assert result["content"]["analyses"][0]["report"]["timeline"]["frames"]
    assert result["content"]["analyses"][0]["report"]["timeline"]["text_segments"]
    assert workflow_service.run(settings, identity)["content"] == result["content"]
    with open_application(settings) as app:
        markdown = generate(app, identity, "markdown")
        assert "Assisted" in markdown["content"]
        with app.database.transaction() as connection:
            row = (
                connection.execute(
                    select(metadata.tables["posts"]).where(
                        metadata.tables["posts"].c.platform == "youtube"
                    )
                )
                .mappings()
                .one()
            )
            assert row["account_id"] is None and row["published_at"] is None
    report_id = workflow_service.plan(
        settings, WorkflowRequest(mode="report", from_workflow=identity)
    )["workflow_id"]
    assert workflow_service.run(settings, report_id)["content"] == result["content"]


def test_image_and_ordered_mixed_carousel_are_real_and_qualified(settings, tmp_path, video):
    image = tmp_path / "owned.png"
    Image.new("RGB", (80, 60), "red").save(image)
    identity = workflow_service.plan(settings, request(image))["workflow_id"]
    result = workflow_service.run(settings, identity)
    assert result["content"]["analyses"][0]["kind"] == "image"
    carousel = workflow_service.plan(settings, request(image, image, replace_media=True))[
        "workflow_id"
    ]
    result = workflow_service.run(settings, carousel)
    items = result["content"]["analyses"][0]["report"]["items"]
    assert [i["position"] for i in items] == [0, 1]
    assert items[1]["duplicate_of"] == 0
    mixed = workflow_service.plan(settings, request(image, video, replace_media=True))[
        "workflow_id"
    ]
    result = workflow_service.run(settings, mixed)
    assert result["status"] == "partial"
    assert result["content"]["analyses"][0]["report"]["items"][1]["status"] == "unavailable"


def test_permission_hash_change_conflict_and_cold_url_are_not_bypassed(settings, tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (80, 60), "red").save(image)
    with pytest.raises(ValidationError):
        WorkflowRequest(mode="analyze", url=URL, media=(str(image),))
    identity = workflow_service.plan(settings, request(image))["workflow_id"]
    workflow_service.run(settings, identity)
    Image.new("RGB", (80, 60), "blue").save(image)
    with pytest.raises(ConfigurationError, match="changed"):
        workflow_service.run(settings, identity)
    other = workflow_service.plan(settings, request(image))["workflow_id"]
    with pytest.raises(StorageConflict):
        workflow_service.run(settings, other)
    cold = workflow_service.plan(settings, WorkflowRequest(mode="analyze", url=URL))["workflow_id"]
    result = workflow_service.run(settings, cold)
    assert result["status"] == "partial" and not result["network_attempted"]


def test_interrupted_video_reuses_checkpoint_and_erasure_scrubs_text(
    settings, video, subtitles, monkeypatch
):
    from socialdna.application import analysis_service
    from socialdna.storage import content_repository as records
    from socialdna.storage.audience_retention import begin, preview, resume
    from socialdna.storage.evidence_repository import EvidenceRepository

    identity = workflow_service.plan(settings, request(video, subtitles=str(subtitles)))[
        "workflow_id"
    ]
    original = analysis_service.analyze_video

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after actual run commit")

    monkeypatch.setattr(analysis_service, "analyze_video", interrupted)
    with pytest.raises(RuntimeError, match="actual run"):
        workflow_service.run(settings, identity)
    monkeypatch.setattr(analysis_service, "analyze_video", original)
    result = workflow_service.run(settings, identity)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            checkpoint = records.records(connection, identity, "content_run")
            assert len(checkpoint) == 1
            binding = records.records(connection, identity, "content_binding")[0]
            source = EvidenceRepository(connection).entity(binding)["source_id"]
            plan = preview(connection, source_id=source)
            begin(
                connection,
                plan,
                confirmation=plan["confirmation"],
                reason="Owner deletion",
                actor="test-owner",
            )
        resume(app.database, app.paths)
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError):
            generate(app, identity)
        with app.database.transaction() as connection:
            assert all(
                "useful opening" not in text.casefold()
                for text in connection.scalars(select(metadata.tables["text_segments"].c.text))
            )
    assert result["content"]["binding"]["revision_id"] == binding.revision_id


def test_dry_run_and_show_do_not_analyze_or_initialize(settings, tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (80, 60), "red").save(image)
    assert workflow_service.plan(settings, request(image), dry_run=True)["dry_run"]
    assert not settings.data_dir.exists()
    identity = workflow_service.plan(settings, request(image))["workflow_id"]
    shown = workflow_service.show(settings, identity)
    assert shown["state"] == "planned" and not shown["bindings"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/p/ABC123/",
        "https://www.tiktok.com/@creator/video/1234567890123456789",
    ],
)
def test_supplied_original_cli_reopens_in_a_fresh_process(settings, tmp_path, url):
    image = tmp_path / "authorized image.png"
    Image.new("RGB", (40, 30), "red").save(image)
    base = [
        sys.executable,
        "-m",
        "socialdna",
        "--data-dir",
        str(settings.data_dir),
        "--offline",
        "--format",
        "json",
    ]

    def cli(*arguments):
        result = subprocess.run([*base, *arguments], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)["data"]

    identity = cli(
        "workflow",
        "plan",
        "--mode",
        "analyze",
        "--url",
        url,
        "--media",
        str(image),
        "--permission-basis",
        "authorized_analysis",
    )["workflow_id"]
    first = cli("workflow", "run", identity)
    saved = cli("workflow", "report", identity)
    assert first["content"] == saved["content"]
    assert not saved["network_attempted"]
    assert saved["content"]["request_fulfilled"]


def test_withdrawal_blocks_frozen_content_and_unanswered_goal_is_partial(settings, tmp_path):
    from socialdna.application.evidence_service import withdraw
    from socialdna.storage import content_repository as records
    from socialdna.storage.evidence_repository import EvidenceRepository

    image = tmp_path / "image.png"
    Image.new("RGB", (40, 30), "red").save(image)
    identity = workflow_service.plan(settings, request(image, goal="Why did this go viral?"))[
        "workflow_id"
    ]
    result = workflow_service.run(settings, identity)
    assert result["status"] == "partial" and result["required_actions"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            binding = records.records(connection, identity, "content_binding")[0]
            withdraw(
                connection,
                source_id=EvidenceRepository(connection).entity(binding)["source_id"],
                reason="Permission revoked",
            )
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError):
            generate(app, identity)


def test_old_plan_fingerprint_is_not_rehashed_with_new_defaults(settings):
    from socialdna.core.hashing import canonical_json, hash_config

    identity = workflow_service.plan(settings, WorkflowRequest(url=URL))["workflow_id"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            table = metadata.tables["workflow_sessions"]
            raw = json.loads(
                connection.scalar(select(table.c.plan_json).where(table.c.id == identity))
            )
            raw.pop("media_inputs")
            raw.pop("subtitles_sha256")
            for name in (
                "scope",
                "media",
                "permission_basis",
                "copy_media",
                "replace_media",
                "subtitles",
                "analysis_options",
            ):
                raw["request"].pop(name)
            connection.execute(
                table.update()
                .where(table.c.id == identity)
                .values(
                    plan_json=canonical_json(raw),
                    request_json=canonical_json(raw["request"]),
                    plan_hash=hash_config(raw),
                )
            )
    assert workflow_service.show(settings, identity)["state"] == "planned"


def test_api_capture_withdrawal_does_not_launder_or_erase_independent_original(
    settings, tmp_path, monkeypatch
):
    import httpx

    from socialdna.application.evidence_service import withdraw
    from socialdna.storage import workflow_repository

    monkeypatch.setenv(settings.youtube_api_key_env, "synthetic-test-key")
    monkeypatch.setattr("socialdna.application.workflow_maintenance.verified", lambda _: True)
    native = workflow_service.plan(settings, WorkflowRequest(url=URL))["workflow_id"]
    response = {
        "items": [
            {
                "id": "EaYRjrQuxEk",
                "snippet": {
                    "channelId": "UC" + "z" * 22,
                    "title": "API-only title",
                    "publishedAt": "2026-01-01T00:00:00Z",
                },
                "statistics": {"viewCount": "123"},
            }
        ]
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response))
    ) as client:
        workflow_service.run(settings, native, client=client)
    image = tmp_path / "independent.png"
    Image.new("RGB", (40, 30), "red").save(image)
    assisted = workflow_service.plan(settings, request(image))["workflow_id"]
    first = workflow_service.run(settings, assisted)
    assert "API-only title" not in json.dumps(first["content"])
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            binding = next(
                item
                for item in workflow_repository.bindings(connection, native)
                if item["role"] == "capture"
            )
            _, manifest = workflow_repository.load_capture(connection, binding["capture_id"])
            source = connection.scalar(
                select(metadata.tables["acquisition_captures"].c.source_id).where(
                    metadata.tables["acquisition_captures"].c.id == binding["capture_id"]
                )
            )
            assert manifest.fields
            withdraw(connection, source_id=source, reason="Native capture revoked")
    with open_application(settings) as app:
        assert generate(app, assisted)["content"] == first["content"]
        with pytest.raises(ConfigurationError):
            generate(app, native)
