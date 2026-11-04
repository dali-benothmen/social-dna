import os
from pathlib import Path

import pytest

from socialdna.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("SOCIALDNA_") and key not in {
            "SOCIALDNA_TEST_MODEL_LIBRARY",
            "SOCIALDNA_TEST_MEDIAPIPE_PYTHON",
        }:
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


@pytest.fixture
def account_export(tmp_path: Path) -> Path:
    import json
    from datetime import UTC, datetime, timedelta

    records = [
        {
            "record_type": "account",
            "platform": "demo",
            "external_id": "0001",
            "creator_key": "owned-creator",
            "handle": "example",
            "niche": "education",
        }
    ]
    for key in ("views", "likes", "shares", "saves"):
        records.append(
            {
                "record_type": "metric_definition",
                "platform": "demo",
                "key": f"demo.{key}.v1",
                "definition": f"Demo platform {key} count",
            }
        )
    records.append(
        {
            "record_type": "metric_definition",
            "platform": "demo",
            "key": "demo.followers.v1",
            "subject_type": "account",
            "definition": "Account follower count at collection time",
        }
    )
    records.append(
        {
            "record_type": "metric_snapshot",
            "platform": "demo",
            "subject_type": "account",
            "subject_external_id": "0001",
            "metric_key": "demo.followers.v1",
            "observed_at": "2026-01-20T00:00:00Z",
            "value": 1200,
        }
    )
    for index in range(6):
        published = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        records.append(
            {
                "record_type": "post",
                "platform": "demo",
                "external_id": f"p{index}",
                "account_external_id": "0001",
                "published_at": published.isoformat(),
                "caption": "Owned caption " + "x" * index,
            }
        )
        records.append(
            {
                "record_type": "tag",
                "platform": "demo",
                "post_external_id": f"p{index}",
                "kind": "topic",
                "value": "learning",
            }
        )
        for key, value in (("views", (index + 1) * 100), ("likes", (index + 1) * 10)):
            records.append(
                {
                    "record_type": "metric_snapshot",
                    "platform": "demo",
                    "subject_external_id": f"p{index}",
                    "metric_key": f"demo.{key}.v1",
                    "observed_at": (published + timedelta(days=7)).isoformat(),
                    "value": value,
                }
            )
        records.append(
            {
                "record_type": "metric_snapshot",
                "platform": "demo",
                "subject_external_id": f"p{index}",
                "metric_key": "demo.shares.v1",
                "observed_at": (published + timedelta(days=7)).isoformat(),
                "availability": "not_permitted",
                "reason": "Shares not included in export",
            }
        )
    destination = tmp_path / "owned-account.json"
    destination.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "owned-demo",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:socialdna:test-export",
                },
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return destination
