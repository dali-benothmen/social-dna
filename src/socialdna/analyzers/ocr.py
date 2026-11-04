import re
from typing import Any

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.core.exceptions import ProviderFailure
from socialdna.core.hashing import canonical_json
from socialdna.domain.providers import OCRBox, OCRFrame


def box_iou(first: OCRBox, second: OCRBox) -> float:
    def bounds(box: OCRBox) -> tuple[float, float, float, float]:
        xs, ys = zip(*box.points, strict=True)
        return min(xs), min(ys), max(xs), max(ys)

    a, b = bounds(first), bounds(second)
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0


def persist_ocr(
    results: list[OCRFrame], frames: list[dict[str, Any]], context: TaskContext
) -> TaskOutput:
    by_id = {frame["id"]: frame for frame in frames}
    if len({r.frame_id for r in results}) != len(results) or any(
        r.frame_id not in by_id for r in results
    ):
        raise ProviderFailure("OCR response contains duplicate or unrequested frame IDs.")
    track_id = context.record(
        "text_tracks",
        {
            "track_type": "ocr",
            "language": None,
            "source": "RapidOCR",
            "is_primary": False,
        },
    )
    tracks: list[dict[str, Any]] = []
    previous: list[dict[str, Any]] = []
    for result in sorted(results, key=lambda row: by_id[row.frame_id]["timestamp_ms"]):
        frame = by_id[result.frame_id]
        current = []
        for box in result.boxes:
            normalized = re.sub(r"\s+", " ", box.text).strip().casefold()
            matching = next(
                (
                    item
                    for item in previous
                    if item["normalized"] == normalized
                    and 0 <= frame["timestamp_ms"] - item["last_ms"] <= 1500
                    and box_iou(item["box"], box) >= 0.6
                    and item not in current
                ),
                None,
            )
            if matching is None:
                matching = {"normalized": normalized, "box": box, "frames": [], "text": box.text}
                tracks.append(matching)
            matching["last_ms"] = frame["timestamp_ms"]
            matching["box"] = box
            matching["frames"].append((frame, box))
            current.append(matching)
        previous = current
    for track in tracks:
        observed = track["frames"]
        begin, end = observed[0][0]["timestamp_ms"], observed[-1][0]["end_ms"]
        segment = context.record(
            "text_segments",
            {
                "track_id": track_id,
                "start_ms": begin,
                "end_ms": end,
                "text": track["text"],
                "confidence": min(box.confidence for _, box in observed),
            },
        )
        context.evidence("text_segment", segment, begin, end, excerpt=track["text"])
        for frame, box in observed:
            box_id = context.record(
                "ocr_boxes",
                {
                    "text_segment_id": segment,
                    "frame_id": frame["id"],
                    "points_json": canonical_json(box.points),
                    "confidence": box.confidence,
                },
            )
            context.evidence(
                "ocr_box",
                box_id,
                frame["timestamp_ms"],
                frame["end_ms"],
                artifact_id=frame["artifact_id"],
                excerpt=box.text,
            )
    context.output.result = {
        "measured_frames": len(results),
        "text_regions": len(tracks),
        "limitations": [
            "OCR persistence links matching adjacent samples; "
            "visibility between sampled frames is not verified."
        ],
    }
    return context.output
