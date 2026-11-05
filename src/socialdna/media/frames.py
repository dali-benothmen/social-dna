from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.config.settings import Settings
from socialdna.core.exceptions import MediaProcessingError
from socialdna.domain.media import MediaInfo
from socialdna.media.ffmpeg import require_tool, run_process
from socialdna.media.probe import frame_timestamps

ImageArray = NDArray[np.uint8]


def decode_proxy(
    source: Path, destination: Path, info: MediaInfo, settings: Settings, context: TaskContext
) -> TaskOutput:
    times, end_ms = frame_timestamps(source, info, settings)
    run_process(
        [
            require_tool("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-map",
            f"0:{info.video_stream_index}",
            "-an",
            "-vf",
            "scale=320:320:force_original_aspect_ratio=decrease",
            "-c:v",
            "ffv1",
            "-threads",
            "1",
            "-vsync",
            "0",
            "-y",
            str(destination),
        ],
        timeout=settings.media_timeout_seconds,
    )
    context.output.blobs["proxy"] = (destination, "analysis-proxy", "video/x-matroska")
    context.output.result = {
        "proxy_artifact_id": "@artifact:proxy",
        "timestamps_ms": times,
        "frame_count": len(times),
        "video_end_ms": end_ms,
    }
    return context.output


def iter_frames(path: Path, times: list[int]) -> Iterator[tuple[int, int, ImageArray]]:
    capture = cv2.VideoCapture(str(path))
    count = 0
    try:
        if not capture.isOpened():
            raise MediaProcessingError("OpenCV could not open the analysis proxy.")
        while True:
            available, frame = capture.read()
            if not available:
                break
            if count >= len(times):
                raise MediaProcessingError(
                    "Proxy/source frame counts differ; timestamp alignment refused."
                )
            yield count, times[count], cast(ImageArray, frame)
            count += 1
        if count != len(times):
            raise MediaProcessingError(
                "Proxy/source frame counts differ; timestamp alignment refused."
            )
    finally:
        capture.release()


def perceptual_hash(frame: ImageArray) -> str:
    gray = cv2.cvtColor(cv2.resize(frame, (9, 8)), cv2.COLOR_BGR2GRAY)
    bits = gray[:, 1:] > gray[:, :-1]
    return f"{int.from_bytes(np.packbits(bits).tobytes(), 'big'):016x}"


def frame_candidates(
    times: list[int],
    scenes: list[dict[str, int]],
    sample_ms: int,
    motion: list[dict[str, Any]],
    limit: int,
) -> dict[int, str]:
    import bisect

    selected: dict[int, str] = {}
    for scene in scenes:
        first = bisect.bisect_left(times, scene["start_ms"])
        last = min(len(times) - 1, bisect.bisect_left(times, scene["end_ms"]) - 1)
        if first <= last:
            for index in (first, (first + last) // 2, last):
                selected[index] = "scene-keyframe"
    for timestamp in range(times[0], times[-1] + 1, sample_ms):
        selected.setdefault(min(bisect.bisect_left(times, timestamp), len(times) - 1), "regular")
    for peak in sorted(motion, key=lambda row: row["value"], reverse=True)[: max(1, limit // 8)]:
        selected.setdefault(peak["ordinal"], "motion-peak")
    if len(selected) > limit:
        ordered = sorted(selected)
        selected = {
            ordered[int(index)]: selected[ordered[int(index)]]
            for index in np.linspace(0, len(ordered) - 1, limit, dtype=int)
        }
    return selected


def extract_frames(
    proxy: Path,
    times: list[int],
    candidates: dict[int, str],
    duration_ms: int,
    directory: Path,
    context: TaskContext,
    *,
    preserve_samples: bool = False,
) -> TaskOutput:
    previous: ImageArray | None = None
    previous_hash: str | None = None
    images: list[tuple[int, Image.Image]] = []
    deduplicated = 0
    frame_rows = []
    for ordinal, timestamp, frame in iter_frames(proxy, times):
        if ordinal not in candidates:
            continue
        phash = perceptual_hash(frame)
        # Histogram/absolute pixel agreement prevents solid colors sharing dHash from collapsing.
        if (
            previous is not None
            and not preserve_samples
            and previous_hash == phash
            and float(np.mean(cv2.absdiff(previous, frame))) < 2
            and candidates[ordinal] != "scene-keyframe"
        ):
            deduplicated += 1
            continue
        previous, previous_hash = frame, phash
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        path = directory / f"frame-{ordinal}.jpg"
        image.save(path, format="JPEG", quality=90)
        key = f"frame-{ordinal}"
        context.output.blobs[key] = (path, "frame", "image/jpeg")
        frame_id = context.record(
            "frames",
            {
                "timestamp_ms": timestamp,
                "ordinal": ordinal,
                "selection_reason": candidates[ordinal],
                "perceptual_hash": phash,
                "artifact_id": f"@artifact:{key}",
            },
        )
        end = min(
            duration_ms,
            max(timestamp + 1, times[ordinal + 1] if ordinal + 1 < len(times) else duration_ms),
        )
        context.evidence("frame", frame_id, timestamp, end, artifact_id=f"@artifact:{key}")
        frame_rows.append(
            {
                "id": frame_id,
                "timestamp_ms": timestamp,
                "end_ms": end,
                "ordinal": ordinal,
                "artifact_id": f"@artifact:{key}",
            }
        )
        if len(images) < 24:
            image.thumbnail((160, 160))
            images.append((timestamp, image))
    if not frame_rows:
        raise MediaProcessingError("No evidence frames could be extracted.")
    sheet = Image.new("RGB", (640, ((len(images) + 3) // 4) * 190), "white")
    draw = ImageDraw.Draw(sheet)
    for position, (timestamp, image) in enumerate(images):
        x, y = (position % 4) * 160, (position // 4) * 190
        sheet.paste(image, (x, y))
        draw.text((x + 4, y + 165), f"{timestamp / 1000:.3f}s", fill="black")
    sheet_path = directory / "contact-sheet.jpg"
    sheet.save(sheet_path, format="JPEG")
    context.output.blobs["contact-sheet"] = (sheet_path, "contact-sheet", "image/jpeg")
    context.output.result = {
        "frames": frame_rows,
        "deduplicated": deduplicated,
        "contact_sheet_artifact_id": "@artifact:contact-sheet",
    }
    return context.output
