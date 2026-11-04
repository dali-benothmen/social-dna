import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from socialdna.application.analysis_service import analyze_video
from socialdna.application.bootstrap import open_application
from socialdna.application.import_service import import_local
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import DependencyUnavailable, InvalidMedia
from socialdna.domain.media import AnalysisOptions
from socialdna.media.timeline import timeline
from socialdna.storage.schema import metadata


def counts(application: object) -> dict[str, int]:
    with application.database.transaction() as connection:
        return {
            name: connection.scalar(select(func.count()).select_from(metadata.tables[name]))
            for name in ("frames", "scenes", "observations", "evidence_items")
        }


def test_video_to_timeline_reports_and_restart(
    settings: Settings, video: Path, subtitles: Path
) -> None:
    with open_application(settings) as application:
        first = analyze_video(application, str(video), subtitles=subtitles)
        assert first["status"] == "success", first
        data = timeline(application, first["media_id"], 0, 1500)
        assert len(data["scenes"]) == 2
        assert data["frames"] and data["observations"] and data["audio_segments"]
        assert data["text_segments"][0]["start_ms"] == 200
        assert all(frame["timestamp_ms"] < 1500 for frame in data["frames"])
        assert all(
            item["start_ms"] < 1500 and item["end_ms"] > 0 for item in data["evidence_items"]
        )
        keys = {item["feature_key"] for item in data["observations"]}
        assert {
            "visual.palette",
            "visual.optical_flow",
            "audio.rms",
            "audio.integrated_loudness",
        } <= keys
        markdown = generate_report(application, first["run_id"], "markdown")["content"]
        assert "Evidence frames" in markdown and "<script>" not in markdown
        assert "\\[click\\]" in markdown
        assert "evidence `" in markdown and "transcription" in markdown
        report = generate_report(application, first["run_id"])["content"]
        assert report["provenance"] and report["feature_definitions"] and report["artifacts"]
        assert all(row["source_record_id"] for row in report["provenance"])
        assert "Contact sheet preview" in markdown
        before = counts(application)
        artifacts = metadata.tables["artifact_objects"]
        with application.database.transaction() as connection:
            media_artifacts = set(
                connection.scalars(select(artifacts.c.id).where(artifacts.c.kind != "report"))
            )
        second = analyze_video(application, str(video), subtitles=subtitles)
        assert counts(application) == before
        with application.database.transaction() as connection:
            assert (
                set(connection.scalars(select(artifacts.c.id).where(artifacts.c.kind != "report")))
                == media_artifacts
            )
        assert second["tasks"]["visual"]["status"] == "cached"
        assert timeline(application, first["media_id"], run_id=second["run_id"])["observations"]
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "timeline",
            "show",
            first["media_id"],
            "--start",
            "0s",
            "--end",
            "1.5s",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["data"]["evidence_items"]
    assert not (video.parent / "PWNED").exists()


def test_selective_invalidation(settings: Settings, video: Path) -> None:
    with open_application(settings) as application:
        original = analyze_video(application, str(video))
        result = analyze_video(application, str(video), options=AnalysisOptions(palette_bins=4))
        assert result["status"] == "success", result
        for name in ("prepare", "scenes", "motion", "frames", "audio.extract", "audio.features"):
            assert result["tasks"][name]["status"] == "cached"
        assert result["tasks"]["visual"]["status"] == "succeeded"
        assert result["tasks"]["timeline"]["status"] == "succeeded"
        application.settings.max_decode_frames -= 1
        with pytest.raises(InvalidMedia, match="Resume requires"):
            analyze_video(application, str(video), resume=original["run_id"])
        with application.database.transaction() as connection:
            runs = metadata.tables["analysis_runs"]
            assert (
                connection.scalar(select(runs.c.status).where(runs.c.id == original["run_id"]))
                == "succeeded"
            )


@pytest.mark.parametrize(
    "interrupt_after",
    [
        "prepare",
        "scenes",
        "motion",
        "frames",
        "visual",
        "audio.extract",
        "audio.features",
        "subtitles",
    ],
)
def test_resume_after_committed_tasks(
    settings: Settings, video: Path, interrupt_after: str
) -> None:
    captured = []

    def interrupt(name: str) -> None:
        if name == interrupt_after:
            raise KeyboardInterrupt()

    with open_application(settings) as application:
        with pytest.raises(KeyboardInterrupt):
            analyze_video(application, str(video), on_run=captured.append, after_task=interrupt)
        partial_report = generate_report(application, captured[0])["content"]
        assert partial_report["status"] == "partial"
        before = counts(application)
    if interrupt_after == "prepare":
        report_process = subprocess.run(
            [
                sys.executable,
                "-m",
                "socialdna",
                "report",
                "generate",
                "--run",
                captured[0],
                "--format",
                "json",
                "--data-dir",
                str(settings.data_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert report_process.returncode == 5, report_process.stdout + report_process.stderr
        assert json.loads(report_process.stdout)["status"] == "partial"
    with open_application(settings) as application:
        result = analyze_video(application, str(video), resume=captured[0])
        assert result["status"] == "success", result
        assert result["run_id"] == captured[0]
        after = counts(application)
        assert after["frames"] >= before["frames"]
        repeated = analyze_video(application, str(video), resume=captured[0])
        assert repeated["status"] == "success"
        assert counts(application) == after


def test_managed_copy_survives_original_deletion(settings: Settings, video: Path) -> None:
    with open_application(settings) as application:
        imported = import_local(application, video, copy_media=True)
        video.unlink()
        result = analyze_video(application, imported["media_id"])
        assert result["status"] == "success", result


def test_missing_tools_and_changed_sources(
    settings: Settings, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with open_application(settings) as application:
        imported = import_local(application, video)
        monkeypatch.setattr("socialdna.media.ffmpeg.shutil.which", lambda name: None)
        with pytest.raises(DependencyUnavailable):
            analyze_video(application, imported["media_id"])
        monkeypatch.undo()
        video.write_bytes(b"changed bytes")
        with pytest.raises(InvalidMedia, match="missing or its bytes changed"):
            analyze_video(application, imported["media_id"])
