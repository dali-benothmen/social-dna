"""Real static pipeline with controlled provider responses, not OCR accuracy claims."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import select
from test_image_analysis import cli, picture, supplied

from socialdna.application import image_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.ids import new_id, stable_id
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.images import ImageOptions
from socialdna.domain.providers import OCRBox, OCRFrame, ProviderIdentity
from socialdna.storage import image_repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


@pytest.mark.parametrize("mode", ["valid", "literal", "wrong_id", "exception"])
def test_ocr_regions_provenance_cache_failure_and_resume(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state: dict[str, Any] = {"mode": mode, "calls": 0}

    def read(request: dict[str, Any]) -> list[OCRFrame]:
        state["calls"] += 1
        with Image.open(request["frames"][0]["path"]) as display:
            assert not display.getexif()
        if state["mode"] == "exception":
            raise RuntimeError("Controlled local inference failure")
        return [
            OCRFrame(
                frame_id=request["frames"][0]["id"]
                if state["mode"] in ("valid", "literal")
                else "unrequested",
                boxes=[
                    OCRBox(
                        text="@artifact:display"
                        if state["mode"] == "literal"
                        else "<b>Actual estimated cooking text</b>",
                        confidence=0.9,
                        points=[(0.1, 0.2), (0.7, 0.2), (0.7, 0.8), (0.1, 0.8)],
                    )
                ],
            )
        ]

    identity = ProviderIdentity(
        provider="controlled-contract-test", model="ocr-fixture", revision="1", execution="local"
    )
    provider = SimpleNamespace(
        identity=identity,
        versions={"runtime": "contract-fixture"},
        manifest=SimpleNamespace(model_dump=lambda: {"identity": identity.model_dump()}),
        read_text=read,
    )
    monkeypatch.setattr(service.ProviderRegistry, "resolve", lambda *args: provider)
    image = picture(tmp_path / "image.png", "white")
    with open_application(settings) as app:
        first = service.analyze_image(app, str(image), options=ImageOptions(ocr=True))
        if mode not in ("valid", "literal"):
            assert first["ocr"]["status"] == "failed" and first["status"] == "partial"
            assert first["features"]["brightness"] == 1
            state["mode"] = "valid"
            fixed = service.analyze_image(
                app, str(image), options=ImageOptions(ocr=True), resume=first["run_id"]
            )
            assert fixed["ocr"]["status"] == "available"
            with app.database.transaction() as connection:
                assert (
                    json.loads(
                        EvidenceRepository(connection).entity(
                            EntityRef.model_validate(first["ref"])
                        )["payload_json"]
                    )["ocr"]["status"]
                    == "failed"
                )
            return
        assert first["ocr"]["status"] == "available"
        with app.database.transaction() as connection:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(first["ocr"]["evidence"][0]),
                purpose="new_claim",
                media_id=first["media"]["id"],
            )
            assert resolved.locator.region == (0.1, 0.2, 0.7, 0.8)
            assert resolved.locator.quote == (
                "@artifact:display" if mode == "literal" else "<b>Actual estimated cooking text</b>"
            )
            assert (
                connection.scalar(
                    select(metadata.tables["provenance_records"].c.provider_name).where(
                        metadata.tables["provenance_records"].c.method == "image.appearance"
                    )
                )
                == identity.provider
            )
            assert connection.scalar(select(metadata.tables["task_citation_inputs"].c.task_id))
        second = service.analyze_image(app, str(image), options=ImageOptions(ocr=True))
        assert second["task"]["status"] == "cached" and state["calls"] == 1
        assert (
            service.analyze_image(app, str(image), options=ImageOptions(ocr=True, no_ai=True))[
                "ocr"
            ]["status"]
            == "disabled"
        )
        assert state["calls"] == 1
        source = supplied(tmp_path, [image, image])
    assert import_dataset(settings, source, "json")["valid"]
    with open_application(settings) as app:
        carousel = service.analyze_carousel(
            app, stable_id("post", "demo", "post"), options=ImageOptions(ocr=True)
        )
        with app.database.transaction() as connection:
            ref = EntityRef.model_validate(carousel["ref"])
            region = image_repository.cite(connection, ref, "ocr", position=1, box_index=0)
            resolved = EvidenceResolver(connection).resolve(region, purpose="new_claim")
            assert resolved.locator.position == 1 and resolved.locator.region == (
                0.1,
                0.2,
                0.7,
                0.8,
            )
        with pytest.raises(StorageIntegrityError, match="mismatched"):
            with app.database.transaction() as connection:
                bad = resolved.locator.model_copy(
                    update={"position": 0, "region": (0.0, 0.0, 0.5, 0.5)}
                )
                repo = EvidenceRepository(connection)
                citation = repo.save_evidence(new_id(), bad, repo.entity(ref)["provenance_id"])
                connection.execute(
                    metadata.tables["static_evidence_bindings"]
                    .insert()
                    .values(
                        evidence_revision_id=citation.revision_id,
                        subject_revision_id=ref.revision_id,
                    )
                )
                EvidenceResolver(connection).resolve(citation)


def test_mixed_missing_and_gapped_carousel_items_remain_explicit(
    settings: Settings, tmp_path: Path, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = supplied(
        tmp_path,
        [
            picture(tmp_path / "red.png", "red"),
            video,
            tmp_path / "missing.png",
            picture(tmp_path / "blue.png", "blue"),
        ],
    )
    raw = json.loads(source.read_text())
    rows = [r for r in raw["records"] if r["record_type"] == "media"]
    for row, position in zip(rows, (0, 2, 3, 6), strict=True):
        row["position"] = position
    source.write_text(json.dumps(raw))
    imported = import_dataset(settings, source, "json")
    assert imported["valid"]
    with open_application(settings) as app:
        report = service.analyze_carousel(app, stable_id("post", "demo", "post"))
        assert [item["position"] for item in report["items"]] == [0, 2, 3, 6]
        assert [item["status"] for item in report["items"]] == [
            "success",
            "unavailable",
            "unavailable",
            "success",
        ]
        with app.database.transaction() as connection:
            withdraw(
                connection, source_id=imported["source_id"], reason="Controlled source withdrawal"
            )
        monkeypatch.setattr(
            service,
            "analyze_image",
            lambda *args, **kwargs: pytest.fail("Cannot process withdrawn input"),
        )
        with pytest.raises(ConfigurationError):
            service.analyze_carousel(app, stable_id("post", "demo", "post"))


def test_public_account_command_processes_photo_and_carousel_without_video_tools(
    settings: Settings, tmp_path: Path, account_export: Path
) -> None:
    image = picture(tmp_path / "white.png", "white")
    raw = json.loads(account_export.read_text())
    posts = [r for r in raw["records"] if r["record_type"] == "post"]
    posts[0]["content_type"], posts[1]["content_type"] = "photo", "carousel"
    raw["records"].extend(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": posts[i]["external_id"],
            "position": j,
            "uri": str(image),
        }
        for i, j in ((0, 0), (1, 0), (1, 1))
    )
    account_export.write_text(json.dumps(raw))
    assert import_dataset(settings, account_export, "json")["valid"]
    result = cli(
        settings,
        "analyze",
        "account",
        stable_id("account", "demo", "0001"),
        "--metric",
        "demo.views.v1",
        "--analyze-media",
        "--max-items",
        "1",
        expected_exit=5,
    )
    successful = [row for row in result["batch"] if "media_run_id" in row]
    assert len(successful) == 2
    with open_application(settings) as app:
        assert {
            service.load_analysis(app, row["media_run_id"])["report_type"] for row in successful
        } == {"image", "carousel"}
