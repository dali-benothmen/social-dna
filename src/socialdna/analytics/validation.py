"""Train-only preprocessing and explicit chronological/creator leakage audits."""

from typing import Any

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.research import CorrectedPerformanceSpec


def audit_split(
    rows: list[dict[str, Any]],
    train: list[int],
    test: list[int],
    *,
    grouped: bool,
    chronological: bool,
    feature_names: tuple[str, ...],
) -> None:
    if not train or not test or set(train).intersection(test):
        raise ConfigurationError("Invalid or overlapping training/test rows")
    if len({rows[index]["post_id"] for index in train + test}) != len(train) + len(test):
        raise ConfigurationError("Post duplication leaks across splits")
    if grouped and {rows[i]["creator_id"] for i in train}.intersection(
        rows[i]["creator_id"] for i in test
    ):
        raise ConfigurationError("Creator leakage across grouped validation")
    if chronological and max(rows[i]["published_at"] for i in train) >= min(
        rows[i]["published_at"] for i in test
    ):
        raise ConfigurationError("Future or simultaneous posts leak into chronological training")
    if chronological and any(
        rows[i].get("outcome_available_at", rows[i]["published_at"])
        >= min(rows[j]["published_at"] for j in test)
        for i in train
    ):
        raise ConfigurationError(
            "Training outcomes were unavailable at the test publication cutoff"
        )
    forbidden = {
        "outcome",
        "views",
        "likes",
        "shares",
        "saves",
        "retention",
        "baseline",
        "median_ratio",
    }
    if any(name in forbidden or name.startswith("metric:") for name in feature_names):
        raise ConfigurationError("Target-derived predictors are forbidden")
    for row in rows:
        if any(time > row["published_at"] for time in row.get("feature_available_at", {}).values()):
            raise ConfigurationError("Predictor was only available after publication")


def predictive_validation(
    rows: list[dict[str, Any]], features: tuple[str, ...], seed: int
) -> dict[str, Any]:
    usable = [row for row in rows if row["outcome"] is not None]
    if len(usable) < 30 or not features:
        return {"status": "insufficient_data", "evaluations": []}
    usable.sort(key=lambda row: (row["published_at"], row["post_id"]))
    matrix = np.array(
        [[row["features"].get(key, np.nan) for key in features] for row in usable], dtype=float
    )
    target = np.array([row["outcome"] for row in usable])
    split = int(len(usable) * 0.8)
    threshold = usable[split]["published_at"]
    splits: list[tuple[str, list[int], list[int]]] = [
        (
            "chronological",
            [
                i
                for i, row in enumerate(usable)
                if row["published_at"] < threshold
                and row.get("outcome_available_at", row["published_at"]) < threshold
            ],
            [i for i, row in enumerate(usable) if row["published_at"] >= threshold],
        )
    ]
    groups = [row["creator_id"] for row in usable]
    if len(set(groups)) >= 5:
        train, test = next(
            GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed).split(
                matrix, target, groups
            )
        )
        splits.append(("creator_held_out", train.tolist(), test.tolist()))
    results = []
    for name, train_ids, test_ids in splits:
        try:
            audit_split(
                usable,
                train_ids,
                test_ids,
                grouped=name == "creator_held_out",
                chronological=name == "chronological",
                feature_names=features,
            )
            if len(train_ids) < 20 or len(test_ids) < 5:
                raise ConfigurationError("Insufficient validation split size")
            # Reject all-missing columns rather than fitting an arbitrary imputed constant.
            if np.any(np.all(np.isnan(matrix[train_ids]), axis=0)):
                raise ConfigurationError("Training feature is entirely missing")
            pipeline = make_pipeline(
                SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1)
            )
            pipeline.fit(matrix[train_ids], target[train_ids])
            prediction = pipeline.predict(matrix[test_ids])
            results.append(
                {
                    "split": name,
                    "status": "evaluated",
                    "train_ids": train_ids,
                    "test_ids": test_ids,
                    "train_post_ids": [usable[i]["post_id"] for i in train_ids],
                    "test_post_ids": [usable[i]["post_id"] for i in test_ids],
                    "mae": float(mean_absolute_error(target[test_ids], prediction)),
                    "baseline_mae": float(
                        mean_absolute_error(
                            target[test_ids], np.repeat(np.median(target[train_ids]), len(test_ids))
                        )
                    ),
                    "training_medians": pipeline[0].statistics_.tolist(),
                    "preprocessing": "training-only median imputer + scaler + ridge(alpha=1)",
                }
            )
        except ConfigurationError as exc:
            results.append({"split": name, "status": "insufficient_data", "reason": str(exc)})
    return {
        "status": "evaluated"
        if any(row["status"] == "evaluated" for row in results)
        else "insufficient_data",
        "evaluations": results,
        "limitations": [
            "Chronological and creator-held-out splits test different, non-causal generalizations.",
            "Historical caption edits/content availability cannot be verified from an export.",
        ],
    }


def designed_split(
    rows: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
) -> dict[str, Any]:
    """One declared split, purging outcomes and connected exact-content groups."""
    from socialdna.analytics.features import eligible_rows

    usable = sorted(
        eligible_rows(rows, spec), key=lambda row: (row["published_at"], row["post_id"])
    )
    if spec.split_policy == "none":
        return {"status": "not_requested", "train_post_ids": [], "test_post_ids": []}
    if len(usable) < 30:
        return {
            "status": "insufficient_data",
            "reason": "Fewer than 30 feature-eligible posts",
            "train_post_ids": [],
            "test_post_ids": [],
        }
    threshold = usable[int(len(usable) * (1 - spec.test_fraction))]["published_at"]
    held_creators: set[str] = set()
    if spec.split_policy in ("creator", "joint"):
        creators = sorted({r["creator_id"] for r in usable})
        rng = np.random.default_rng(spec.seed)
        held_creators = set(
            rng.choice(
                creators, max(1, int(len(creators) * spec.test_fraction)), replace=False
            ).tolist()
        )
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for row in usable:
        time_test = row["published_at"] >= threshold
        creator_test = row["creator_id"] in held_creators
        if spec.split_policy == "chronological":
            (test if time_test else train).append(row)
        elif spec.split_policy == "creator":
            (test if creator_test else train).append(row)
        elif time_test and creator_test:
            test.append(row)
        elif not time_test and not creator_test:
            train.append(row)
    if spec.split_policy in ("chronological", "joint"):
        train = [
            r
            for r in train
            if r.get("outcome_available_at") and r["outcome_available_at"] < threshold
        ]
    # Entire duplicate components touch only one side, even across creators/time.
    test_groups = {r["duplicate_group"] for r in test if r.get("duplicate_group")}
    train = [
        r for r in train if not r.get("duplicate_group") or r["duplicate_group"] not in test_groups
    ]

    # Remove repeated media inside each side too; repeated chunks/posts are not new units.
    def unique(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen, result = set(), []
        for row in items:
            identity = row.get("duplicate_group") or row["post_id"]
            if identity not in seen:
                result.append(row)
                seen.add(identity)
        return result

    train, test = unique(train), unique(test)
    retained = {r["post_id"] for r in train + test}
    return {
        "status": "ready" if len(train) >= 30 and len(test) >= 5 else "insufficient_data",
        "reason": "Split sizes after timing/duplicate purges"
        if len(train) < 30 or len(test) < 5
        else None,
        "split": spec.split_policy,
        "threshold": threshold,
        "train_post_ids": [r["post_id"] for r in train],
        "test_post_ids": [r["post_id"] for r in test],
        "purged_post_ids": sorted({r["post_id"] for r in usable} - retained),
        "feature_policy": spec.feature_policy,
        "generalization": "historical forecasting"
        if spec.feature_policy == "historical_prediction"
        else "retrospective content association; not a deployable historical forecast",
    }


def validate_pipeline(
    rows: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    split: dict[str, Any],
) -> dict[str, Any]:
    from socialdna.analytics.designs import fit_pipeline

    if spec.maturity_policy == "collection_proxy" and spec.split_policy != "none":
        return {
            **split,
            "status": "insufficient_data",
            "evaluations": [],
            "reason": "Unknown source measurement lag: collection-proxy validation is withheld",
        }
    if split["status"] != "ready":
        return {**split, "evaluations": []}
    by_id = {row["post_id"]: row for row in rows}
    train = [by_id[identity] for identity in split["train_post_ids"]]
    test = [by_id[identity] for identity in split["test_post_ids"]]
    if {r["creator_id"] for r in test} - {r["creator_id"] for r in train}:
        return {
            **split,
            "status": "unsupported_creator_prediction",
            "evaluations": [],
            "reason": (
                "Fixed-effect pipeline cannot predict unseen creator intercepts; "
                "no surrogate fitted"
            ),
        }
    try:
        pipeline = fit_pipeline(train, spec)
        prediction = pipeline.predict(test)
        truth = np.asarray([r["outcome"] for r in test])
        return {
            **split,
            "status": "evaluated",
            "evaluations": [
                {
                    "mae": float(mean_absolute_error(truth, prediction)),
                    "baseline_mae": float(
                        mean_absolute_error(
                            truth, np.repeat(np.median([r["outcome"] for r in train]), len(test))
                        )
                    ),
                    "pipeline": pipeline.manifest,
                    "predictions": prediction.tolist(),
                }
            ],
            "limitations": [
                "Predictive scoring is not independent inferential replication or a causal test."
            ],
        }
    except (ConfigurationError, ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
        return {**split, "status": "insufficient_data", "reason": str(exc), "evaluations": []}
