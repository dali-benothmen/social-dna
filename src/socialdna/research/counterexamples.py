"""Deterministic contrary cases from the full protected population, never semantic top-K."""

from typing import Any

import numpy as np


def counterexamples(
    pipeline: Any, train: list[dict[str, Any]], test: list[dict[str, Any]]
) -> dict[str, Any]:
    prediction = pipeline.predict(test)
    threshold = float(np.median([r["outcome"] for r in train]))
    cases = []
    for row, value in zip(test, prediction, strict=True):
        if (value >= threshold) != (row["outcome"] >= threshold):
            cases.append(
                {
                    "unit_id": row["unit_id"],
                    "observed": row["outcome"],
                    "predicted": float(value),
                    "niche": row["niche"],
                    "direction": "predicted_high_observed_low"
                    if value >= threshold
                    else "predicted_low_observed_high",
                    "evidence": row["evidence"],
                }
            )
    cases.sort(key=lambda c: (-abs(c["predicted"] - c["observed"]), c["unit_id"]))
    return {
        "count": len(cases),
        "examples": cases[:20],
        "threshold": threshold,
        "selection": "largest signed prediction contradictions; training median threshold",
        "limitation": "Not proof that a technique was absent or a mechanism was falsified",
    }
