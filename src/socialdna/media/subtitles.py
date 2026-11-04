import re
from pathlib import Path

import pysubs2

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.core.exceptions import InvalidMedia


def import_subtitles(path: Path | None, duration_ms: int, context: TaskContext) -> TaskOutput:
    if path is None:
        return TaskOutput(
            skipped="No supplied subtitles; "
            "automatic transcription is not implemented until Milestone 3."
        )
    if path.suffix.lower() not in (".srt", ".vtt") or not path.is_file():
        raise InvalidMedia("Supply an existing SRT or VTT file.")
    if path.stat().st_size > 5_000_000:
        raise InvalidMedia("Subtitle file exceeds the 5 MB limit.")
    try:
        subtitles = pysubs2.load(str(path), encoding="utf-8-sig")
    except Exception as exc:
        raise InvalidMedia(f"Cannot parse supplied subtitles: {exc}") from exc
    track_id = context.record(
        "text_tracks",
        {
            "track_type": "supplied_subtitle",
            "language": None,
            "source": path.name,
            "is_primary": True,
        },
    )
    count, clipped = 0, 0
    for segment in subtitles:
        start, end = max(0, segment.start), min(duration_ms, segment.end)
        text = re.sub(r"<[^>]*>", "", segment.plaintext).strip()
        if not text or end <= start:
            clipped += 1
            continue
        segment_id = context.record(
            "text_segments",
            {
                "track_id": track_id,
                "start_ms": start,
                "end_ms": end,
                "text": text,
                "confidence": None,
            },
        )
        context.evidence("text_segment", segment_id, start, end, excerpt=text)
        count += 1
    if count == 0:
        raise InvalidMedia("No supplied subtitle cues overlap this video's timeline.")
    context.output.blobs["supplied-subtitles"] = (path, "supplied-subtitles", "text/plain")
    context.output.result = {"track_id": track_id, "segments": count, "discarded_cues": clipped}
    return context.output
