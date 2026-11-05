"""Conservative numeric craft proxies with complete reviewed coverage requirements."""

from statistics import mean, median
from typing import Any

from socialdna.analytics.creative_recipes import _covers, _events
from socialdna.domain.production import ProductionRecipe


def evaluate_recipe(recipe: ProductionRecipe, bundle: dict[str, Any]) -> dict[str, Any]:
    def result(value: float | None, reason: str) -> dict[str, Any]:
        return {
            "value": value,
            "coverage": "observed" if value is not None else "unknown",
            "reason": reason,
        }

    duration = bundle.get("duration_ms")
    if bundle.get("reason") or not duration:
        return result(None, bundle.get("reason") or "unknown_duration")
    selected: dict[str, list[dict[str, Any]]] = {}
    for technique in recipe.techniques:
        modality = "audio" if technique == "music_beat" else "visual"
        events, ambiguous = _events(bundle, technique, (modality,), False)
        if ambiguous or not _covers(bundle, technique, modality, duration):
            return result(None, "ambiguous_or_incomplete_professional_review")
        selected[technique] = []
        for item in events:
            event = item["annotation"]
            if technique in ("camera_angle", "shot_size") and event.get("value") == "mixed":
                return result(None, "mixed_categories_require_finer_review")
            for anchor in event["anchors"]:
                # Numeric summaries do not silently collapse uncertainty to a
                # convenient nominal time, or assign duration to a point/box.
                if (
                    anchor["start_min_ms"] is None
                    or anchor["start_min_ms"] != anchor["start_max_ms"]
                ):
                    return result(None, "uncertain_craft_timing")
                point = technique in ("cut", "music_beat")
                if point and anchor["kind"] != "point":
                    return result(None, "point_events_required")
                if point and (
                    anchor["start_min_ms"] >= duration
                    or (technique == "cut" and anchor["start_min_ms"] == 0)
                ):
                    return result(None, "interior_cut_or_in_clip_beat_required")
                if not point and (
                    anchor["kind"] != "interval"
                    or anchor["end_min_ms"] != anchor["end_max_ms"]
                    or anchor["end_min_ms"] is None
                ):
                    return result(None, "exact_intervals_required")
                selected[technique].append(
                    {
                        "start": anchor["start_min_ms"],
                        "end": anchor["end_min_ms"] if not point else anchor["start_min_ms"],
                        "value": event.get("value"),
                    }
                )
        selected[technique].sort(key=lambda event: (event["start"], event["end"]))
        if technique in ("cut", "music_beat") and len(
            {e["start"] for e in selected[technique]}
        ) != len(selected[technique]):
            return result(None, "duplicate_reviewed_points_require_adjudication")
    operation = recipe.operation
    first = selected[recipe.techniques[0]]
    if operation in ("shot_mean", "shot_median", "pacing_change", "angle_changes"):
        if (
            not first
            or first[0]["start"] != 0
            or first[-1]["end"] != duration
            or any(
                left["end"] != right["start"] for left, right in zip(first, first[1:], strict=False)
            )
        ):
            return result(None, "complete_nonoverlapping_partition_required")
    if operation in ("shot_mean", "shot_median"):
        values = [(event["end"] - event["start"]) / 1000 for event in first]
        return result(
            float(mean(values) if operation == "shot_mean" else median(values)),
            "reviewed_shot_duration_distribution",
        )
    if operation == "pacing_change":
        groups = [
            [(e["end"] - e["start"]) for e in first if (e["start"] < duration / 2) == half]
            for half in (True, False)
        ]
        if any(len(group) < 2 for group in groups):
            return result(None, "at_least_two_shots_in_each_temporal_half_required")
        return result(
            mean(groups[1]) / mean(groups[0]) - 1, "reviewed_temporal_half_duration_ratio_minus_one"
        )
    if operation == "cuts_per_minute":
        return result(len(first) * 60000 / duration, "reviewed_cut_density")
    if operation == "subtitle_occupancy":
        total, end = 0, 0
        for event in first:
            total += max(0, event["end"] - max(end, event["start"]))
            end = max(end, event["end"])
        return result(total / duration, "reviewed_visible_interval_union")
    if operation == "cut_beat_rate":
        if not first:
            return result(None, "no_cut_denominator")
        beats = selected["music_beat"]
        aligned = sum(
            any(abs(cut["start"] - beat["start"]) <= recipe.tolerance_ms for beat in beats)
            for cut in first
        )
        return result(
            aligned / len(first), "reviewed_cut_beat_proximity_not_semantic_reinforcement"
        )
    if operation == "angle_changes":
        return result(
            float(
                sum(
                    left["value"] != right["value"]
                    for left, right in zip(first, first[1:], strict=False)
                )
            ),
            "reviewed_camera_angle_sequence",
        )
    return result(
        float(any(event["value"] in ("close", "extreme_close") for event in first)),
        "reviewed_close_framing_presence",
    )
