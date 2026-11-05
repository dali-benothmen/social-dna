"""Actual bounded marginal pipeline, train-only selection and protected partitions.

These are observational prediction models, not within-creator causal estimators.
No fixed-effect intercept is invented for a creator outside training.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import statsmodels.api as sm
from sklearn.linear_model import Ridge
from sklearn.preprocessing import SplineTransformer, StandardScaler
from statsmodels.stats.multitest import multipletests

from socialdna.core.exceptions import ConfigurationError
from socialdna.research.candidates import Candidate, DiscoverySpec
from socialdna.research.counterexamples import counterexamples

METHOD = "bounded-marginal-1"


def partitions(rows: list[dict[str, Any]], spec: DiscoverySpec) -> dict[str, Any]:
    """Plan without looking at outcomes; exact duplicate components are purged."""
    ordered = sorted(rows, key=lambda r: (r["published_at"], r["unit_id"]))
    transfer = [r for r in ordered if r["niche"] in spec.transfer_niches]
    transfer_creators = {r["creator_id"] for r in transfer}
    source = [
        r
        for r in ordered
        if r["niche"] not in spec.transfer_niches and r["creator_id"] not in transfer_creators
    ]
    if not source:
        return {"train": [], "test": [], "transfer": [], "purged": [r["unit_id"] for r in rows]}
    threshold = source[min(len(source) - 1, int(len(source) * (1 - spec.test_fraction)))][
        "published_at"
    ]
    creators = sorted({r["creator_id"] for r in source})
    rng = np.random.default_rng(spec.seed)
    held = (
        set(
            rng.choice(
                creators, max(2, int(len(creators) * spec.test_fraction)), replace=False
            ).tolist()
        )
        if len(creators) >= 2
        else set(creators)
    )
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for row in source:
        time_test, creator_test = row["published_at"] >= threshold, row["creator_id"] in held
        if spec.split == "creator":
            (test if creator_test else train).append(row)
        elif spec.split == "chronological":
            (test if time_test else train).append(row)
        elif time_test and creator_test:
            test.append(row)
        elif not time_test and not creator_test:
            train.append(row)
    if spec.split in ("chronological", "joint"):
        train = [
            r
            for r in train
            if r["outcome_end"] < threshold
            and (not r["forecast"] or r["outcome_available_at"] < threshold)
        ]
    # A duplicate touching an outer holdout never enters training or the other holdout.
    transfer_groups = {r["duplicate_group"] for r in transfer if r.get("duplicate_group")}
    test = [
        r
        for r in test
        if not r.get("duplicate_group") or r["duplicate_group"] not in transfer_groups
    ]
    held_groups = transfer_groups | {r["duplicate_group"] for r in test if r.get("duplicate_group")}
    train = [
        r for r in train if not r.get("duplicate_group") or r["duplicate_group"] not in held_groups
    ]

    def unique(items: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        result = []
        for row in items:
            key = row.get("duplicate_group") or row["unit_id"]
            if key not in seen:
                seen.add(key)
                result.append(row["unit_id"])
        return result

    result: dict[str, Any] = {
        "train": unique(train),
        "test": unique(test),
        "transfer": unique(transfer),
        "threshold": threshold,
    }
    result["purged"] = sorted(
        {r["unit_id"] for r in rows} - set(result["train"] + result["test"] + result["transfer"])
    )
    return result


def inner_folds(
    rows: list[dict[str, Any]], spec: DiscoverySpec
) -> list[tuple[list[str], list[str]]]:
    creators = sorted({r["creator_id"] for r in rows})
    rng = np.random.default_rng(spec.seed)
    rng.shuffle(creators)
    folds = []
    # Always creator-disjoint inside training, including for later time-block tests.
    for groups in np.array_split(creators, 3):
        held = set(groups.tolist())
        test = [r for r in rows if r["creator_id"] in held]
        train = [r for r in rows if r["creator_id"] not in held]
        if spec.split in ("chronological", "joint") and test:
            threshold = sorted(r["published_at"] for r in test)[len(test) // 2]
            test = [r for r in test if r["published_at"] >= threshold]
            train = [
                r
                for r in train
                if r["outcome_end"] < threshold
                and (not r["forecast"] or r["outcome_available_at"] < threshold)
            ]
        groups_test = {r["duplicate_group"] for r in test if r.get("duplicate_group")}
        train = [
            r
            for r in train
            if not r.get("duplicate_group") or r["duplicate_group"] not in groups_test
        ]
        folds.append(([r["unit_id"] for r in train], [r["unit_id"] for r in test]))
    return folds


@dataclass
class Pipeline:
    candidate: Candidate
    alpha: float
    scaler: StandardScaler
    spline: Any
    model: Any
    manifest: dict[str, Any]

    def terms(self, rows: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
        candidate = self.candidate
        keys = candidate.features + candidate.adjusters
        raw = np.array([[r["features"][key] for key in keys] for r in rows], dtype=float)
        if not np.isfinite(raw).all():
            raise ConfigurationError("Missing/non-finite predictors; complete cases only")
        if candidate.kind == "spline":
            return np.column_stack((self.spline.transform(raw[:, :1]), raw[:, 1:]))
        if candidate.kind == "quadratic":
            return np.column_stack((raw, raw[:, 0] ** 2))
        if candidate.kind == "interaction":
            return np.column_stack((raw, raw[:, 0] * raw[:, 1]))
        return raw

    def predict(self, rows: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
        matrix = self.scaler.transform(self.terms(rows))
        prediction = np.asarray(
            self.model.predict(sm.add_constant(matrix, has_constant="add"))
            if self.alpha == 0
            else self.model.predict(matrix),
            dtype=float,
        )
        if not np.isfinite(prediction).all():
            raise ConfigurationError("Non-finite predictions")
        return prediction


def fit(rows: list[dict[str, Any]], candidate: Candidate, alpha: float) -> Pipeline:
    if any(r.get("creator_identity", "supplied") != "supplied" for r in rows):
        raise ConfigurationError(
            "Supplied creator identities are required; "
            "account proxies are not independent creator evidence"
        )
    if len(rows) < 30 or len({r["creator_id"] for r in rows}) < 5:
        raise ConfigurationError("Need 30 complete units and five training creators (not power)")
    spline = None
    if candidate.kind == "spline":
        spline = SplineTransformer(
            n_knots=3, degree=2, knots="quantile", include_bias=False, extrapolation="linear"
        )
        spline.fit(np.array([[r["features"][candidate.features[0]]] for r in rows]))
    pipeline = Pipeline(candidate, alpha, StandardScaler(), spline, None, {})
    matrix = pipeline.terms(rows)
    if matrix.shape[1] * 5 > len(rows) or np.any(np.std(matrix, axis=0) < 1e-12):
        raise ConfigurationError("No variation or too few independent units per parameter")
    scaled = pipeline.scaler.fit_transform(matrix)
    design = sm.add_constant(scaled, has_constant="add")
    rank, condition = int(np.linalg.matrix_rank(design)), float(np.linalg.cond(design))
    if alpha == 0 and (rank < design.shape[1] or condition > 1e8):
        raise ConfigurationError("Aliased/ill-conditioned OLS design; no identifiable contrast")
    target = np.array([r["outcome"] for r in rows], dtype=float)
    if not np.isfinite(target).all() or np.std(target) < 1e-12:
        raise ConfigurationError("Missing/non-finite or constant outcome")
    pipeline.model = (
        sm.OLS(target, design).fit() if alpha == 0 else Ridge(alpha=alpha).fit(scaled, target)
    )
    pipeline.manifest = {
        "method": METHOD,
        "candidate": candidate.model_dump(mode="json"),
        "alpha": alpha,
        "prediction_target": "marginal raw outcome; no creator intercept or causal interpretation",
        "train_unit_ids": [r["unit_id"] for r in rows],
        "creator_count": len({r["creator_id"] for r in rows}),
        "means": pipeline.scaler.mean_.tolist(),
        "scales": pipeline.scaler.scale_.tolist(),
        "knots": spline.bsplines_[0].t.tolist() if spline else None,
        "rank": rank,
        "parameters": design.shape[1],
        "condition_number": condition if np.isfinite(condition) else None,
        "feature_ranges": {
            k: [min(r["features"][k] for r in rows), max(r["features"][k] for r in rows)]
            for k in candidate.features + candidate.adjusters
        },
    }
    return pipeline


def contrast(pipeline: Pipeline, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One focal predeclared block, not a causal effect or validation score."""
    candidate = pipeline.candidate
    uncertainty = (
        pipeline.alpha == 0
        and candidate.alphas == (0.0,)
        and len({r["creator_id"] for r in rows}) >= 20
        and float(np.var(pipeline.model.resid)) > 1e-12
    )
    result: dict[str, Any] = {
        "p_value": None,
        "adjusted_p_value": None,
        "uncertainty": "withheld: tuning, regularization, perfect fit or <20 clusters",
    }
    if not uncertainty:
        return result
    robust = pipeline.model.get_robustcov_results(
        cov_type="cluster", groups=[r["creator_id"] for r in rows], use_t=True
    )
    count = pipeline.scaler.n_features_in_
    focal = (
        [count]
        if candidate.kind in ("interaction", "quadratic")
        else list(range(1, count - len(candidate.adjusters) + 1))
        if candidate.kind == "spline"
        else [1]
    )
    restriction = np.zeros((len(focal), count + 1))
    for i, index in enumerate(focal):
        restriction[i, index] = 1
    tested = robust.wald_test(restriction, scalar=True)
    if not np.isfinite(tested.pvalue):
        return result
    intervals = np.asarray(robust.conf_int())
    result.update(
        {
            "p_value": float(tested.pvalue),
            "uncertainty": "creator-cluster; exploratory",
            "contrast": "joint spline association (not nonlinearity vs linear)"
            if candidate.kind == "spline"
            else candidate.kind,
            "coefficients": [
                {
                    "basis_column": i,
                    "estimate": float(robust.params[i]),
                    "ci_low": float(intervals[i, 0]),
                    "ci_high": float(intervals[i, 1]),
                    "raw_basis_estimate": float(robust.params[i] / pipeline.scaler.scale_[i - 1]),
                    "raw_basis_ci_low": float(intervals[i, 0] / pipeline.scaler.scale_[i - 1]),
                    "raw_basis_ci_high": float(intervals[i, 1] / pipeline.scaler.scale_[i - 1]),
                }
                for i in focal
            ],
            "coefficient_units": "training-standardized basis; not raw technique effects",
        }
    )
    return result


def score(
    pipeline: Pipeline, train: list[dict[str, Any]], test: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(test) < 10 or len({r["creator_id"] for r in test}) < 2:
        raise ConfigurationError("Need ten test units and two test creators; scope withheld")
    prediction = pipeline.predict(test)
    truth = np.array([r["outcome"] for r in test])
    baseline = float(np.median([r["outcome"] for r in train]))
    return {
        "status": "evaluated",
        "unit_ids": [r["unit_id"] for r in test],
        "predictions": prediction.tolist(),
        "mae": float(np.mean(abs(truth - prediction))),
        "baseline_mae": float(np.mean(abs(truth - baseline))),
        "predictive_skill_observed": bool(
            np.mean(abs(truth - prediction)) < np.mean(abs(truth - baseline))
        ),
        "n_creators": len({r["creator_id"] for r in test}),
        "outside_training_range": [
            r["unit_id"]
            for r in test
            if any(
                not low <= r["features"][k] <= high
                for k, (low, high) in pipeline.manifest["feature_ranges"].items()
            )
        ],
    }


def run(
    rows: list[dict[str, Any]], spec: DiscoverySpec, split: dict[str, Any], attempt: Any
) -> dict[str, Any]:
    """The callback durably starts/finishes every actual fit, including failures."""
    by_id = {r["unit_id"]: r for r in rows}
    train = [by_id[i] for i in split["train"]]
    folds = inner_folds(train, spec)
    candidates = []
    for candidate in spec.candidates:
        tuning: list[dict[str, Any]] = []
        for alpha in candidate.alphas:
            evaluations = []
            for index, (training, validation) in enumerate(folds):
                a, b = [by_id[i] for i in training], [by_id[i] for i in validation]

                def inner(
                    a: Any = a, b: Any = b, alpha: float = alpha, candidate: Candidate = candidate
                ) -> dict[str, Any]:
                    pipeline = fit(a, candidate, alpha)
                    return {**score(pipeline, a, b), "pipeline": pipeline.manifest}

                evaluations.append(
                    attempt(candidate.key, "inner", alpha, index, training, validation, inner)
                )
            valid = all(e.get("status") == "evaluated" for e in evaluations)
            tuning.append(
                {
                    "alpha": alpha,
                    "evaluations": evaluations,
                    "mae": float(np.mean([e["mae"] for e in evaluations])) if valid else None,
                }
            )
        usable = [t for t in tuning if t["mae"] is not None]
        chosen = min(usable, key=lambda t: (t["mae"], t["alpha"])) if usable else None

        def descriptive(chosen: Any = chosen, candidate: Candidate = candidate) -> dict[str, Any]:
            if chosen is None:
                raise ConfigurationError("All three protected inner folds must be estimable")
            pipeline = fit(train, candidate, chosen["alpha"])
            return {
                "status": "fitted",
                "pipeline": pipeline.manifest,
                "contrast": contrast(pipeline, train),
            }

        fitted = attempt(
            candidate.key,
            "training",
            chosen["alpha"] if chosen else None,
            None,
            split["train"],
            [],
            descriptive,
        )
        candidates.append(
            {
                "key": candidate.key,
                "tuning": tuning,
                "training": fitted,
                "selection_mae": chosen["mae"] if chosen and fitted["status"] == "fitted" else None,
            }
        )
    # Failed/null candidates remain members (p=1) of the complete frozen family.
    p_values = [c["training"].get("contrast", {}).get("p_value") for c in candidates]
    adjusted = multipletests(
        [p if p is not None else 1.0 for p in p_values],
        method="fdr_by",
    )[1]
    for candidate_result, value in zip(candidates, adjusted, strict=True):
        term = candidate_result["training"].get("contrast", {})
        if term.get("p_value") is not None:
            term["adjusted_p_value"] = float(value)
    successful = [c for c in candidates if c["selection_mae"] is not None]
    winner = min(successful, key=lambda c: (c["selection_mae"], c["key"])) if successful else None
    outer: dict[str, Any] = {"status": "insufficient_data", "reason": "No estimable candidate"}
    if winner:
        candidate = next(c for c in spec.candidates if c.key == winner["key"])

        def evaluate() -> dict[str, Any]:
            pipeline = fit(train, candidate, winner["training"]["pipeline"]["alpha"])
            evaluations = {}
            for name, ids in (("in_scope", split["test"]), ("transfer", split["transfer"])):
                if not ids:
                    continue
                test = [by_id[i] for i in ids]
                try:
                    evaluation = score(pipeline, train, test)
                    evaluation["by_niche"] = {}
                    for niche in sorted({r["niche"] for r in test}):
                        niche_rows = [r for r in test if r["niche"] == niche]
                        try:
                            evaluation["by_niche"][niche] = score(pipeline, train, niche_rows)
                        except ConfigurationError as exc:
                            evaluation["by_niche"][niche] = {
                                "status": "insufficient_data",
                                "reason": str(exc),
                            }
                    evaluation["counterexamples"] = counterexamples(pipeline, train, test)
                    evaluations[name] = evaluation
                except ConfigurationError as exc:
                    evaluations[name] = {"status": "insufficient_data", "reason": str(exc)}
            return {
                "status": "evaluated",
                "selected": candidate.key,
                "pipeline": pipeline.manifest,
                "evaluations": evaluations,
            }

        outer = attempt(
            candidate.key,
            "outer",
            winner["training"]["pipeline"]["alpha"],
            None,
            split["train"],
            split["test"] + split["transfer"],
            evaluate,
        )
    winners = []
    for index in range(3):
        choices = [
            (t["evaluations"][index]["mae"], c["key"])
            for c in candidates
            for t in c["tuning"]
            if t["evaluations"][index].get("status") == "evaluated"
        ]
        winners.append(min(choices)[1] if choices else None)
    return {
        "status": "completed",
        "claim_level": spec.claim_level,
        "method": METHOD,
        "candidates": candidates,
        "selected": winner["key"] if winner else None,
        "outer": outer,
        "stability": {
            "inner_fold_winners": winners,
            "interpretation": "selection sensitivity, not independent replications",
        },
        "multiplicity": {
            "method": "BY",
            "family_size": len(spec.candidates),
            "scope": "declared training focal blocks only; no sequential or selection guarantee",
        },
        "independent_confirmation": False,
        "limitations": [
            "Marginal prediction is not a mechanism, causal effect or ranking weight.",
            "Outer performance does not replicate an interaction contrast.",
            "Small-cluster thresholds are engineering gates, not power calculations.",
            "Exact-content duplicates are purged; near-duplicate coverage is unknown.",
            "Declared source frames/language/audience are not automatically verified.",
            "No universal niche, platform, posting-time or profile-conversion recommendation.",
        ],
    }
