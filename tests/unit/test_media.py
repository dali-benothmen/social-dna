import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from socialdna.analyzers.audio import audio_features
from socialdna.analyzers.base import TaskContext
from socialdna.analyzers.visual import visual_features
from socialdna.cli.app import parse_offset
from socialdna.core.exceptions import ConfigurationError, InvalidMedia, MediaProcessingError
from socialdna.media.ffmpeg import run_process
from socialdna.media.frames import frame_candidates, perceptual_hash
from socialdna.media.probe import parse_probe
from socialdna.media.subtitles import import_subtitles


def test_visual_and_audio_numeric_features() -> None:
    red = np.zeros((32, 32, 3), dtype=np.uint8)
    red[:, :, 2] = 255
    features = visual_features(red, 8)
    assert features["saturation"] == 1
    assert features["brightness"] == pytest.approx(76 / 255, abs=0.01)
    assert features["contrast"] == 0 and features["entropy"] == 0
    assert features["palette"][0]["fraction"] == 1
    assert features["palette"][0]["rgb"][0] > 230
    assert sum(features["hsv_histogram"][0]) == pytest.approx(1)
    samples = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 0.25
    audio = audio_features(samples, 16000)
    assert audio["rms"] == pytest.approx(0.25 / math.sqrt(2), rel=0.01)
    assert audio["spectral_centroid"] == pytest.approx(440, abs=1)
    assert audio["zero_crossing_rate"] == pytest.approx(880 / 16000, abs=0.001)
    assert audio_features(np.zeros(100), 16000)["rms"] == 0
    assert np.isfinite(audio_features(np.zeros(100), 16000)["rms_dbfs"])


def test_probe_offsets_and_missing_metrics() -> None:
    info = parse_probe(
        {
            "format": {"start_time": "5", "duration": "3", "format_name": "test"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "width": 96,
                    "height": 64,
                    "start_time": "5.25",
                    "duration": "2.75",
                    "avg_frame_rate": "24000/1001",
                    "time_base": "1/1000",
                    "side_data_list": [{"rotation": 90}],
                },
                {"index": 1, "codec_type": "audio", "start_time": "5", "duration": "3"},
            ],
        }
    )
    assert info.video_start_ms == 250 and info.audio_start_ms == 0
    assert info.duration_ms == 3000 and info.rotation == 90
    assert info.frame_rate == pytest.approx(23.976, abs=0.001)
    with pytest.raises(InvalidMedia):
        parse_probe({"streams": []})


def test_subtitle_tracks_do_not_fabricate_words(tmp_path: Path) -> None:
    path = tmp_path / "supplied.vtt"
    path.write_text("WEBVTT\n\n00:00.200 --> 00:01.200\nHello world\n", encoding="utf-8")
    context = TaskContext("task", "media", "provenance")
    result = import_subtitles(path, 1000, context)
    assert result.records["text_tracks"][0]["track_type"] == "supplied_subtitle"
    assert result.records["text_segments"][0]["end_ms"] == 1000
    assert "text_words" not in result.records
    assert import_subtitles(None, 1000, context).skipped


def test_candidate_bounds_and_hash_dedup() -> None:
    times = list(range(0, 10000, 100))
    selected = frame_candidates(times, [{"start_ms": 0, "end_ms": 10000}], 250, [], 10)
    assert len(selected) <= 10 and min(selected) == 0 and max(selected) < len(times)
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    assert perceptual_hash(image) == perceptual_hash(cv2.resize(image, (40, 40)))


def test_subprocess_timeout_bounded_output_and_argument_safety() -> None:
    with pytest.raises(MediaProcessingError, match="timeout"):
        run_process([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)
    with pytest.raises(MediaProcessingError, match="size limit"):
        run_process([sys.executable, "-c", "print('x'*10000)"], stdout_limit=100)
    output = run_process([sys.executable, "-c", "import sys; print(sys.argv[1])", "$(touch PWNED)"])
    assert output.stdout.strip() == "$(touch PWNED)"
    output = run_process(
        [sys.executable, "-c", "import sys; sys.stderr.write('x'*10000)"], stderr_limit=100
    )
    assert len(output.stderr) == 100


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group semantics")
def test_subprocess_cleans_descendants_retaining_pipes() -> None:
    # The direct child exits, but its descendant inherits the pipe handles.
    output = run_process(
        [
            sys.executable,
            "-c",
            "import subprocess, sys; subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(30)']); print('done')",
        ],
        timeout=1,
    )
    assert output.stdout.strip() == "done"


@pytest.mark.parametrize("value,expected", [("5s", 5000), ("200ms", 200), ("1.5", 1500)])
def test_offsets(value: str, expected: int) -> None:
    assert parse_offset(value) == expected


@pytest.mark.parametrize("value", ["-1s", "nan", "inf", "garbage"])
def test_bad_offsets(value: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_offset(value)
