"""One declared design matrix and model pipeline, used by fit AND validation."""

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import statsmodels.api as sm

from socialdna.analytics.features import eligible_rows
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.research import CorrectedPerformanceSpec


def raw_terms(row: dict[str, Any], spec: CorrectedPerformanceSpec) -> list[float]:
    values = row["features"]
    return [float(values[key]) for key in spec.features] + [
        float(values[a] * values[b]) for a, b in spec.interactions
    ]


@dataclass
class ModelPipeline:
    spec: CorrectedPerformanceSpec
    creators: list[str]
    means: dict[str, np.ndarray[Any, Any]]
    scales: np.ndarray[Any, Any]
    nuisance: dict[str, list[str]]
    fitted: Any
    manifest: dict[str, Any]

    def matrix(self, rows: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
        if any(row["creator_id"] not in self.creators for row in rows):
            raise ConfigurationError(
                "unsupported_creator_prediction: unseen fixed-effect intercept"
            )
        numeric = (
            np.asarray([raw_terms(row, self.spec) - self.means[row["creator_id"]] for row in rows])
            / self.scales
        )
        columns = [np.ones(len(rows)), *numeric.T]
        for key, levels in self.nuisance.items():
            values = [context_value(row.get(key)) for row in rows]
            if any(value not in levels for value in values):
                raise ConfigurationError(f"Unsupported new context level: {key}")
            columns.extend(
                np.array([value == level for value in values], dtype=float) for level in levels[1:]
            )
        columns.extend(
            np.array([r["creator_id"] == creator for r in rows], dtype=float)
            for creator in self.creators[1:]
        )
        return np.column_stack(columns)

    def predict(self, rows: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
        prediction = np.asarray(self.fitted.predict(self.matrix(rows)), dtype=float)
        if self.spec.target_transform == "log1p":
            prediction = np.expm1(prediction)
        if not np.all(np.isfinite(prediction)):
            raise ConfigurationError("Non-finite model predictions")
        return prediction


def context_value(value: Any) -> str:
    return repr(value)  # frozen lists/strings; None stays an explicitly unknown category


def fit_pipeline(rows: list[dict[str, Any]], spec: CorrectedPerformanceSpec) -> ModelPipeline:
    if spec.model == "none":
        raise ConfigurationError("No model selected")
    if len(rows) < 30 or not spec.features:
        raise ConfigurationError("At least 30 complete posts and one declared feature are required")
    creators = sorted({r["creator_id"] for r in rows})
    raw = np.asarray([raw_terms(row, spec) for row in rows])
    means = {
        creator: raw[[r["creator_id"] == creator for r in rows]].mean(axis=0)
        for creator in creators
    }
    centered = np.asarray([raw[i] - means[row["creator_id"]] for i, row in enumerate(rows)])
    scales = centered.std(axis=0)
    names = [*spec.features, *(f"{a}*{b}" for a, b in spec.interactions)]
    if np.any(scales < 1e-12):
        raise ConfigurationError("No identifiable within-creator variation in a declared term")
    nuisance, absorbed = {}, []
    for key in ("platform", "content_type", "niche", "topics"):
        if all(
            len({context_value(r.get(key)) for r in rows if r["creator_id"] == creator}) == 1
            for creator in creators
        ):
            absorbed.append(key)
        else:
            nuisance[key] = sorted({context_value(row.get(key)) for row in rows})
    pipeline = ModelPipeline(spec, creators, means, scales, nuisance, None, {})
    matrix = pipeline.matrix(rows)
    rank = int(np.linalg.matrix_rank(matrix))
    if rank < matrix.shape[1]:
        raise ConfigurationError("Aliased/rank-deficient declared design; estimand withheld")
    if len(rows) < max(30, 3 * matrix.shape[1]):
        raise ConfigurationError(
            "Insufficient observations per parameter (engineering gate, not power)"
        )
    condition = float(np.linalg.cond(matrix))
    if condition > 1e8:
        raise ConfigurationError("Ill-conditioned declared design")
    target = np.asarray([row["outcome"] for row in rows], dtype=float)
    if np.std(target) == 0:
        raise ConfigurationError("Constant outcome")
    if spec.target_transform == "log1p":
        if np.any(target < 0):
            raise ConfigurationError("log1p target requires nonnegative outcomes")
        target = np.log1p(target)
    if spec.model == "poisson" and (np.any(target < 0) or np.any(target != np.floor(target))):
        raise ConfigurationError("Poisson outcome must be a nonnegative integer count")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        fitted = (
            sm.GLM(target, matrix, family=sm.families.Poisson()).fit()
            if spec.model == "poisson"
            else sm.OLS(target, matrix).fit()
        )
    if captured or not getattr(fitted, "converged", True):
        raise ConfigurationError("Model warnings/non-convergence; unstable estimates withheld")
    dispersion = float(fitted.pearson_chi2 / fitted.df_resid) if spec.model == "poisson" else None
    if dispersion is not None and dispersion > 2:
        raise ConfigurationError("Poisson overdispersion >2; respecify the declared model")
    if not np.all(np.isfinite(np.asarray(fitted.params))):
        raise ConfigurationError("Non-finite model estimates")
    perfect_fit = spec.model == "ols" and float(np.var(fitted.resid)) < 1e-12
    inferential = len(creators) >= 20 and not perfect_fit
    if inferential:
        groups = [row["creator_id"] for row in rows]
        fitted = (
            sm.GLM(target, matrix, family=sm.families.Poisson()).fit(
                cov_type="cluster", cov_kwds={"groups": groups}
            )
            if spec.model == "poisson"
            else fitted.get_robustcov_results(cov_type="cluster", groups=groups)
        )
    pipeline.fitted = fitted
    pipeline.manifest = {
        "method_version": "within-pipeline-2",
        "family": spec.model,
        "covariance": "creator-cluster"
        if inferential
        else (
            "withheld: perfect residual fit"
            if perfect_fit
            else "withheld: fewer than 20 creator clusters"
        ),
        "inferential_uncertainty": inferential,
        "link": "log" if spec.model == "poisson" else "identity",
        "prediction_target": "inverse log1p is conditional transformed-location, not mean"
        if spec.target_transform == "log1p"
        else "conditional raw outcome",
        "target_transform": spec.target_transform,
        "numeric_terms": names,
        "term_construction": "raw products, then training-only creator centering and scaling",
        "training_creator_means": {key: value.tolist() for key, value in means.items()},
        "training_scales": scales.tolist(),
        "creator_levels": creators,
        "nuisance_levels": nuisance,
        "absorbed_by_creator": absorbed,
        "rank": rank,
        "parameters": matrix.shape[1],
        "condition_number": condition,
        "sample_count": len(rows),
        "cluster_count": len(creators),
        "dispersion": dispersion,
        "missing": "complete-case, no imputation",
        "offset": None,
        "regularization": None,
        "training_post_ids": [row["post_id"] for row in rows],
    }
    return pipeline


def designed_regression(
    rows: list[dict[str, Any]], spec: CorrectedPerformanceSpec
) -> dict[str, Any]:
    if spec.model == "none":
        return {"status": "not_requested", "terms": []}
    if spec.maturity_policy == "collection_proxy":
        return {
            "status": "insufficient_data",
            "terms": [],
            "reason": "Unknown source measurement lag: collection-proxy models are withheld",
        }
    sample = eligible_rows(rows, spec)
    # Reposted identical media cannot contribute repeated independent observations.
    seen, unique = set(), []
    for row in sorted(sample, key=lambda r: (r["published_at"], r["post_id"])):
        identity = row.get("duplicate_group") or row["post_id"]
        if identity not in seen:
            unique.append(row)
            seen.add(identity)
    try:
        pipeline = fit_pipeline(unique, spec)
        matrix = pipeline.matrix(unique)
        inferential = pipeline.manifest["inferential_uncertainty"]
        covariance = pipeline.manifest["covariance"]
        fitted = pipeline.fitted
        intervals = np.asarray(fitted.conf_int())
        terms = []
        for index, name in enumerate(pipeline.manifest["numeric_terms"], start=1):
            scale = pipeline.scales[index - 1]
            finite = np.all(
                np.isfinite([fitted.bse[index], *intervals[index], fitted.pvalues[index]])
            )
            terms.append(
                {
                    "term": name,
                    "estimate": float(fitted.params[index] / scale),
                    "standard_error": float(fitted.bse[index] / scale)
                    if inferential and finite
                    else None,
                    "ci_low": float(intervals[index, 0] / scale)
                    if inferential and finite
                    else None,
                    "ci_high": float(intervals[index, 1] / scale)
                    if inferential and finite
                    else None,
                    "p_value": float(fitted.pvalues[index]) if inferential and finite else None,
                    "adjusted_p_value": None,
                    "sample_count": len(unique),
                    "cluster_count": len(pipeline.creators),
                }
            )
        from statsmodels.stats.multitest import multipletests

        # Include declared but untested family terms as p=1, not a smaller discovered family.
        p_values = [
            next(
                (t["p_value"] for t in terms if t["term"] == name and t["p_value"] is not None), 1.0
            )
            for name in spec.family_terms
        ]
        adjusted = dict(
            zip(spec.family_terms, multipletests(p_values, method="fdr_by")[1], strict=True)
        )
        for term in terms:
            if term["p_value"] is not None:
                term["adjusted_p_value"] = float(adjusted[term["term"]])
        influence = sm.OLS([r["outcome"] for r in unique], matrix).fit().get_influence()
        cook = np.asarray(influence.cooks_distance[0])
        return {
            "status": "fitted"
            if inferential and all(t["p_value"] is not None for t in terms)
            else "fitted_descriptive",
            "terms": terms,
            "pipeline": {**pipeline.manifest, "covariance": covariance},
            "diagnostics": {
                "excluded_post_ids": sorted(
                    {r["post_id"] for r in rows} - {r["post_id"] for r in unique}
                ),
                "influential_post_ids": [
                    r["post_id"]
                    for r, value in zip(unique, cook, strict=True)
                    if np.isfinite(value) and value > 4 / len(unique)
                ],
                "influence_method": "raw-outcome OLS design sensitivity, not GLM influence",
            },
        }
    except (ConfigurationError, ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
        return {"status": "insufficient_data", "terms": [], "reason": str(exc)}
