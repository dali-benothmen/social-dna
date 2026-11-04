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
from socialdna.core.exceptions import InvalidMedia, MediaProcessingError
from socialdna.domain.results import ResultEnvelope
from socialdna.media.ffmpeg import require_tool, run_process
from socialdna.media.probe import frame_timestamps, probe
from socialdna.media.timeline import timeline
from socialdna.storage.health import artifact_checks, database_checks, doctor
from socialdna.storage.schema import metadata


def test_variable_frame_rate_nonzero_start_and_no_audio(
    settings: Settings, video: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "offset-vfr.mkv"
    run_process(
        [
            require_tool("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(video),
            "-an",
            "-vf",
            "select='not(mod(n,3))+eq(n,1)',setpts=PTS+5/TB",
            "-vsync",
            "0",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            str(destination),
        ]
    )
    info = probe(destination, settings)
    assert info.origin_seconds == pytest.approx(5)
    times, end = frame_timestamps(destination, info, settings)
    assert times[:4] == [0, 83, 250, 500]
    assert len(set(b - a for a, b in zip(times, times[1:], strict=False))) > 1
    with open_application(settings) as application:
        result = analyze_video(application, str(destination))
        assert result["status"] == "success", result
        assert result["tasks"]["audio.extract"]["status"] == "skipped"
        assert result["tasks"]["audio.features"]["status"] == "skipped"
        data = timeline(application, result["media_id"], 0, 5000)
        assert data["end_ms"] == end and not data["audio_segments"]
        assert all(frame["timestamp_ms"] in times for frame in data["frames"])
        assert data["scenes"][0]["start_ms"] == 0
        for lane in ("scenes", "evidence_items", "observations"):
            assert all(0 <= item["start_ms"] < item["end_ms"] <= end for item in data[lane])
        assert all(check.status != "error" for check in database_checks(application))
        assert all(check.status != "error" for check in artifact_checks(application))


def test_delayed_short_audio_preserves_alignment(
    settings: Settings, video: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "delayed-audio.mkv"
    run_process(
        [
            require_tool("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(video),
            "-itsoffset",
            "0.25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=0.5",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )
    with open_application(settings) as application:
        result = analyze_video(application, str(destination))
        assert result["status"] == "success", result
        data = timeline(application, result["media_id"])
        track = next(row for row in data["audio_segments"] if row["segment_type"] == "audio_track")
        assert track["start_ms"] == 250 and track["end_ms"] == 750
        rms = [row for row in data["observations"] if row["feature_key"] == "audio.rms"]
        assert len(rms) == 1 and rms[0]["start_ms"] == 250 and rms[0]["end_ms"] == 750


def test_failed_analyzer_keeps_other_modalities_and_can_resume(
    settings: Settings, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object) -> None:
        raise MediaProcessingError("injected visual failure")

    with open_application(settings) as application:
        monkeypatch.setattr("socialdna.application.analysis_service.measure_visual", fail)
        result = analyze_video(application, str(video))
        assert result["status"] == "partial"
        assert result["tasks"]["visual"]["status"] == "failed"
        data = timeline(application, result["media_id"])
        assert data["audio_segments"] and data["frames"]
        assert not any(row["feature_key"] == "visual.palette" for row in data["observations"])
        report = generate_report(application, result["run_id"])["content"]
        assert report["status"] == "partial"
        assert any("injected visual failure" in item for item in report["limitations"])
        monkeypatch.undo()
        resumed = analyze_video(application, str(video), resume=result["run_id"])
        assert resumed["status"] == "success", resumed
        assert resumed["tasks"]["frames"]["status"] == "cached"
        assert resumed["tasks"]["visual"]["status"] == "succeeded"


def test_input_limits_and_malformed_media(settings: Settings, video: Path, tmp_path: Path) -> None:
    bad = tmp_path / "malformed.mp4"
    bad.write_bytes(b"not a media file")
    with open_application(settings) as application:
        with pytest.raises(InvalidMedia, match="Cannot probe"):
            import_local(application, bad)
        application.settings.max_media_bytes = 1
        with pytest.raises(InvalidMedia, match="max_media_bytes"):
            import_local(application, video)
        application.settings.max_media_bytes = 2_000_000_000
        application.settings.max_duration_seconds = 1
        with pytest.raises(InvalidMedia, match="max_duration_seconds"):
            import_local(application, video)
        application.settings.max_duration_seconds = 600
        application.settings.max_decode_frames = 2
        result = analyze_video(application, str(video))
        assert result["status"] == "partial"
        assert result["tasks"]["prepare"]["status"] == "failed"
        assert result["tasks"]["frames"]["status"] == "skipped"
        with application.database.transaction() as connection:
            assert (
                connection.scalar(select(func.count()).select_from(metadata.tables["frames"])) == 0
            )


def test_cli_analyze_and_report_after_process_restart(
    settings: Settings, video: Path, subtitles: Path
) -> None:
    def command(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "socialdna", *arguments, "--data-dir", str(settings.data_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )

    first = command("import", "local", str(video), "--format", "json")
    assert first.returncode == 0, first.stdout + first.stderr
    imported = ResultEnvelope.model_validate_json(first.stdout)
    second = command(
        "analyze",
        "video",
        imported.data["media_id"],
        "--depth",
        "deep",
        "--subtitles",
        str(subtitles),
        "--format",
        "json",
    )
    assert second.returncode == 0, second.stdout + second.stderr
    envelope = ResultEnvelope.model_validate_json(second.stdout)
    assert envelope.run_id and envelope.data["reports"] and "Analysis run:" in second.stderr
    third = command("report", "generate", "--run", envelope.run_id, "--format", "markdown")
    assert third.returncode == 0, third.stdout + third.stderr
    assert "# Video analysis:" in third.stdout and "evidence `" in third.stdout
    fourth = command("report", "generate", "--run", envelope.run_id, "--format", "json")
    assert fourth.returncode == 0, fourth.stdout + fourth.stderr
    report = json.loads(fourth.stdout)["data"]["content"]
    assert report["timeline"]["observations"] and report["timeline"]["text_segments"]


def test_doctor_and_cli_missing_tools(
    settings: Settings, video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from socialdna.cli.app import app

    monkeypatch.setattr("shutil.which", lambda name: None)
    checks = doctor(settings)
    assert {item.name for item in checks if item.status == "warning"} >= {"ffmpeg", "ffprobe"}
    result = CliRunner().invoke(
        app,
        ["analyze", "video", str(video), "--format", "json", "--data-dir", str(settings.data_dir)],
    )
    assert result.exit_code == 3
    assert json.loads(result.stdout)["status"] == "error"
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            assert (
                connection.scalar(select(func.count()).select_from(metadata.tables["reports"])) == 0
            )
