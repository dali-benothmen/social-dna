from pathlib import Path

from scenedetect import AdaptiveDetector, FrameTimecode, StatsManager

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.media.frames import iter_frames


def detect_scenes(
    proxy: Path,
    times: list[int],
    duration_ms: int,
    threshold: float,
    context: TaskContext,
    frame_rate: float = 30.0,
) -> TaskOutput:
    detector = AdaptiveDetector(adaptive_threshold=threshold, min_scene_len=3)
    stats = StatsManager()
    detector.stats_manager = stats
    stats.register_metrics(detector.get_metrics())
    cuts = []
    for ordinal, _, frame in iter_frames(proxy, times):
        cuts.extend(detector.process_frame(FrameTimecode(ordinal, fps=frame_rate), frame))
    cuts.extend(detector.post_process(FrameTimecode(len(times) - 1, fps=frame_rate)))
    scores = []
    metric_keys = detector.get_metrics()
    for ordinal, start in enumerate(times):
        values = stats.get_metrics(FrameTimecode(ordinal, fps=frame_rate), metric_keys)
        scores.append(
            {"timestamp_ms": start, "values": dict(zip(metric_keys, values, strict=True))}
        )
    boundaries = sorted({0, *[int(cut) for cut in cuts if 0 < int(cut) < len(times)]})
    scenes = []
    for index, frame_index in enumerate(boundaries):
        start = times[frame_index]
        end = times[boundaries[index + 1]] if index + 1 < len(boundaries) else duration_ms
        if end <= start:
            continue
        scene_id = context.record(
            "scenes",
            {
                "ordinal": index,
                "start_ms": start,
                "end_ms": end,
                "detector": "PySceneDetect.AdaptiveDetector",
            },
        )
        context.evidence("scene", scene_id, start, end)
        context.observe(
            "visual.shot_duration_ms",
            end - start,
            start,
            end,
            modality="visual",
            unit="ms",
            description="Detected shot duration.",
        )
        scenes.append({"start_ms": start, "end_ms": end})
    context.observe(
        "visual.cuts_per_second",
        max(0, len(scenes) - 1) / (duration_ms / 1000),
        0,
        duration_ms,
        modality="visual",
        unit="cuts/s",
        description="Detected cuts divided by video duration.",
    )
    context.output.result = {"scenes": scenes, "scores": scores}
    return context.output
