from typing import Any

from socialdna.domain.research import PerformanceSpec


def select_snapshot(
    snapshots: list[dict[str, Any]],
    spec: PerformanceSpec,
) -> tuple[dict[str, Any] | None, str]:
    """One snapshot per post/key, never one independent sample per collection."""
    if not snapshots:
        return None, "not_supplied"
    target, tolerance = spec.age_days * 86400, spec.age_tolerance_days * 86400
    superseded = {row["supersedes_id"] for row in snapshots if row.get("supersedes_id")}
    candidates = []
    for row in snapshots:
        age = row["post_age_seconds"]
        if row["id"] in superseded or age is None or abs(age - target) > tolerance:
            continue
        if spec.window_seconds is not None:
            if not row["window_start"] or not row["window_end"]:
                continue
            from datetime import datetime

            width = (
                datetime.fromisoformat(row["window_end"])
                - datetime.fromisoformat(row["window_start"])
            ).total_seconds()
            if width != spec.window_seconds:
                continue
        candidates.append(row)
    if not candidates:
        return None, "no_age_aligned_snapshot"
    candidates.sort(
        key=lambda row: (abs(row["post_age_seconds"] - target), row["observed_at"], row["id"])
    )
    selected = candidates[0]
    # Independent sources disagreeing about the same measurement are not silently averaged.
    peers = [
        row
        for row in candidates
        if row["observed_at"] == selected["observed_at"]
        and row["window_start"] == selected["window_start"]
        and row["window_end"] == selected["window_end"]
    ]
    if len({(row["value"], row["availability"]) for row in peers}) > 1:
        return None, "conflicting_sources"
    return selected, selected["availability"]


def outcome(
    selected: dict[str, dict[str, Any] | None], spec: PerformanceSpec
) -> tuple[float | None, str]:
    keys = (spec.metric_key, *spec.numerator_keys)
    required = (*keys, spec.denominator_key) if spec.denominator_key else keys
    rows = [selected.get(key) for key in required if key]
    if any(row is None or row["availability"] != "available" for row in rows):
        return None, "missing_required_metric"
    present = [row for row in rows if row is not None]
    if len({(row["observed_at"], row["window_start"], row["window_end"]) for row in present}) != 1:
        return None, "unaligned_rate_inputs"
    numerator_rows = [selected[key] for key in keys]
    total = sum(float(row["value"]) for row in numerator_rows if row is not None)
    if spec.denominator_key:
        denominator_row = selected[spec.denominator_key]
        assert denominator_row is not None
        denominator = float(denominator_row["value"])
        if denominator <= 0:
            return None, "nonpositive_denominator"
        return total / denominator, "available"
    return total, "available"


def account_size_as_of(
    measurements: list[dict[str, Any]],
    world_cutoff: str,
    knowledge_cutoff: str,
    *,
    exact: bool = False,
) -> dict[str, Any]:
    """Actual known follower snapshot, never a later/nearest-post proxy."""
    candidates = [
        row
        for row in measurements
        if row["available_at"] <= knowledge_cutoff
        and row["spec"]["clock"]["data_cutoff"] is not None
        and row["spec"]["clock"]["data_cutoff"] == row["spec"]["clock"]["window_end"]
        and (
            row["spec"]["clock"]["data_cutoff"] == world_cutoff
            if exact
            else row["spec"]["clock"]["data_cutoff"] <= world_cutoff
        )
    ]
    if not candidates:
        return {
            "value": None,
            "availability": "not_supplied",
            "reason": "No genuinely known matching account snapshot",
            "measurement": None,
        }
    latest = max(row["spec"]["clock"]["data_cutoff"] for row in candidates)
    peers = [row for row in candidates if row["spec"]["clock"]["data_cutoff"] == latest]
    if len({(row["result"]["value"], row["result"]["availability"]) for row in peers}) != 1:
        return {
            "value": None,
            "availability": "unavailable",
            "reason": "conflicting_endpoint_sources",
            "measurement": None,
        }
    row = peers[0]
    return {**row["result"], "measurement": row["ref"], "data_cutoff": latest}
