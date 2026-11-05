"""Conservative branching aggregate rates; no individual journey reconstruction."""

from typing import Any

from socialdna.domain.profile import FunnelRate


def rates(
    stages: dict[str, dict[str, Any]], requests: tuple[FunnelRate, ...], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    result = []
    for request in requests:
        numerator, denominator = stages[request.numerator], stages[request.denominator]
        reason = None
        if (
            not request.source_reports_subset
            or not request.linkage_evidence
            or manifest["join_basis"] != "source_reported_nested_counts"
        ):
            reason = "unlinked_aggregates_do_not_establish_a_conversion_probability"
        elif manifest["deduplication"] != "source_unique_per_window" or any(
            r["uniqueness"] != "unique_accounts" for r in (numerator, denominator)
        ):
            reason = "source_uniqueness_or_deduplication_unknown"
        elif numerator["cohort"] != denominator["cohort"] or not all(
            r["cohort_known"] for r in (numerator, denominator)
        ):
            reason = "incompatible_or_unknown_cohorts"
        elif any(
            r["availability"] != "available" or r["value"] is None for r in (numerator, denominator)
        ):
            reason = "missing_required_owner_metrics"
        elif any(
            r["clock"]["data_cutoff"] != r["clock"]["window_end"] for r in (numerator, denominator)
        ) or any(
            numerator["clock"][key] != denominator["clock"][key]
            for key in ("window_start", "window_end", "data_cutoff")
        ):
            reason = "incompatible_or_incomplete_windows"
        elif (
            numerator["population_basis"] != "accounts"
            or denominator["population_basis"] != "accounts"
            or numerator["unit"] != denominator["unit"]
        ):
            reason = "incompatible_denominator_units_or_populations"
        elif denominator["value"] <= 0:
            reason = "nonpositive_denominator"
        elif not 0 <= numerator["value"] <= denominator["value"]:
            reason = "source_nested_counts_contradicted"
        result.append(
            {
                "numerator": numerator["signal"],
                "denominator": denominator["signal"],
                "numerator_evidence": numerator["evidence"],
                "denominator_evidence": denominator["evidence"],
                "value": None if reason else numerator["value"] / denominator["value"],
                "reason": reason,
                "claim_level": "source_qualified_aggregate_rate_not_individual_path",
            }
        )
    return result
