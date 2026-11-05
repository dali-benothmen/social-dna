"""Deterministic, conservative judgments over the actual frozen statistical pipeline."""

from collections import Counter
from typing import Any

from socialdna.domain.investigation import HypothesisPlan


def association(plan: HypothesisPlan, analyses: list[dict[str, Any]]) -> dict[str, Any]:
    observations = []
    for report in analyses:
        configuration = report["analysis_configuration"]["spec"]
        if configuration["metric_key"] != plan.prediction.metric_key:
            continue
        model = report["results"]["regression"]
        term = next((t for t in model["terms"] if t["term"] == plan.prediction.feature), None)
        status = "inconclusive"
        if (
            model["status"] == "fitted"
            and term
            and term.get("adjusted_p_value") is not None
            and term["adjusted_p_value"] <= 0.05
            and term.get("ci_low") is not None
            and term.get("ci_high") is not None
            and (term["ci_low"] > 0 or term["ci_high"] < 0)
        ):
            positive = term["ci_low"] > 0
            status = (
                "consistent"
                if positive == (plan.prediction.direction == "positive")
                else "contrary"
            )
        observations.append(
            {
                "run_id": report["run_id"],
                "status": status,
                "term": term,
                "design": configuration["design"],
                "comparison": report["results"].get("comparison"),
                "model_status": model["status"],
                "reason": model.get("reason"),
                "limitations": list(report["limitations"]),
                "ledger": report["test_ledger"],
            }
        )
    decisive = {item["status"] for item in observations} - {"inconclusive"}
    status = (
        "conflicting"
        if len(decisive) > 1
        else next(iter(decisive))
        if decisive
        else "inconclusive"
        if observations
        else "unavailable"
    )
    return {
        "status": status,
        "observations": observations,
        "claim_level": "association" if decisive else "hypothesis",
        "limitation": "A scoped observational association does not identify a mediator or cause.",
    }


def examples(report: dict[str, Any], feature: str) -> dict[str, Any]:
    rows = report["posts"]
    available = [r for r in rows if r["outcome"] is not None]
    ordered = sorted(available, key=lambda r: (r["outcome"], r["post_id"]))
    binary_creative = feature in report["analysis_configuration"]["spec"].get(
        "creative_recipes", {}
    ) and all(r["features"].get(feature) in (None, 0, 1) for r in rows)
    # Bounded exemplars only; the complete SQL population is separately frozen.
    low = {r["post_id"] for r in ordered[: max(1, len(ordered) // 4)]}
    high = {r["post_id"] for r in ordered[-max(1, len(ordered) // 4) :]}
    return {
        "run_id": report["run_id"],
        "feature": feature,
        "selection": "within-analysis outcome quartile exemplars; not a statistical sample",
        "status": "binary_creative_examples"
        if binary_creative
        else "not_a_binary_creative_feature",
        "unsuccessful_uses": [
            r["post_id"] for r in ordered if r["post_id"] in low and r["features"].get(feature) == 1
        ][:5]
        if binary_creative
        else [],
        "alternative_successes": [
            r["post_id"]
            for r in reversed(ordered)
            if r["post_id"] in high and r["features"].get(feature) == 0
        ][:5]
        if binary_creative
        else [],
        "unknown_feature_count": sum(r["features"].get(feature) is None for r in rows),
        "limitation": "Absence of a retrieved counterexample does not establish universality.",
    }


def measurement_quality(plan: HypothesisPlan, reports: list[dict[str, Any]]) -> dict[str, Any]:
    rows = {r["post_id"]: r for report in reports for r in report["posts"]}
    values = [r.get("feature_values", {}).get(plan.prediction.feature) for r in rows.values()]
    measured = [v for v in values if v and v.get("value") is not None]
    return {
        "unique_posts": len(rows),
        "available_feature_count": len(measured),
        "unknown_feature_count": len(values) - len(measured),
        "coverage": dict(Counter(str(v.get("coverage", "unknown")) for v in measured)),
        "outcome_blinding": dict(
            Counter(str(v.get("lineage", {}).get("outcome_blind")) for v in measured)
        ),
        "feature_value_ids": sorted({v["id"] for v in measured}),
        "empirical_label_accuracy": "not_established_by_software_tests",
    }
