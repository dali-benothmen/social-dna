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
