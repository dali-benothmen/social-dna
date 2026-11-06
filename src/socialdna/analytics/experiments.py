"""Prespecified matched-block assignment contrasts, not viewer or mediator effects."""

from typing import Any

import numpy as np
from scipy.stats import t
from statsmodels.stats.multitest import multipletests

from socialdna.research.experiments import ExperimentSpec

METHOD = "paired-assignment-1"


def analyze(spec: ExperimentSpec, snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = snapshot["rows"]
    common = list(snapshot["threats"])
    if spec.assignment_method != "engine_block_randomized":
        common.append(
            "Nonrandomized or native-arm aggregate design; no supported assignment estimator"
        )
    blocks = sorted({r["block"] for r in rows})
    if len(blocks) < 20:
        common.append("Fewer than twenty independent matched blocks (engineering gate, not power)")
    results: list[dict[str, Any]] = []
    control, treatment = (v.key for v in spec.variants)
    for outcome in spec.outcomes:
        available = [r for r in rows if r["values"].get(outcome.key) is not None]
        reasons = list(common)
        if len(available) != len(spec.units):
            reasons.append(
                "Missing assigned outcomes; no complete-case causal estimate or imputed zero"
            )
        groups = {
            arm: [r["values"][outcome.key] for r in available if r["assigned"] == arm]
            for arm in (control, treatment)
        }
        means = {arm: float(np.mean(values)) if values else None for arm, values in groups.items()}
        left, right = means[control], means[treatment]
        estimate = right - left if left is not None and right is not None else None
        item: dict[str, Any] = {
            "key": outcome.key,
            "role": outcome.role,
            "means": means,
            "available_units": len(available),
            "assigned_units": len(spec.units),
            "estimate": estimate,
            "ci_low": None,
            "ci_high": None,
            "p_value": None,
            "adjusted_p_value": None,
            "reasons": reasons,
            "disposition": "insufficient_data",
            "claim_level": "descriptive_observational",
            "estimand": "observed available-unit mean difference, not an ITT estimate",
        }
        if not reasons:
            differences = []
            for block in blocks:
                pair = [r for r in rows if r["block"] == block]
                by_arm = {r["assigned"]: r["values"][outcome.key] for r in pair}
                differences.append(by_arm[treatment] - by_arm[control])
            values = np.array(differences, dtype=float)
            effect = float(np.mean(values))
            se = float(np.std(values, ddof=1) / np.sqrt(len(values)))
            # Zero residual variation cannot supply a calibrated population interval.
            if se < 1e-12:
                item["reasons"].append("Degenerate block differences; uncertainty withheld")
            else:
                rng = np.random.default_rng(spec.seed)
                signs = rng.choice([-1, 1], size=(spec.permutation_resamples, len(values)))
                simulated = (signs * values).mean(axis=1)
                p_value = (1 + np.count_nonzero(abs(simulated) >= abs(effect) - 1e-12)) / (
                    len(simulated) + 1
                )
                # Bonferroni simultaneous intervals across the entire declared family;
                # Holm p adjustment below includes unavailable endpoints as p=1.
                critical = float(t.ppf(1 - 0.05 / (2 * len(spec.outcomes)), len(values) - 1))
                item.update(
                    estimate=effect,
                    ci_low=effect - critical * se,
                    ci_high=effect + critical * se,
                    p_value=float(p_value),
                    claim_level="randomized_assignment_effect_conditional_on_review",
                    estimand="equal matched-block assignment contrast; not viewer-weighted",
                    n_blocks=len(blocks),
                    interval_method="simultaneous paired-t across independent blocks",
                    test_null="sharp no-assignment-effect; within-block swaps with +1 correction",
                )
        results.append(item)
    adjusted = multipletests(
        [r["p_value"] if r["p_value"] is not None else 1 for r in results], method="holm"
    )[1]
    for item, adjusted_p, outcome in zip(results, adjusted, spec.outcomes, strict=True):
        if item["p_value"] is None:
            continue
        item["adjusted_p_value"] = float(adjusted_p)
        low, high = item["ci_low"], item["ci_high"]
        lower, upper = (low, high) if outcome.direction == "positive" else (-high, -low)
        item["disposition"] = (
            "supported_in_scope"
            if adjusted_p <= 0.05 and lower > outcome.minimum_meaningful_difference
            else "contradicted_in_scope"
            if adjusted_p <= 0.05 and upper < 0
            else "inconclusive"
        )
    return {
        "method": METHOD,
        "outcomes": results,
        "threats": common,
        "claim_level": results[next(i for i, o in enumerate(spec.outcomes) if o.role == "primary")][
            "claim_level"
        ],
        "mechanism_status": "not_identified_even_if_construct_measure_changes",
        "actual_assignment_unit": spec.assignment_unit,
        "registered_units": len(spec.units),
        "multiplicity": {
            "p_values": "Holm",
            "intervals": "Bonferroni paired-t",
            "family_size": len(spec.outcomes),
            "sequential_guarantee": False,
        },
        "limitations": [
            "Source execution reviews are attestations, not automatic verification.",
            "Assignment effects require the design, no interference and valid measurement.",
            "Platform audience allocation is not itself randomized by post assignment.",
            "No mediator, sustained growth or universal transfer follows automatically.",
        ],
    }
