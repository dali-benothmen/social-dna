import os
from pathlib import Path

import pytest

from socialdna.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("SOCIALDNA_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("SOCIALDNA_DATA_DIR", str(tmp_path / "default-data"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", lock_timeout=0)


@pytest.fixture
def video(tmp_path: Path) -> Path:
    import shutil
    import subprocess

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe are required for media integration tests")
    destination = tmp_path / "owned video ; $(touch PWNED).mkv"
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=96x64:r=12:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=96x64:r=12:d=1",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=96x64:r=12:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=3",
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "3:a",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            "-c:a",
            "pcm_s16le",
            "-y",
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return destination


@pytest.fixture
def subtitles(tmp_path: Path) -> Path:
    path = tmp_path / "captions.srt"
    path.write_text(
        "1\n00:00:00,200 --> 00:00:01,100\nA useful opening?\n\n"
        "2\n00:00:01,200 --> 00:00:02,800\n<script>alert(1)</script> [click](https://bad)\n",
        encoding="utf-8",
    )
    return path
