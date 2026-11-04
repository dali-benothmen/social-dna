import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from socialdna.application.analysis_service import analyze_video
from socialdna.application.bootstrap import open_application
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.domain.media import AnalysisOptions
from socialdna.media.ffmpeg import require_tool, run_process

pytestmark = pytest.mark.local_models


def test_real_isolated_pose_and_audio(settings: Settings, video: Path) -> None:
    library = os.environ.get("SOCIALDNA_TEST_MODEL_LIBRARY")
    python = os.environ.get("SOCIALDNA_TEST_MEDIAPIPE_PYTHON")
    if not library or not python:
        pytest.skip("Set model library and isolated MediaPipe interpreter for native smoke tests")
    shutil.copytree(Path(library) / "models", settings.data_dir / "models")
    settings.offline = True
    settings.provider_pythons = {"pose": Path(python), "audio_classifier": Path(python)}
    with open_application(settings) as application:
        result = analyze_video(
            application,
            str(video),
            options=AnalysisOptions(
                transcribe=False,
                ocr=False,
                pose=True,
                classify_audio=True,
            ),
        )
        assert result["status"] == "success", result
        assert result["tasks"]["pose"]["status"] == "succeeded"
        assert result["tasks"]["audio.classify"]["status"] == "succeeded"
        report = generate_report(application, result["run_id"])["content"]
        observations = report["timeline"]["observations"]
        assert any(row["feature_key"] == "visual.pose_landmarks" for row in observations)
        assert any(row["feature_key"] == "audio.event_candidates" for row in observations)
        assert all(
            row["value"]["claim_level"] == "hypothesis"
            for row in observations
            if row["feature_key"] == "audio.event_candidates"
        )


def test_real_cpu_asr_ocr_and_restart(settings: Settings, tmp_path: Path) -> None:
    library = os.environ.get("SOCIALDNA_TEST_MODEL_LIBRARY")
    if not library:
        pytest.skip("Set SOCIALDNA_TEST_MODEL_LIBRARY to an explicitly prepared model library")
    shutil.copytree(Path(library) / "models", settings.data_dir / "models")
    settings.offline = True
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    draw.text((35, 130), "SOCIAL DNA", font=font, fill="black")
    picture, video = tmp_path / "own-text.png", tmp_path / "own-speech.mkv"
    image.save(picture)
    filters = run_process([require_tool("ffmpeg"), "-hide_banner", "-filters"])
    if "flite" not in filters.stdout:
        pytest.skip("FFmpeg with libflite is required for this generated-speech fixture")
    run_process(
        [
            require_tool("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-loop",
            "1",
            "-i",
            str(picture),
            "-f",
            "lavfi",
            "-i",
            "flite=text='Hello world. This is a test of local speech recognition.':voice=slt",
            "-t",
            "6",
            "-r",
            "8",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            str(video),
        ]
    )
    with open_application(settings) as application:
        result = analyze_video(
            application,
            str(video),
            options=AnalysisOptions(depth="deep", transcribe=True, ocr=True),
        )
        assert result["status"] == "success", result
        report = generate_report(application, result["run_id"])["content"]
        segments = report["timeline"]["text_segments"]
        speech = " ".join(row["text"] for row in segments if row["track_type"] == "asr").lower()
        printed = " ".join(row["text"] for row in segments if row["track_type"] == "ocr").upper()
        assert "hello" in speech and ("speech" in speech or "local" in speech), speech
        assert "SOCIAL" in printed and "DNA" in printed, printed
        assert report["timeline"]["text_words"] and report["timeline"]["ocr_boxes"]
        assert report["timeline"]["inference_inputs"]
        cached = analyze_video(
            application,
            str(video),
            options=AnalysisOptions(depth="deep", transcribe=True, ocr=True),
        )
        assert cached["tasks"]["transcription"]["status"] == "cached"
        assert cached["tasks"]["ocr"]["status"] == "cached"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "report",
            "generate",
            "--run",
            result["run_id"],
            "--format",
            "json",
            "--data-dir",
            str(settings.data_dir),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["data"]["content"]["timeline"]["ocr_boxes"]
