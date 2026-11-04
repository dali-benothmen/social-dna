from typing import Any

from socialdna.domain.research import PerformanceSpec, Population


def in_population(row: dict[str, Any], population: Population) -> bool:
    for field, allowed in (
        ("platform", population.platforms),
        ("creator_id", population.creator_ids),
        ("niche", population.niches),
        ("content_type", population.content_types),
    ):
        if allowed and row[field] not in allowed:
            return False
    if population.topics and not set(population.topics).intersection(row["topics"]):
        return False
    duration = row["features"].get("duration_seconds")
    if population.min_duration_seconds is not None and (
        duration is None or duration < population.min_duration_seconds
    ):
        return False
    return not (
        population.max_duration_seconds is not None
        and (duration is None or duration > population.max_duration_seconds)
    )


def match_pairs(rows: list[dict[str, Any]], spec: PerformanceSpec) -> list[tuple[str, str]]:
    """Deterministic, no-replacement exact-context + duration-caliper matching.

    No outcome is inspected. Creator, platform, niche, type, topic set, and actual
    observation window/age are held comparable; unmatched posts remain visible.
    """
    left = sorted(
        (row for row in rows if row["role"] == "left" and row["outcome"] is not None),
        key=lambda row: row["post_id"],
    )
    right = {
        row["post_id"]: row for row in rows if row["role"] == "right" and row["outcome"] is not None
    }
    pairs = []
    for row in left:
        candidates = []
        duration = row["features"].get("duration_seconds")
        if duration is None:
            continue
        for other in right.values():
            if any(
                row[key] != other[key]
                for key in (
                    "platform",
                    "creator_id",
                    "niche",
                    "content_type",
                    "topics",
                    "window_seconds",
                )
            ):
                continue
            other_duration = other["features"].get("duration_seconds")
            if other_duration is None or row["age_seconds"] is None or other["age_seconds"] is None:
                continue
            if abs(row["age_seconds"] - other["age_seconds"]) > spec.age_tolerance_days * 86400:
                continue
            distance = abs(duration - other_duration)
            if distance <= spec.duration_caliper_seconds:
                candidates.append((distance, other["post_id"]))
        if candidates:
            _, other_id = min(candidates)
            pairs.append((row["post_id"], other_id))
            right.pop(other_id)
    return pairs
