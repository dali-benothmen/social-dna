"""Conservative aggregation of supplied conversion attribution."""

from typing import Any


def summarize_attribution(observations: list[dict[str, Any]]) -> dict[str, Any]:
    seen: dict[str, dict[str, Any]] = {}
    unique, excluded, reasons = [], [], []
    for row in observations:
        spec = row["spec"]
        key = spec["deduplication_key"]
        comparable = {k: v for k, v in spec.items() if k != "key"}
        if key in seen:
            excluded.append(row["ref"])
            if seen[key] != comparable:
                reasons.append("conflicting_duplicate_event_set")
            continue
        seen[key] = comparable
        unique.append(row)
    ordered = sorted(unique, key=lambda r: r["spec"]["clock"]["window_start"])
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left["spec"]["clock"]["window_end"] > right["spec"]["clock"]["window_start"]:
            reasons.append("overlapping_conversion_windows; independent_events_not_established")
    for row in unique:
        spec = row["spec"]
        if spec["attribution_type"] == "unknown":
            reasons.append("unknown_attribution")
        if spec["allocation_policy"] == "full_credit_each":
            reasons.append("nonadditive_multi_touch_credit")
        if row["result"]["value"] is None:
            reasons.append("missing_conversion_measurement")
        if spec["clock"]["data_cutoff"] != spec["clock"]["window_end"]:
            reasons.append("unknown_or_incomplete_source_freshness")
    signatures = {
        (
            r["spec"]["definition"]["revision_id"],
            r["spec"]["cohort"]["revision_id"],
            r["spec"]["model"],
            r["spec"]["allocation_policy"],
            r["spec"]["attribution_type"],
        )
        for r in unique
    }
    if len(signatures) > 1:
        reasons.append("incompatible_attribution_definitions_cohorts_or_models")
    if not unique:
        reasons.append("not_supplied; creator-authorized conversion data is required")
    return {
        "source_reported_total": sum(r["result"]["value"] for r in unique) if not reasons else None,
        "observations": unique,
        "duplicate_refs_excluded": excluded,
        "limitations": sorted(set(reasons)),
        "causal_effect": None,
        "claim_scope": "source-reported attribution, not experimentally identified effects",
    }
