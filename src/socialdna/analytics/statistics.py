"""Conservative post-level inference with explicit method-specific gates."""

import warnings
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import PerfectSeparationError

from socialdna.analytics.baselines import creator_baselines, robust_summary, time_aware_baselines
from socialdna.analytics.cohorts import balance_diagnostics, designed_pairs, match_pairs
from socialdna.analytics.validation import predictive_validation, validate_pipeline
from socialdna.domain.research import CorrectedPerformanceSpec, PerformanceSpec


def adjust_fdr(results: list[dict[str, Any]]) -> None:
    tested = [row for row in results if row.get("p_value") is not None]
    if tested:
        # BY is conservative under arbitrary dependence between exploratory features.
        adjusted = multipletests([row["p_value"] for row in tested], method="fdr_by")[1]
        for row, value in zip(tested, adjusted, strict=True):
            row["adjusted_p_value"] = float(value)


def bootstrap_median(
    values: list[float], clusters: list[str], spec: PerformanceSpec
) -> dict[str, Any]:
    if len(values) < 5 or len(set(clusters)) < 2:
        return {"ci_low": None, "ci_high": None, "status": "insufficient_data"}
    rng = np.random.default_rng(spec.seed)
    data = np.asarray(values)
    group_names = sorted(set(clusters))
    groups = {name: data[np.array(clusters) == name] for name in group_names}
    estimates = [
        np.median(
            np.concatenate([groups[name] for name in rng.choice(group_names, len(group_names))])
        )
        for _ in range(spec.bootstrap_resamples)
    ]
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {
        "ci_low": float(low),
        "ci_high": float(high),
        "status": "exploratory",
        "method": "creator-cluster percentile bootstrap",
        "resamples": spec.bootstrap_resamples,
        "cluster_count": len(groups),
    }


def correlations(rows: list[dict[str, Any]], spec: PerformanceSpec) -> list[dict[str, Any]]:
    results = []
    for feature in spec.features:
        paired = [
            row
            for row in rows
            if row["outcome"] is not None and row["features"].get(feature) is not None
        ]
        result: dict[str, Any] = {
            "term": f"spearman:{feature}",
            "estimate": None,
            "p_value": None,
            "adjusted_p_value": None,
            "sample_count": len(paired),
            "cluster_count": len({row["creator_id"] for row in paired}),
            "diagnostics": {},
        }
        if len(paired) >= 3:
            x, y = (
                [row["features"][feature] for row in paired],
                [row["outcome"] for row in paired],
            )
            if len(set(x)) > 1 and len(set(y)) > 1:
                result["estimate"] = float(stats.spearmanr(x, y).statistic)
                # Post-level rank correlation is descriptive. A separate creator-aggregate
                # permutation test avoids pretending repeated posts are independent.
                if result["cluster_count"] >= 20:
                    frame = pd.DataFrame(
                        {"x": x, "y": y, "creator": [r["creator_id"] for r in paired]}
                    )
                    grouped = frame.groupby("creator", sort=True)[["x", "y"]].median()
                    gx, gy = grouped.x.to_numpy(), grouped.y.to_numpy()
                    if len(set(gx)) > 1 and len(set(gy)) > 1:
                        observed = float(stats.spearmanr(gx, gy).statistic)
                        # Rank once; permutation of ranks is Spearman's permutation null.
                        rx, ry = stats.rankdata(gx), stats.rankdata(gy)
                        rng = np.random.default_rng(spec.seed)
                        samples = [
                            float(np.corrcoef(rx, rng.permutation(ry))[0, 1])
                            for _ in range(spec.bootstrap_resamples)
                        ]
                        p = (1 + sum(abs(value) >= abs(observed) for value in samples)) / (
                            1 + len(samples)
                        )
                        result["diagnostics"] = {
                            "creator_median_spearman": observed,
                            "creator_aggregate_p_value": p,
                            "permutations": len(samples),
                            "note": "Aggregate test differs from descriptive post correlation.",
                        }
                        # Do not attach the aggregate p-value to a different, post-level estimand.
                else:
                    result["diagnostics"]["limitation"] = (
                        "insufficient_data: fewer than 20 creator clusters; no correlation test"
                    )
        results.append(result)
    # Correct the actual creator-aggregate test family, not the descriptive post effects.
    aggregate = [
        {"p_value": r["diagnostics"]["creator_aggregate_p_value"], "result": r}
        for r in results
        if "creator_aggregate_p_value" in r["diagnostics"]
    ]
    adjust_fdr(aggregate)
    for row in aggregate:
        row["result"]["diagnostics"]["creator_aggregate_adjusted_p_value"] = row["adjusted_p_value"]
    return results


def regression(rows: list[dict[str, Any]], spec: PerformanceSpec) -> dict[str, Any]:
    if spec.model == "none":
        return {"status": "not_requested", "terms": []}
    complete = sorted(
        [
            row
            for row in rows
            if row["outcome"] is not None
            and all(row["features"].get(key) is not None for key in spec.features)
        ],
        key=lambda row: (row["published_at"], row["post_id"]),
    )
    n = len(complete)
    clusters = sorted({row["creator_id"] for row in complete})
    skipped: dict[str, Any] = {
        "status": "insufficient_data",
        "terms": [],
        "sample_count": n,
        "cluster_count": len(clusters),
    }
    if not spec.features or n < 30:
        return {
            **skipped,
            "reason": "At least 30 complete posts and one declared feature are required",
        }
    frame = pd.DataFrame(
        {key: [row["features"][key] for row in complete] for key in spec.features}, dtype=float
    )
    for left, right in spec.interactions:
        frame[f"{left}*{right}"] = frame[left] * frame[right]
    # Adjust explicitly observed platform/type differences. No arbitrary formula evaluation.
    confounders = pd.DataFrame(
        {
            key: [row[key] or "unsupplied" for row in complete]
            for key in ("platform", "content_type", "niche")
        }
    )
    frame = pd.concat([frame, pd.get_dummies(confounders, drop_first=True, dtype=float)], axis=1)
    if spec.model in ("ols", "poisson") and len(clusters) > 1:
        frame = pd.concat(
            [
                frame,
                pd.get_dummies(
                    pd.Series([r["creator_id"] for r in complete], name="creator"),
                    prefix="creator",
                    drop_first=True,
                    dtype=float,
                ),
            ],
            axis=1,
        )
    design = sm.add_constant(frame, has_constant="add").to_numpy(dtype=float)
    terms = ["intercept", *frame.columns.tolist()]
    outcome_values = np.array([row["outcome"] for row in complete])
    if n < 10 * design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
        return {
            **skipped,
            "reason": "Insufficient observations per parameter or collinear/constant predictors",
        }
    if np.std(outcome_values) == 0:
        return {**skipped, "reason": "Constant outcome"}
    if len(clusters) > 1 and len(clusters) < 20:
        return {**skipped, "reason": "Repeated-creator inference requires at least 20 clusters"}
    if spec.model in ("gee", "mixed") and (
        len(clusters) < 20
        or min(sum(row["creator_id"] == group for row in complete) for group in clusters) < 3
    ):
        return {**skipped, "reason": "GEE/mixed require at least 20 creators with 3 posts each"}
    if spec.model == "poisson" and (
        np.any(outcome_values < 0) or np.any(outcome_values != np.floor(outcome_values))
    ):
        return {**skipped, "reason": "Poisson outcome must be a non-negative count"}
    condition = float(np.linalg.cond(design))
    if condition > 1e8:
        return {
            **skipped,
            "reason": "Ill-conditioned design; respecify/scalably transform predictors",
        }
    group_values = [row["creator_id"] for row in complete]
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            base_ols = sm.OLS(outcome_values, design).fit()
            if np.var(base_ols.resid) < 1e-12:
                return {**skipped, "reason": "Perfect prediction; no residual uncertainty"}
            influence = base_ols.get_influence()
            if spec.model == "gee":
                fitted = sm.GEE(
                    outcome_values,
                    design,
                    groups=group_values,
                    family=sm.families.Gaussian(),
                    cov_struct=sm.cov_struct.Exchangeable(),
                ).fit()
            elif spec.model == "mixed":
                fitted = sm.MixedLM(outcome_values, design, groups=group_values).fit(
                    reml=True, method="lbfgs", disp=False
                )
            elif spec.model == "poisson":
                covariance = (
                    {"cov_type": "cluster", "cov_kwds": {"groups": group_values}}
                    if len(clusters) > 1
                    else {"cov_type": "HAC", "cov_kwds": {"maxlags": min(3, n // 10)}}
                )
                fitted = sm.GLM(outcome_values, design, family=sm.families.Poisson()).fit(
                    **covariance
                )
                dispersion = float(fitted.pearson_chi2 / fitted.df_resid)
                if dispersion > 2:
                    return {
                        **skipped,
                        "reason": "Poisson overdispersion >2; choose a different model",
                        "dispersion": dispersion,
                    }
            else:
                fitted = (
                    base_ols.get_robustcov_results(cov_type="cluster", groups=group_values)
                    if len(clusters) > 1
                    else base_ols.get_robustcov_results(cov_type="HAC", maxlags=min(3, n // 10))
                )
        if captured or not getattr(fitted, "converged", True):
            return {
                **skipped,
                "reason": "Model warnings/non-convergence; no unstable estimates released",
                "warnings": sorted({type(item.message).__name__ for item in captured}),
            }
        count = len(terms)
        if not np.all(np.isfinite(np.asarray(fitted.params)[:count])) or not np.all(
            np.isfinite(np.asarray(fitted.conf_int())[:count])
        ):
            return {**skipped, "reason": "Non-finite model estimates"}
        intervals = np.asarray(fitted.conf_int())
        results = [
            {
                "term": str(term),
                "estimate": float(fitted.params[index]),
                "standard_error": float(fitted.bse[index]),
                "ci_low": float(intervals[index, 0]),
                "ci_high": float(intervals[index, 1]),
                "p_value": float(fitted.pvalues[index]),
                "sample_count": n,
                "cluster_count": len(clusters),
            }
            for index, term in enumerate(terms)
        ]
        adjust_fdr(results)
        cook = np.asarray(influence.cooks_distance[0])
        leverage = np.asarray(influence.hat_matrix_diag)
        flagged = [
            complete[index]["post_id"]
            for index in range(n)
            if cook[index] > 4 / n or leverage[index] > 2 * design.shape[1] / n
        ]
        return {
            "status": "fitted",
            "method": spec.model,
            "terms": results,
            "condition_number": condition,
            "sample_count": n,
            "cluster_count": len(clusters),
            "diagnostics": {
                "influential_post_ids": flagged,
                "influence_method": "OLS design sensitivity (not GLM/random-effect influence)",
                "max_cooks_distance": float(np.max(cook)),
                "max_leverage": float(np.max(leverage)),
            },
            "limitations": [
                "Observational adjusted association, not a causal finding.",
                "Unmeasured confounding, creator selection, and serial dependence can remain.",
            ],
        }
    except (
        ValueError,
        np.linalg.LinAlgError,
        ZeroDivisionError,
        PerfectSeparationError,
        FloatingPointError,
        OverflowError,
    ) as exc:
        return {**skipped, "reason": f"Unstable model: {type(exc).__name__}"}


def comparison(rows: list[dict[str, Any]], spec: PerformanceSpec) -> dict[str, Any]:
    pairs = match_pairs(rows, spec) if spec.matched else []
    by_id = {row["post_id"]: row for row in rows}
    left = [row["outcome"] for row in rows if row["role"] == "left" and row["outcome"] is not None]
    right = [
        row["outcome"] for row in rows if row["role"] == "right" and row["outcome"] is not None
    ]
    result: dict[str, Any] = {
        "left": robust_summary(left),
        "right": robust_summary(right),
        "matched": spec.matched,
        "pairs": pairs,
        "unmatched_median_difference": float(np.median(left) - np.median(right))
        if left and right
        else None,
        "claim_level": "observation",
        "limitations": [
            "Comparisons are not causal; unmatched group differences may be confounded."
        ],
    }
    if spec.matched:
        differences = [by_id[a]["outcome"] - by_id[b]["outcome"] for a, b in pairs]
        groups = [by_id[a]["creator_id"] for a, _ in pairs]
        result["matched_effect"] = {
            **robust_summary(differences),
            **bootstrap_median(differences, groups, spec),
        }
        if len(pairs) < 5:
            result["limitations"].append(
                "insufficient_data: fewer than five comparable matched pairs"
            )
    elif left and right:
        # A raw-scale median effect is more interpretable than a standardized effect for counts.
        result["effect_size"] = {
            "estimand": "left minus right post median",
            "estimate": result["unmatched_median_difference"],
        }
        result["limitations"].append(
            "Unmatched effects are descriptive; no independence-based p-value is issued."
        )
    return result


def analyze_rows(
    rows: list[dict[str, Any]], spec: PerformanceSpec, *, comparing: bool = False
) -> dict[str, Any]:
    available = [row for row in rows if row["outcome"] is not None]
    missingness = (
        pd.Series([row["availability"] for row in rows], dtype="string").value_counts().to_dict()
    )
    outcome_values = [row["outcome"] for row in available]
    limitations = [
        "Snapshots use the declared age/window tolerance; no exposure interpolation.",
        "Missing engagement components are never imputed as zero.",
        "Associations are not causal; creator/content selection and unmeasured confounding remain.",
    ]
    if len(available) < 30:
        limitations.append(
            "insufficient_data: fewer than 30 usable posts; descriptive results only"
        )
    model = regression(rows, spec)
    if model["status"] == "insufficient_data":
        limitations.append("insufficient_data: " + model["reason"])
    if len({row["creator_id"] for row in available}) < 20:
        limitations.append(
            "insufficient_data: fewer than 20 creator clusters; no cross-creator significance"
        )
    return {
        "claim_level": "observation" if model["status"] != "fitted" else "association",
        "population_n": len(rows),
        "available_n": len(available),
        "missing_n": len(rows) - len(available),
        "missingness": {str(k): int(v) for k, v in missingness.items()},
        "feature_missingness": {
            key: sum(row["features"].get(key) is None for row in rows) for key in spec.features
        },
        "outcome": robust_summary(outcome_values),
        "outcome_interval": bootstrap_median(
            outcome_values, [r["creator_id"] for r in available], spec
        ),
        "observation_age_seconds": robust_summary([row["age_seconds"] for row in available]),
        "creator_baselines": creator_baselines(rows),
        "correlations": correlations(rows, spec),
        "regression": model,
        "validation": predictive_validation(rows, spec.features, spec.seed),
        "comparison": comparison(rows, spec) if comparing else None,
        "multiple_testing": "Benjamini-Yekutieli FDR per test family; all terms retained",
        "limitations": limitations,
    }


def designed_comparison(
    rows: list[dict[str, Any]], spec: CorrectedPerformanceSpec
) -> dict[str, Any]:
    pairs = designed_pairs(rows, spec) if spec.design != "descriptive" else []
    balance = balance_diagnostics(rows, pairs, spec)
    retained = {item for pair in pairs for item in pair}
    by_id = {row["post_id"]: row for row in rows}
    supported = len(pairs) >= 5 and all(
        value["after"]["smd"] is not None and abs(value["after"]["smd"]) <= spec.max_abs_smd
        for value in balance.values()
    )
    differences = [by_id[a]["outcome"] - by_id[b]["outcome"] for a, b in pairs]
    return {
        "design": spec.design,
        "estimand": spec.estimand,
        "left": robust_summary(
            [r["outcome"] for r in rows if r["role"] == "left" and r["outcome"] is not None]
        ),
        "right": robust_summary(
            [r["outcome"] for r in rows if r["role"] == "right" and r["outcome"] is not None]
        ),
        "status": "descriptive"
        if spec.design == "descriptive"
        else ("supported_descriptive" if supported else "insufficient_overlap"),
        "pairs": pairs,
        "replacement": False,
        "tie_break": "distance then post ID",
        "balance": balance,
        "retained_n": len(retained),
        "dropped_post_ids": sorted(set(by_id) - retained),
        "effective_creator_count": len({by_id[item]["creator_id"] for item in retained}),
        "matched_effect": {
            **robust_summary(differences),
            "estimate": float(np.median(differences)) if supported else None,
            "ci_low": None,
            "ci_high": None,
            "status": "descriptive_only" if supported else "withheld",
        },
        "caliper_sensitivity": {
            str(factor): len(designed_pairs(rows, spec, multiplier=factor))
            for factor in (0.5, 1, 2)
        }
        if spec.design != "descriptive"
        else {},
        "unknown_confounders": [
            "as-of audience",
            "paid distribution",
            "traffic source",
            "collaboration",
            "timezone",
        ],
        "limitations": [
            "Matched left-minus-right post differences are observational, not causal.",
            "Measured balance cannot establish exchangeability; unknown confounding remains.",
            "Pairs can share creators/content dependence; no pair-independent CI is issued.",
        ],
    }


def analyze_designed_rows(
    rows: list[dict[str, Any]],
    history: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    *,
    comparing: bool,
    split: dict[str, Any],
) -> dict[str, Any]:
    from socialdna.analytics.designs import designed_regression

    available = [r for r in rows if r["outcome"] is not None]
    model = designed_regression(rows, spec)
    missingness = {
        state: sum(r["availability"] == state for r in rows)
        for state in sorted({r["availability"] for r in rows})
    }
    return {
        "method_version": "performance-2",
        "claim_level": "association" if model["status"] == "fitted" else "observation",
        "estimand": spec.estimand,
        "population_n": len(rows),
        "available_n": len(available),
        "missing_n": len(rows) - len(available),
        "missingness": missingness,
        "feature_missingness": {
            key: sum(not r["feature_values"][key]["eligible"] for r in rows)
            for key in spec.features
        },
        "outcome": robust_summary([r["outcome"] for r in available]),
        "outcome_interval": {"ci_low": None, "ci_high": None, "status": "descriptive_only"},
        "observation_age_seconds": robust_summary(
            [r["age_seconds"] for r in available if r["age_seconds"] is not None]
        ),
        "creator_baselines": time_aware_baselines(rows, history, spec),
        "correlations": [],
        "regression": model,
        "validation": validate_pipeline(rows, spec, split),
        "comparison": designed_comparison(rows, spec) if comparing else None,
        "multiple_testing": (
            "Declared fixed-family BY; untested terms assigned p=1. "
            "Repeated attempts are exploratory, not global adaptive FDR control."
        ),
        "limitations": [
            "Observational association only; unknown confounding and sampling selection remain.",
            "Population is the declared canonical SQL sampling frame, never vector neighbors.",
            "Exact hashes group known duplicates; near-duplicate/unlinked coverage is unknown.",
            "Imported captions do not establish historical wording. "
            "Account niche is profile context, not a post-level label.",
            "Small-sample gates are engineering safeguards, not power guarantees.",
        ]
        + (
            ["Collection age is only a freshness proxy; strict maturity inference is withheld."]
            if spec.maturity_policy == "collection_proxy"
            else []
        )
        + ([model["reason"]] if model["status"] == "insufficient_data" else []),
    }
