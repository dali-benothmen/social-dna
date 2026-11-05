from typing import Any

import numpy as np

from socialdna.domain.research import CorrectedPerformanceSpec, PerformanceSpec, Population


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


def designed_pairs(
    rows: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    *,
    multiplier: float = 1,
) -> list[tuple[str, str]]:
    """Outcome-blind, deterministic, no replacement; different named estimands."""
    usable = [
        row
        for row in rows
        if row["outcome"] is not None
        and all(
            row["feature_values"].get(key, {}).get("eligible", False) for key in spec.covariates
        )
    ]
    scales = {key: float(np.std([r["features"][key] for r in usable])) for key in spec.covariates}
    right = {row["post_id"]: row for row in usable if row["role"] == "right"}
    pairs: list[tuple[str, str]] = []
    from datetime import datetime

    for row in sorted((r for r in usable if r["role"] == "left"), key=lambda r: r["post_id"]):
        candidates = []
        for other in right.values():
            same_creator = row["creator_id"] == other["creator_id"]
            if (spec.design == "within_creator") != same_creator:
                continue
            if (
                not row["published_at"]
                or not other["published_at"]
                or any(
                    row.get(key) is None or other.get(key) is None or row[key] != other[key]
                    for key in spec.context
                )
            ):
                continue
            if row.get("duplicate_group") and row["duplicate_group"] == other.get(
                "duplicate_group"
            ):
                continue
            if (
                row["age_seconds"] is None
                or other["age_seconds"] is None
                or abs(row["age_seconds"] - other["age_seconds"]) > spec.age_tolerance_days * 86400
                or row["window_seconds"] != other["window_seconds"]
            ):
                continue
            if (
                abs(
                    (
                        datetime.fromisoformat(row["published_at"])
                        - datetime.fromisoformat(other["published_at"])
                    ).total_seconds()
                )
                > spec.publication_caliper_days * 86400
            ):
                continue
            distance = 0.0
            valid = True
            for key, scale in scales.items():
                delta = abs(row["features"][key] - other["features"][key])
                if key == "duration_seconds" and delta > spec.duration_caliper_seconds * multiplier:
                    valid = False
                if scale == 0 and delta != 0:
                    valid = False
                distance += (delta / scale) ** 2 if scale else 0
            if valid and distance**0.5 <= spec.standardized_caliper * multiplier:
                candidates.append((distance, other["post_id"]))
        if candidates:
            _, identity = min(candidates)
            pairs.append((row["post_id"], identity))
            del right[identity]
    return pairs


def balance_diagnostics(
    rows: list[dict[str, Any]],
    pairs: list[tuple[str, str]],
    spec: CorrectedPerformanceSpec,
) -> dict[str, Any]:
    retained = {identity for pair in pairs for identity in pair}

    def distribution(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
        values = [r["features"].get(key) for r in items]
        from socialdna.analytics.baselines import robust_summary

        return {
            **robust_summary([v for v in values if v is not None]),
            "missing_n": sum(v is None for v in values),
        }

    result: dict[str, Any] = {}
    for key in spec.covariates:
        stages = {}
        for stage, sample in (
            ("before", rows),
            ("after", [r for r in rows if r["post_id"] in retained]),
        ):
            left = distribution([r for r in sample if r["role"] == "left"], key)
            right = distribution([r for r in sample if r["role"] == "right"], key)
            lv = [
                r["features"][key]
                for r in sample
                if r["role"] == "left" and r["features"].get(key) is not None
            ]
            rv = [
                r["features"][key]
                for r in sample
                if r["role"] == "right" and r["features"].get(key) is not None
            ]
            scale = float(np.sqrt((np.var(lv) + np.var(rv)) / 2)) if lv and rv else None
            delta = float(np.mean(lv) - np.mean(rv)) if lv and rv else None
            stages[stage] = {
                "left": left,
                "right": right,
                "smd": delta / scale
                if scale and delta is not None
                else (0.0 if delta == 0 else None),
            }
        result[key] = stages
    return result
