from typing import Any

import numpy as np


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
