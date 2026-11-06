"""Actual static decoding, canonical citations, cache/reports, ordered partial inputs."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import func, select

from socialdna.application import audience_service
from socialdna.application import image_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.import_service import resolve_media
from socialdna.application.performance_service import _batch_media
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, InvalidMedia
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.images import ImageOptions
from socialdna.domain.media import AnalysisOptions
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import database_checks, evidence_checks
from socialdna.storage.schema import metadata


def supplied(tmp_path: Path, paths: list[Path | str], *, kind: str = "carousel") -> Path:
    path = tmp_path / "owned.json"
    raw = {
        "schema_version": "1.0",
        "source": {
            "dataset_id": "owned-static",
            "source_uri": "urn:owned:static",
            "permission_basis": "creator_owned_export",
        },
        "records": [
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": "owner",
                "niche": "cooking",
            },
            {
                "record_type": "post",
                "platform": "demo",
                "external_id": "post",
                "account_external_id": "owner",
                "content_type": kind,
                "published_at": "2026-01-01T00:00:00Z",
                "caption": "<script>not executable</script> A supplied caption",
                "title": "An actual cooking post",
            },
            {
                "record_type": "tag",
                "platform": "demo",
                "post_external_id": "post",
                "value": "#Recipe",
            },
            *[
                {
                    "record_type": "media",
                    "platform": "demo",
                    "post_external_id": "post",
                    "position": i,
                    "uri": str(value),
                    "alt_text": f"Source description of cooking item {i}",
                }
                for i, value in enumerate(paths)
            ],
        ],
    }
    path.write_text(json.dumps(raw))
    return path


def picture(path: Path, color: str) -> Path:
    Image.new("RGB", (120, 80), color).save(path)
    return path


def cli(settings: Settings, *args: str, expected_exit: int = 0) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            *args,
        ],
        text=True,
        capture_output=True,
        timeout=60,
        env={**os.environ, "PATH": ""},
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    return json.loads(result.stdout)["data"]


def test_static_image_without_ffmpeg_uses_real_regions_and_task_cache(
    settings: Settings, tmp_path: Path
) -> None:
    path = picture(tmp_path / "red.png", "red")
    first = cli(settings, "analyze", "image", str(path), "--copy-media")
    assert first["report_type"] == "image" and first["status"] == "success"
    assert first["features"]["saturation"] == pytest.approx(1)
    with open_application(settings) as app:
        second = service.analyze_image(app, first["media"]["id"])
        assert second["task"]["status"] == "cached"
        assert (
            service.analyze_image(app, first["media"]["id"], resume=second["run_id"])["features"]
            == first["features"]
        )
        with pytest.raises(InvalidMedia, match="Resume"):
            service.analyze_image(
                app,
                first["media"]["id"],
                options=ImageOptions(max_side=512),
                resume=second["run_id"],
            )
        with pytest.raises(InvalidMedia, match="Static images"):
            resolve_media(app, first["media"]["id"])
        with app.database.transaction() as connection:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(first["evidence"]), purpose="new_claim"
            )
            assert resolved.locator_kind == "image_record"
            assert "interval" not in resolved.locator.model_dump()
            assert resolved.locator.region == (0, 0, 1, 1)
            assert (
                connection.scalar(select(func.count()).select_from(metadata.tables["observations"]))
                == 0
            )
            assert (
                connection.scalar(select(func.count()).select_from(metadata.tables["scenes"])) == 0
            )
        assert all(c.status == "ok" for c in database_checks(app) + evidence_checks(app))
        original = generate_report(app, first["run_id"])
    restarted = cli(settings, "report", "generate", "--run", first["run_id"])
    assert restarted["content"] == original["content"]
    path.unlink()
    with open_application(settings) as app:
        assert service.analyze_image(app, first["media"]["id"])["status"] == "success"


def test_ordered_carousel_partial_duplicates_text_and_old_reports(
    settings: Settings, tmp_path: Path
) -> None:
    red = picture(tmp_path / "red.png", "red")
    blue = picture(tmp_path / "blue.png", "blue")
    path = supplied(tmp_path, [red, blue, red, "https://example.invalid/never-downloaded.png"])
    assert import_dataset(settings, path, "json")["valid"]
    post = stable_id("post", "demo", "post")
    with open_application(settings) as app:
        first = service.analyze_carousel(app, post)
        assert first["status"] == "partial"
        assert [i["position"] for i in first["items"]] == [0, 1, 2, 3]
        assert first["items"][2]["duplicate_of"] == 0
        assert first["items"][3]["status"] == "unavailable"
        assert first["items"][0]["alternative_text"]["origin"] == "source_supplied"
        assert first["text"]["hashtags"] == ["recipe"]
        assert first["aggregate"]["coverage"] == 0.75
        assert first["aggregate"]["unique_images"] == 2
        frozen = generate_report(app, first["run_id"])
        markdown = generate_report(app, first["run_id"], "markdown")
        assert "<script>" not in markdown["content"] and "&lt;script&gt;" in markdown["content"]
        limited = service.analyze_carousel(app, post, max_items=1)
        assert limited["aggregate"]["available_images"] == 1
        assert limited["items"][1]["status"] == "budget_skipped"
        with app.database.transaction() as connection:
            for item in first["items"][:3]:
                resolved = EvidenceResolver(connection).resolve(
                    EvidenceRef.model_validate(item["evidence"]), purpose="new_claim", post_id=post
                )
                assert resolved.locator.position == item["position"]
                expected_image = json.loads(
                    EvidenceRepository(connection).get(
                        "entity_revisions", item["image"]["revision_id"]
                    )["payload_json"]
                )
                assert resolved.locator.media.model_dump() == expected_image["media"]
    changed = json.loads(path.read_text())
    rows = [r for r in changed["records"] if r["record_type"] == "media"]
    rows[0]["uri"], rows[1]["uri"] = rows[1]["uri"], rows[0]["uri"]
    path.write_text(json.dumps(changed))
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        reordered = service.analyze_carousel(app, post)
        assert reordered["items"][0]["image"] != first["items"][0]["image"]
        assert (
            reordered["items"][0]["appearance"]["brightness"]
            != first["items"][0]["appearance"]["brightness"]
        )
        assert generate_report(app, first["run_id"])["content"] == frozen["content"]


def test_requested_ocr_missing_does_not_discard_deterministic_measurements(
    settings: Settings, tmp_path: Path
) -> None:
    path = picture(tmp_path / "image.png", "white")
    with open_application(settings) as app:
        report = service.analyze_image(app, str(path), options=ImageOptions(ocr=True))
        assert report["status"] == "partial" and report["ocr"]["status"] == "unavailable"
        assert report["features"]["brightness"] == 1
        assert not report["ocr"]["boxes"]


def test_source_withdrawal_and_confirmed_erasure_remove_static_cache_and_reports(
    settings: Settings, tmp_path: Path
) -> None:
    path = picture(tmp_path / "image.png", "white")
    with open_application(settings) as app:
        first = service.analyze_image(app, str(path))
        reused = service.analyze_image(app, str(path))
        archived = generate_report(app, reused["run_id"])
        with app.database.transaction() as connection:
            source = EvidenceRepository(connection).get(
                "entity_revisions", first["ref"]["revision_id"]
            )["source_id"]
            withdraw(connection, source_id=source, reason="Controlled permission withdrawal")
        with pytest.raises(ConfigurationError):
            service.load_analysis(app, first["run_id"])
        preview = audience_service.redact(app, source_id=source)
        audience_service.redact(
            app,
            source_id=source,
            confirmation=preview["confirmation"],
            reason="Controlled source erasure",
        )
        assert not Path(archived["path"]).exists()
        with app.database.transaction() as connection:
            rows = list(
                connection.scalars(select(metadata.tables["analysis_task_results"].c.result_json))
            )
            assert all(json.loads(row).get("redacted") for row in rows)
        with pytest.raises(ConfigurationError):
            service.analyze_image(app, str(path))


def test_account_photo_and_carousel_batches_are_budgeted(
    settings: Settings, tmp_path: Path
) -> None:
    path = picture(tmp_path / "photo.png", "white")
    source = supplied(tmp_path, [path, path])
    assert import_dataset(settings, source, "json")["valid"]
    with open_application(settings) as app:
        batch = _batch_media(
            app, stable_id("account", "demo", "owner"), AnalysisOptions(no_ai=True), 1, 1
        )
        assert len(batch) == 1 and batch[0]["status"] == "partial"
        assert (
            service.load_analysis(app, batch[0]["media_run_id"])["items"][1]["status"]
            == "budget_skipped"
        )


def test_missing_derivative_is_recomputed_and_changed_original_cannot_reuse_cache(
    settings: Settings, tmp_path: Path
) -> None:
    path = picture(tmp_path / "uncopied.png", "red")
    with open_application(settings) as app:
        first = service.analyze_image(app, str(path))
        with app.database.transaction() as connection:
            artifact = app.artifacts.get(connection, first["artifact_id"])
        app.artifacts.path_for(artifact["relative_path"]).unlink()
        with pytest.raises(InvalidMedia, match="derivative"):
            service.load_analysis(app, first["run_id"])
        rebuilt = service.analyze_image(app, str(path))
        assert rebuilt["task"]["status"] == "succeeded"
        assert rebuilt["artifact_id"] == first["artifact_id"]
        picture(path, "blue")
        with pytest.raises(InvalidMedia, match="bytes changed"):
            service.analyze_image(app, first["media"]["id"])
        assert service.analyze_image(app, str(path))["media"]["id"] != first["media"]["id"]
