import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from socialdna.config.settings import Settings
from socialdna.core.exceptions import InvalidMedia, MediaProcessingError
from socialdna.domain.media import MediaInfo
from socialdna.media.ffmpeg import require_tool, run_process


def number(value: Any, default: float = 0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def parse_probe(raw: dict[str, Any]) -> MediaInfo:
    streams = raw.get("streams", [])
    videos = [
        stream
        for stream in streams
        if stream.get("codec_type") == "video"
        and not stream.get("disposition", {}).get("attached_pic")
    ]
    if not videos:
        raise InvalidMedia("The supplied file has no decodable video stream.")
    video = videos[0]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    audio = audios[0] if audios else None
    container = raw.get("format", {})
    starts = [number(stream["start_time"]) for stream in [video, *audios] if "start_time" in stream]
    if "start_time" in container:
        starts.append(number(container["start_time"]))
    origin = min(starts, default=0)
    duration = number(container.get("duration"))
    # A stream duration is a length; preserve its offset within the source timeline.
    stream_ends = [
        number(s.get("start_time"), origin) - origin + number(s.get("duration"))
        for s in [video, *audios]
        if number(s.get("duration")) > 0
    ]
    if stream_ends:
        duration = max(stream_ends)
    try:
        frame_rate = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        frame_rate = 0
    if frame_rate <= 0:
        try:
            frame_rate = float(Fraction(video.get("r_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            frame_rate = 0
    rotation = number(video.get("tags", {}).get("rotate"))
    for side in video.get("side_data_list", []):
        rotation = number(side.get("rotation"), rotation)
    if duration <= 0 or frame_rate <= 0:
        raise InvalidMedia("Video duration or frame rate is missing or invalid.")
    return MediaInfo(
        duration_ms=round(duration * 1000),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        video_stream_index=video["index"],
        audio_stream_index=audio["index"] if audio else None,
        origin_seconds=origin,
        video_start_ms=max(0, round((number(video.get("start_time"), origin) - origin) * 1000)),
        audio_start_ms=max(0, round((number(audio.get("start_time"), origin) - origin) * 1000))
        if audio
        else None,
        frame_rate=frame_rate,
        time_base=video.get("time_base", "unknown"),
        rotation=round(rotation),
        format_name=container.get("format_name", "unknown"),
        streams=streams,
        raw=raw,
    )


def probe(path: Path, settings: Settings) -> MediaInfo:
    try:
        result = run_process(
            [
                require_tool("ffprobe"),
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            timeout=settings.media_timeout_seconds,
        )
        info = parse_probe(json.loads(result.stdout))
    except (MediaProcessingError, ValueError, KeyError) as exc:
        raise InvalidMedia(f"Cannot probe the supplied video: {exc}") from exc
    if info.duration_ms > settings.max_duration_seconds * 1000:
        raise InvalidMedia(
            "Video exceeds max_duration_seconds; raise the explicit configuration limit."
        )
    return info


def frame_timestamps(path: Path, info: MediaInfo, settings: Settings) -> tuple[list[int], int]:
    result = run_process(
        [
            require_tool("ffprobe"),
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-select_streams",
            str(info.video_stream_index),
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time,pkt_duration_time",
            "-of",
            "csv=p=0",
            str(path),
        ],
        timeout=settings.media_timeout_seconds,
        stdout_limit=settings.max_decode_frames * 80,
    )
    times = []
    final_duration = 1000 / info.frame_rate
    for line in result.stdout.splitlines():
        fields = line.split(",")
        field = fields[0].strip()
        if not field:
            continue
        try:
            seconds = float(field)
        except ValueError as exc:
            raise InvalidMedia("A decoded frame lacks a reliable presentation timestamp.") from exc
        if not math.isfinite(seconds):
            raise InvalidMedia("A decoded frame has a non-finite presentation timestamp.")
        times.append(max(0, round((seconds - info.origin_seconds) * 1000)))
        final_duration = number(fields[1] if len(fields) > 1 else None)
        final_duration = (final_duration if final_duration > 0 else 1 / info.frame_rate) * 1000
    if not times or len(times) > settings.max_decode_frames:
        raise InvalidMedia("Video has no frames or exceeds max_decode_frames.")
    if any(right < left for left, right in zip(times, times[1:], strict=False)):
        raise InvalidMedia("Non-monotonic video timestamps cannot be aligned reliably.")
    end_ms = times[-1] + max(1, round(final_duration))
    if end_ms > settings.max_duration_seconds * 1000:
        raise InvalidMedia("Decoded presentation timestamps exceed max_duration_seconds.")
    return times, end_ms
