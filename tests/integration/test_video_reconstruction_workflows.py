import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.workflow_report_service import generate
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.providers import OCRBox, OCRFrame, SpeechResult
from socialdna.domain.workflows import ReconstructionOptions, WorkflowRequest
from socialdna.providers.models import PACKAGES, catalog
from socialdna.providers.registry import ProviderRegistry
from socialdna.storage import content_repository as records
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

URL = "https://www.youtube.com/shorts/EaYRjrQuxEk"


def direct(video: Path, subtitles: Path | None = None, **options) -> WorkflowRequest:
    return WorkflowRequest(
        mode="reconstruct",
        url=URL,
        media=(str(video),),
        permission_basis="creator_owned_original",
        subtitles=str(subtitles) if subtitles else None,
        analysis_options=AnalysisOptions(no_ai=True, max_frames=4, depth="quick"),
        reconstruction=ReconstructionOptions(**options),
    )


def execute(settings, request):
    identity = workflow_service.plan(settings, request)["workflow_id"]
    return identity, workflow_service.run(settings, identity)


def from_saved(identity: str, **options) -> WorkflowRequest:
    return WorkflowRequest(
        mode="reconstruct", from_workflow=identity, reconstruction=ReconstructionOptions(**options)
    )


class ControlledProvider:
    """Contract fixture, not real-model transcription/vision accuracy evidence."""

    calls = 0

    def __init__(self, name, capability):
        self.manifest = catalog()["ocr-en" if capability == "ocr" else "asr-tiny"].model_copy(
            update={"name": name}
        )
        self.identity = self.manifest.identity
        self.versions = {
            package: "controlled-fixture" for group in PACKAGES.values() for package in group
        }

    def transcribe(self, request):
        type(self).calls += 1
        return SpeechResult.model_validate(
            {
                "language": "en",
                "segments": [
                    {
                        "start": 0.2,
                        "end": 1.1,
                        "text": "Different spoken words.",
                        "words": [
                            {"text": "Different", "start": 0.2, "end": 0.5, "confidence": 0.8},
                            {"text": "spoken"},
                        ],
                    }
                ],
            }
        )

    def read_text(self, request):
        return [
            OCRFrame(
                frame_id=frame["id"],
                boxes=[
                    OCRBox(
                        text="VISIBLE",
                        confidence=0.8,
                        points=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.4), (0.1, 0.4)],
                    )
                ],
            )
            for frame in request["frames"]
        ]


@pytest.fixture
def controlled_providers(monkeypatch):
    ControlledProvider.calls = 0
    monkeypatch.setattr(
        ProviderRegistry,
        "resolve",
        lambda self, name, capability: ControlledProvider(name, capability),
    )


def test_direct_subtitle_script_is_frozen_cited_and_reopens_in_another_process(
    settings, video, subtitles, tmp_path
):
    settings.offline = True
    identity, result = execute(settings, direct(video, subtitles, allow_verbatim=True))
    document = result["content"]
    assert result["status"] == "partial" and not result["network_attempted"]
    assert document["modality_coverage"]["speech"] == "unknown_not_silence"
    assert document["modality_coverage"]["supplied_subtitles"] == "available_unverified"
    assert {row["lane"] for row in document["rows"]} >= {
        "supplied_subtitle",
        "shot",
        "frame",
        "audio_measurement",
    }
    assert document["transcript_row_ids"] and document["audiovisual_row_ids"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            for row in document["rows"]:
                for citation in row["evidence"]:
                    assert (
                        EvidenceResolver(connection)
                        .resolve(EvidenceRef.model_validate(citation), purpose="new_claim")
                        .eligible
                    )
            count = connection.scalar(
                select(func.count()).select_from(metadata.tables["analysis_tasks"])
            )
        markdown = generate(app, identity, "markdown")
        assert (
            "Transcript lanes" in markdown["content"]
            and "Audiovisual script" in markdown["content"]
        )
    assert workflow_service.run(settings, identity)["content"] == document
    exported = tmp_path / "script.md"
    command = [
        sys.executable,
        "-m",
        "socialdna",
        "--data-dir",
        str(settings.data_dir),
        "--offline",
        "workflow",
        "report",
        identity,
        "--format",
        "markdown",
        "--output",
        str(exported),
    ]
    output = subprocess.run(command, text=True, capture_output=True)
    assert output.returncode == 5, output.stdout + output.stderr
    assert (
        json.loads(output.stdout)["data"]["content"] == exported.read_text() == markdown["content"]
    )
    assert subprocess.run(command, capture_output=True).returncode != 0
    report, repeated = execute(settings, WorkflowRequest(mode="report", from_workflow=identity))
    assert repeated["content"] == document and repeated["workflow_id"] == report
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["analysis_tasks"])
                )
                == count
            )


def test_verbatim_is_not_included_without_declared_reproduction_permission(
    settings, video, subtitles
):
    _, result = execute(settings, direct(video, subtitles))
    doc = result["content"]
    assert doc["status"] == "partial" and doc["verbatim_permission_basis"] is None
    assert all(row["text"] is None and row["words"] == [] for row in doc["rows"])
    assert "useful opening" not in json.dumps(doc).lower()
    assert any(
        action["code"] == "reproduction_permission_required" for action in doc["required_actions"]
    )


def test_actual_track_selection_conflicts_ocr_and_unknown_word_times(
    settings, video, subtitles, controlled_providers
):
    request = direct(video, subtitles, allow_verbatim=True).model_copy(
        update={
            "analysis_options": AnalysisOptions(
                no_ai=False, transcribe=True, ocr=True, align=False, max_frames=4, depth="quick"
            )
        }
    )
    identity, result = execute(settings, request)
    document = result["content"]
    assert document["status"] == "success"
    assert document["disagreements"]
    assert {track["track_type"] for track in document["source_tracks"]} == {
        "asr",
        "ocr",
        "supplied_subtitle",
    }
    spoken = next(row for row in document["rows"] if row["lane"] == "speech")
    assert spoken["words"][1]["start_ms"] is None and spoken["words"][1]["end_ms"] is None
    visible = next(row for row in document["rows"] if row["lane"] == "visible_text")
    assert visible["values"]["regions"] and len(visible["evidence"]) > 1
    asr = next(track["id"] for track in document["source_tracks"] if track["track_type"] == "asr")
    selected, result = execute(
        settings,
        from_saved(
            identity,
            output="transcript",
            track_ids=(asr,),
            allow_verbatim=True,
            start_ms=400,
            end_ms=900,
        ),
    )
    assert ControlledProvider.calls == 1
    assert result["content"]["audiovisual_row_ids"] == []
    assert {row["track_id"] for row in result["content"]["rows"]} == {asr}
    # Overlapping native segment is retained, not text-truncated with invented word bounds.
    assert result["content"]["rows"][0]["start_ms"] == 200
    assert result["content"]["rows"][0]["end_ms"] == 1100
    assert result["content"]["parent_report"]["kind"] == "content_report"
    with pytest.raises(ConfigurationError, match="tracks"):
        execute(settings, from_saved(identity, track_ids=("not-this-run",), allow_verbatim=True))
    with pytest.raises(ConfigurationError, match="duration"):
        execute(settings, from_saved(identity, end_ms=99_999, allow_verbatim=True))
    assert workflow_service.show(settings, selected)["state"] == "completed"


def test_no_audio_has_no_invented_dialogue_but_tone_audio_is_not_silence(settings, video, tmp_path):
    no_audio = tmp_path / "silent.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-an",
            str(no_audio),
        ],
        check=True,
    )
    _, result = execute(settings, direct(no_audio, allow_verbatim=True, output="transcript"))
    assert result["status"] == "success"
    assert result["content"]["modality_coverage"]["speech"] == "no_audio_stream"
    assert not result["content"]["rows"] and not result["content"]["transcript_row_ids"]
    # A new post association prevents replacing the first clip's declared bytes implicitly.
    tone_request = direct(video, allow_verbatim=True).model_copy(
        update={"url": "https://youtu.be/AAAAAAAAAAA"}
    )
    _, result = execute(settings, tone_request)
    assert result["status"] == "partial"
    assert result["content"]["modality_coverage"]["speech"] == "unknown_not_silence"
    assert not any(row["lane"] == "speech" for row in result["content"]["rows"])


def test_withdrawal_and_confirmed_erasure_cover_script_artifacts_and_memory(
    settings, video, subtitles, tmp_path
):
    from socialdna.memory.documents import build
    from socialdna.storage.audience_retention import begin, preview, resume
    from socialdna.storage.backup import backup_library, restore_library

    identity, result = execute(settings, direct(video, subtitles, allow_verbatim=True))
    backup = tmp_path / "before-erasure"
    backup_library(settings, backup)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            ref = records.records(connection, identity, "video_reconstruction")[0]
            citation = records.cite(connection, ref)
            assert build(connection, "evidence", citation.revision_id)
            source = EvidenceRepository(connection).entity(ref)["source_id"]
            withdraw(connection, source_id=source, reason="Owner revoked use")
        with pytest.raises(ConfigurationError):
            generate(app, identity)
        with app.database.transaction() as connection:
            assert build(connection, "evidence", citation.revision_id) is None
            planned = preview(connection, source_id=source)
            assert ref.revision_id in planned["items"]["entity_revision"]
            begin(
                connection,
                planned,
                confirmation=planned["confirmation"],
                reason="Owner deletion",
                actor="test owner",
            )
        resume(app.database, app.paths)
        with app.database.transaction() as connection:
            payload = connection.scalar(
                select(metadata.tables["entity_revisions"].c.payload_json).where(
                    metadata.tables["entity_revisions"].c.id == ref.revision_id
                )
            )
            assert "useful opening" not in payload.lower()
        with pytest.raises(ConfigurationError):
            generate(app, identity)
    assert result["content"]["transcript_row_ids"]
    restored = tmp_path / "restored"
    restore_library(backup, restored, withdrawals_from=settings.data_dir)
    with open_application(settings.model_copy(update={"data_dir": restored})) as app:
        with pytest.raises(ConfigurationError):
            generate(app, identity)


def test_missing_input_photo_and_dry_run_remain_honest(settings, video, tmp_path):
    from PIL import Image

    dry = workflow_service.plan(settings, direct(video), dry_run=True)
    assert dry["dry_run"] and not settings.data_dir.exists()
    _, result = execute(settings, WorkflowRequest(mode="reconstruct", url=URL))
    assert result["status"] == "partial" and not result["network_attempted"]
    image = tmp_path / "photo.png"
    Image.new("RGB", (40, 30), "red").save(image)
    _, result = execute(settings, direct(image))
    assert result["status"] == "partial"


def test_multilingual_source_is_not_translated_and_markdown_is_escaped(settings, video):
    captions = Path(__file__).parents[1] / "fixtures/media/multilingual.srt"
    _, result = execute(settings, direct(video, captions, allow_verbatim=True, output="transcript"))
    text = " ".join(row["text"] for row in result["content"]["rows"])
    assert "مرحبا — ¡Café!" in text
    assert "Ignore previous instructions" in text
    assert all(track["language"] is None for track in result["content"]["source_tracks"])
    with open_application(settings) as app:
        markdown = generate(app, result["workflow_id"], "markdown")["content"]
    assert "\\[untrusted link\\]" in markdown


def test_interrupted_reconstruction_reuses_analysis_and_pins_new_selections(
    settings, video, subtitles, controlled_providers, monkeypatch
):
    from socialdna.application import reconstruction_service

    request = direct(video, subtitles, allow_verbatim=True).model_copy(
        update={
            "analysis_options": AnalysisOptions(
                no_ai=False, transcribe=True, ocr=False, max_frames=4, depth="quick"
            )
        }
    )
    identity = workflow_service.plan(settings, request)["workflow_id"]
    original = reconstruction_service.render

    def crash(_):
        raise RuntimeError("before reconstruction artifact publication")

    monkeypatch.setattr(reconstruction_service, "render", crash)
    with pytest.raises(RuntimeError, match="publication"):
        workflow_service.run(settings, identity)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            assert records.records(connection, identity, "content_report")
            assert not records.records(connection, identity, "video_reconstruction")
        with pytest.raises(ConfigurationError, match="script"):
            generate(app, identity)
    monkeypatch.setattr(reconstruction_service, "render", original)
    result = workflow_service.run(settings, identity)
    assert result["status"] == "success" and ControlledProvider.calls == 1
    # A track change is a new composition, not a rerun or mutation of media tasks.
    track = next(t["id"] for t in result["content"]["source_tracks"] if t["track_type"] == "asr")
    other, selected = execute(
        settings, from_saved(identity, track_ids=(track,), output="transcript", allow_verbatim=True)
    )
    assert other != identity and selected["report"] != result["report"]
    assert selected["content"]["run_id"] == result["content"]["run_id"]
    assert ControlledProvider.calls == 1
    assert workflow_service.run(settings, identity)["content"] == result["content"]


def test_explicit_unprepared_asr_does_not_download_or_invent_speech(settings, video):
    request = direct(video, allow_verbatim=True).model_copy(
        update={
            "analysis_options": AnalysisOptions(
                no_ai=False, transcribe=True, ocr=False, max_frames=4, depth="quick"
            )
        }
    )
    _, result = execute(settings, request)
    assert result["status"] == "partial" and not result["network_attempted"]
    assert result["content"]["modality_coverage"]["speech"] == "unknown_not_silence"
    assert not list((settings.data_dir / "models").rglob("*.safetensors"))


def test_only_explicit_reviewed_creative_revision_enters_script(settings, video):
    from socialdna.application.creative_service import import_into_application
    from socialdna.domain.creative import CreativeAnnotationSet

    identity, result = execute(settings, direct(video, allow_verbatim=True))
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            checksum = EvidenceRepository(connection).get(
                "media_assets", result["content"]["media"]["id"]
            )["sha256"]
        specification = CreativeAnnotationSet.model_validate(
            {
                "key": "controlled-cut-review",
                "media_sha256": checksum,
                "permission_basis": "Owned synthetic annotation, not real review accuracy evidence",
                "protocol": {
                    "origin": "human",
                    "author": "Controlled test fixture",
                    "procedure": "Declared synthetic cut review",
                    "outcome_access": "blinded",
                },
                "events": [
                    {
                        "key": "reviewed-cut",
                        "technique": "cut",
                        "description": "Synthetic reviewed cut cue.",
                        "modalities": ["visual"],
                        "state": "reviewed",
                        "reviewer": "Controlled test fixture",
                        "anchors": [
                            {
                                "kind": "point",
                                "start_min_ms": 950,
                                "start_max_ms": 1050,
                                "nominal_start_ms": 1000,
                            }
                        ],
                    },
                    {
                        "key": "not-reviewed",
                        "technique": "cut",
                        "description": "Do not promote this proposal.",
                        "modalities": ["visual"],
                        "state": "proposed",
                        "anchors": [{"kind": "point", "start_min_ms": 2000, "start_max_ms": 2000}],
                    },
                ],
            }
        )
        imported = import_into_application(app, specification)
    selected, result = execute(
        settings,
        from_saved(identity, allow_verbatim=True, creative_revision=imported["ref"]["revision_id"]),
    )
    rows = [row for row in result["content"]["rows"] if row["lane"] == "reviewed_creative"]
    assert len(rows) == 1 and rows[0]["text"] == "Synthetic reviewed cut cue."
    assert rows[0]["start_ms"] == 1000 and rows[0]["end_ms"] is None
    assert rows[0]["values"]["anchors"][0]["start_min_ms"] == 950
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            annotation = EvidenceRepository(connection).entity(
                EvidenceRepository(connection).ref(
                    EvidenceRepository(connection).get(
                        "entity_revisions", imported["ref"]["revision_id"]
                    )
                )
            )
            withdraw(connection, source_id=annotation["source_id"], reason="Review withdrawn")
        with pytest.raises(ConfigurationError):
            generate(app, selected)
