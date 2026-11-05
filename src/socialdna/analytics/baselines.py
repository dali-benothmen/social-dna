from typing import Any

import numpy as np

from socialdna.domain.research import CorrectedPerformanceSpec


def robust_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "median": None,
            "mad": None,
            "mean": None,
            "q25": None,
            "q75": None,
            "min": None,
            "max": None,
        }
    data = np.asarray(values, dtype=float)
    median = float(np.median(data))
    return {
        "n": len(data),
        "median": median,
        "mad": float(np.median(abs(data - median))),
        "mean": float(np.mean(data)),
        "q25": float(np.quantile(data, 0.25)),
        "q75": float(np.quantile(data, 0.75)),
        "min": float(min(data)),
        "max": float(max(data)),
    }


def creator_baselines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for creator in sorted({row["creator_id"] for row in rows}):
        members = [
            row for row in rows if row["creator_id"] == creator and row["outcome"] is not None
        ]
        summary = robust_summary([row["outcome"] for row in members])
        scores = []
        # Leave-one-post-out: a post cannot define its own normalization denominator.
        for row in members:
            reference = robust_summary(
                [other["outcome"] for other in members if other["post_id"] != row["post_id"]]
            )
            median, mad = reference["median"], reference["mad"]
            scores.append(
                {
                    "post_id": row["post_id"],
                    "reference_n": reference["n"],
                    "median_ratio": row["outcome"] / median
                    if median and reference["n"] >= 3
                    else None,
                    "robust_z": (row["outcome"] - median) / (1.4826 * mad)
                    if mad and reference["n"] >= 3
                    else None,
                }
            )
        results.append({"creator_id": creator, **summary, "leave_one_out_scores": scores})
    return results


def time_aware_baselines(
    rows: list[dict[str, Any]],
    history: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
) -> list[dict[str, Any]]:
    """Exact reference manifests, without fallback or exposure interpolation."""
    from datetime import datetime, timedelta

    creators: dict[str, list[dict[str, Any]]] = {}
    for row in rows if spec.baseline_policy == "retrospective_cohort" else history:
        creators.setdefault(row["creator_id"], []).append(row)
    results = []
    for target in rows:
        cutoff = (
            min(spec.knowledge_cutoff, target["published_at"] or spec.knowledge_cutoff)
            if (spec.baseline_cutoff == "publication")
            else spec.knowledge_cutoff
        )
        lower = (
            (datetime.fromisoformat(cutoff) - timedelta(days=spec.baseline_lookback_days))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        reference, exclusions = [], []
        candidates = creators.get(target["creator_id"], [])
        for candidate in candidates:
            other = candidate
            if spec.baseline_policy == "historical_as_of" and "snapshot_candidates" in candidate:
                from socialdna.analytics.metrics import outcome, select_snapshot

                selected = {
                    key: select_snapshot(
                        [r for r in snapshots if max(r["imported_at"], r["observed_at"]) <= cutoff],
                        spec,
                    )[0]
                    for key, snapshots in candidate["snapshot_candidates"].items()
                }
                value, _ = outcome(selected, spec)
                chosen = [r for r in selected.values() if r]
                other = {
                    **candidate,
                    "outcome": value,
                    "outcome_available_at": max(
                        (max(r["imported_at"], r["observed_at"]) for r in chosen), default=None
                    ),
                    "snapshot_ids": sorted(r["id"] for r in chosen),
                }
            reason = None
            if other["post_id"] == target["post_id"]:
                reason = "self"
            elif other["creator_id"] != target["creator_id"]:
                continue
            elif other["platform"] != target["platform"]:
                reason = "different_platform"
            elif other["outcome"] is None:
                reason = "missing_or_ineligible_outcome"
            elif spec.baseline_policy == "historical_as_of":
                if not target["published_at"] or not other["published_at"]:
                    reason = "unknown_publication_time"
                elif other["published_at"] >= target["published_at"]:
                    reason = "not_prior_publication"
                elif other["published_at"] < lower:
                    reason = "outside_lookback"
                elif not other["outcome_available_at"] or other["outcome_available_at"] > cutoff:
                    reason = "measurement_not_known_by_cutoff"
            if reason:
                exclusions.append({"post_id": other["post_id"], "reason": reason})
            else:
                reference.append(other)
        summary = robust_summary([row["outcome"] for row in reference])
        sufficient = summary["n"] >= spec.baseline_min_posts
        median, mad = summary["median"], summary["mad"]
        results.append(
            {
                "post_id": target["post_id"],
                "policy": spec.baseline_policy,
                "cutoff": cutoff,
                "reference_post_ids": sorted(row["post_id"] for row in reference),
                "reference_snapshot_ids": sorted(
                    {i for row in reference for i in row["snapshot_ids"]}
                ),
                "exclusions": sorted(exclusions, key=lambda item: item["post_id"]),
                "summary": summary,
                "status": "available" if sufficient else "insufficient_history",
                "median_ratio": target["outcome"] / median
                if (sufficient and median and target["outcome"] is not None)
                else None,
                "robust_z": (target["outcome"] - median) / (1.4826 * mad)
                if (sufficient and mad and target["outcome"] is not None)
                else None,
                "limitations": ["Zero median/MAD scores are unavailable; no epsilon denominator."]
                + (
                    ["Retrospective leave-one-out cohort summary, not a historical benchmark."]
                    if spec.baseline_policy == "retrospective_cohort"
                    else []
                ),
            }
        )
    return results
