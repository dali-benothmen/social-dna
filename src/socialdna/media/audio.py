import json
import math
from pathlib import Path

import soundfile as sf

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.config.settings import Settings
from socialdna.domain.media import MediaInfo
from socialdna.media.ffmpeg import require_tool, run_process


def extract_audio(
    source: Path, destination: Path, info: MediaInfo, settings: Settings, context: TaskContext
) -> TaskOutput:
    if info.audio_stream_index is None:
        return TaskOutput(result={"available": False}, skipped="Video has no audio stream.")
    start_ms = info.audio_start_ms or 0
    if start_ms >= info.duration_ms:
        return TaskOutput(result={"available": False}, skipped="Audio does not overlap the video.")
    length_seconds = (info.duration_ms - start_ms) / 1000
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
            f"0:{info.audio_stream_index}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-t",
            str(length_seconds),
            "-y",
            str(destination),
        ],
        timeout=settings.media_timeout_seconds,
    )
    extracted = sf.info(destination)
    end_ms = min(info.duration_ms, start_ms + round(extracted.duration * 1000))
    if end_ms <= start_ms:
        return TaskOutput(result={"available": False}, skipped="Audio stream has no samples.")
    # Measure original mix before mono downmix/resampling; do not call amplitude LUFS.
    loudness = None
    loudness_warning = None
    try:
        output = run_process(
            [
                require_tool("ffmpeg"),
                "-nostdin",
                "-v",
                "info",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(source),
                "-map",
                f"0:{info.audio_stream_index}",
                "-vn",
                "-t",
                str(length_seconds),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                "-f",
                "null",
                "-",
            ],
            timeout=settings.media_timeout_seconds,
        )
        begin, end = output.stderr.rfind("{"), output.stderr.rfind("}")
        data = json.loads(output.stderr[begin : end + 1])
        candidate = float(data["input_i"])
        loudness = candidate if math.isfinite(candidate) else None
        if loudness is None:
            loudness_warning = "Integrated LUFS is undefined for silent/ungated audio."
    except Exception as exc:
        loudness_warning = f"EBU R128 integrated loudness unavailable: {exc}"
    context.output.blobs["audio"] = (destination, "analysis-audio", "audio/wav")
    segment_id = context.record(
        "audio_segments",
        {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "segment_type": "audio_track",
            "artifact_id": "@artifact:audio",
        },
    )
    context.evidence(
        "audio_segment",
        segment_id,
        start_ms,
        end_ms,
        artifact_id="@artifact:audio",
    )
    if loudness is not None:
        context.observe(
            "audio.integrated_loudness",
            loudness,
            start_ms,
            end_ms,
            modality="audio",
            unit="LUFS",
            description="FFmpeg EBU R128 input integrated loudness; original mix.",
        )
    context.output.result = {
        "available": True,
        "artifact_id": "@artifact:audio",
        "sample_rate": 16000,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "integrated_lufs": loudness,
        "limitations": [loudness_warning] if loudness_warning else [],
    }
    return context.output
