from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest

from socialdna.analytics.baselines import time_aware_baselines
from socialdna.analytics.cohorts import balance_diagnostics, designed_pairs
from socialdna.analytics.designs import designed_regression, fit_pipeline
from socialdna.analytics.statistics import designed_comparison
from socialdna.analytics.validation import designed_split, validate_pipeline
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.time import format_utc
from socialdna.domain.research import (
    CorrectedPerformanceSpec,
    PerformanceSpec,
    parse_performance_spec,
)


def specification(**changes: Any) -> CorrectedPerformanceSpec:
    return CorrectedPerformanceSpec.model_validate(
        {
            "metric_key": "demo.views.v1",
            "estimand": "within_creator_association",
            "design": "within_creator",
            "feature_policy": "retrospective_content",
            "knowledge_cutoff": "2026-11-01T00:00:00Z",
            "publication_cutoff": "2026-10-01T00:00:00Z",
            "sampling_frame": "authorized cooking exports, all supplied posts",
            "features": ["duration_seconds", "caption_length"],
            "family_id": "cooking-duration-caption",
            "family_terms": ["duration_seconds", "caption_length"],
            "bootstrap_resamples": 200,
            **changes,
        }
    )


def sample_rows(n: int = 240, creators: int = 24) -> list[dict[str, Any]]:
    rng = np.random.default_rng(14)
    rows = []
    for i in range(n):
        creator = i % creators
        x, z = rng.normal(size=2)
        published = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)
        features = {"duration_seconds": x + 20, "caption_length": z + 10}
        rows.append(
            {
                "post_id": f"p{i:04d}",
                "creator_id": f"c{creator:02d}",
                "platform": "demo",
                "content_type": "video",
                "niche": f"n{creator % 2}",
                "topics": ["cooking"],
                "published_at": format_utc(published),
                "outcome_available_at": format_utc(published + timedelta(days=7)),
                "features": features,
                "feature_values": {
                    key: {"eligible": True, "available_at": format_utc(published)}
                    for key in features
                },
                "outcome": 100 + creator * 8 + 2 * x + rng.normal(scale=0.2),
                "age_seconds": 7 * 86400,
                "window_seconds": None,
                "availability": "available",
                "role": "left" if (i // creators) % 2 == 0 else "right",
                "snapshot_ids": [f"s{i}"],
                "duplicate_group": None,
            }
        )
    return rows


def test_explicit_spec_dispatch_and_estimand_gates() -> None:
    assert type(parse_performance_spec({"metric_key": "demo.views.v1"})) is PerformanceSpec
    assert isinstance(
        parse_performance_spec(specification().model_dump()), CorrectedPerformanceSpec
    )
    for changes in (
        {"design": "cross_creator"},
        {"model": "mixed"},
        {"family_terms": ["duration_seconds"]},
        {"knowledge_cutoff": "2026-01-01"},
        {"split_policy": "chronological", "model": "ols"},
    ):
        with pytest.raises(ValueError):
            specification(**changes)


def test_historical_baseline_uses_full_history_known_measurements_and_no_epsilon() -> None:
    rows = sample_rows(10, 1)
    spec = specification(baseline_cutoff="evaluation")
    baseline = time_aware_baselines([rows[8]], rows, spec)[0]
    assert baseline["reference_post_ids"] == [r["post_id"] for r in rows[:8]]
    assert baseline["summary"]["n"] == 8
    future = deepcopy(rows[-1])
    future.update(post_id="future", published_at="2027-01-01T00:00:00.000000Z")
    # Future reference candidates cannot change the estimate/reference manifest.
    extended = time_aware_baselines([rows[8]], rows + [future], spec)[0]
    assert extended["summary"] == baseline["summary"]
    assert extended["reference_post_ids"] == baseline["reference_post_ids"]
    strict = time_aware_baselines([rows[8]], rows, specification())[0]
    assert strict["summary"]["n"] == 2  # only p0/p1 matured by p8's publication
    for row in rows:
        row["outcome"] = 0
    constant = time_aware_baselines([rows[8]], rows, spec)[0]
    assert constant["median_ratio"] is None and constant["robust_z"] is None


def test_historical_baseline_selects_revision_known_at_target_not_later_correction() -> None:
    rows = sample_rows(10, 1)
    for i, row in enumerate(rows):
        snapshot = {
            "id": f"s{i}",
            "value": 10,
            "availability": "available",
            "supersedes_id": None,
            "observed_at": row["outcome_available_at"],
            "post_age_seconds": 7 * 86400,
            "window_start": None,
            "window_end": None,
            "imported_at": row["outcome_available_at"],
        }
        correction = {
            **snapshot,
            "id": f"c{i}",
            "value": 10000,
            "supersedes_id": snapshot["id"],
            "imported_at": "2026-10-01T00:00:00.000000Z",
        }
        row["snapshot_candidates"] = {"demo.views.v1": [snapshot, correction]}
    baseline = time_aware_baselines([rows[9]], rows, specification())[0]
    assert baseline["summary"]["median"] == 10
    assert all(s.startswith("s") for s in baseline["reference_snapshot_ids"])


def test_cross_creator_matching_context_support_balance_and_outcome_blinding() -> None:
    rows = sample_rows(24, 2)
    for i, row in enumerate(rows):
        row["creator_id"] = "left" if i % 2 == 0 else "right"
        row["role"] = "left" if i % 2 == 0 else "right"
        row["features"]["duration_seconds"] = float((i // 2) - 6)  # signed covariates are valid
    spec = specification(design="cross_creator", estimand="cross_creator_comparison")
    pairs = designed_pairs(rows, spec)
    assert len(pairs) == 12
    assert balance_diagnostics(rows, pairs, spec)["duration_seconds"]["after"]["smd"] == 0
    for row in rows:
        row["outcome"] = 1e9
    assert designed_pairs(rows, spec) == pairs
    assert designed_comparison(rows, spec)["status"] == "supported_descriptive"
    for row in rows:
        if row["role"] == "right":
            row["features"]["duration_seconds"] += 1000
    unsupported = designed_comparison(rows, spec)
    assert unsupported["status"] == "insufficient_overlap"
    assert unsupported["matched_effect"]["estimate"] is None
    rows[0]["features"]["duration_seconds"] = None
    rows[1]["topics"] = None
    rows[0]["feature_values"]["duration_seconds"]["eligible"] = False
    assert not designed_pairs(rows, spec)


def test_within_creator_controls_between_creator_confounding_and_nested_niche() -> None:
    rows = sample_rows(480, 24)
    rng = np.random.default_rng(8)
    for i, row in enumerate(rows):
        creator = i % 24
        within = rng.normal()
        row["features"]["duration_seconds"] = creator * 10 + within
        row["outcome"] = creator * 100 - 3 * within + rng.normal(scale=0.1)
    assert (
        np.corrcoef(
            [r["features"]["duration_seconds"] for r in rows], [r["outcome"] for r in rows]
        )[0, 1]
        > 0.9
    )
    result = designed_regression(rows, specification(model="ols"))
    assert result["status"] == "fitted", result
    assert result["terms"][0]["estimate"] == pytest.approx(-3, abs=0.05)
    assert "niche" in result["pipeline"]["absorbed_by_creator"]
    assert result["pipeline"]["rank"] == result["pipeline"]["parameters"]
    for row in rows:
        row["features"]["duration_seconds"] = float(int(row["creator_id"][1:]))
    refused = designed_regression(rows, specification(model="ols"))
    assert refused["status"] == "insufficient_data" and "variation" in refused["reason"]


def test_pure_interaction_validation_uses_selected_pipeline_and_train_only_preprocessing() -> None:
    rows = sample_rows(240, 1)
    rng = np.random.default_rng(7)
    for row in rows:
        x, z = rng.choice([-1, 1], size=2)
        row["features"] = {"duration_seconds": float(x), "caption_length": float(z)}
        row["outcome"] = 100 + 20 * x * z + rng.normal(scale=0.05)
    spec = specification(
        model="ols",
        interactions=[["duration_seconds", "caption_length"]],
        family_terms=["duration_seconds", "caption_length", "duration_seconds*caption_length"],
        split_policy="chronological",
        holdout_id="interaction-holdout",
    )
    split = designed_split(rows, spec)
    result = validate_pipeline(rows, spec, split)
    assert result["status"] == "evaluated", result
    evaluation = result["evaluations"][0]
    assert evaluation["mae"] < 0.1 and evaluation["baseline_mae"] > 10
    assert evaluation["pipeline"]["numeric_terms"][-1] == "duration_seconds*caption_length"
    trained = fit_pipeline([r for r in rows if r["post_id"] in split["train_post_ids"]], spec)
    for row in rows:
        if row["post_id"] in split["test_post_ids"]:
            row["features"]["duration_seconds"] = 10000
    changed = validate_pipeline(rows, spec, split)
    assert changed["evaluations"][0]["pipeline"]["training_scales"] == trained.scales.tolist()


@pytest.mark.parametrize("policy", ["creator", "joint"])
def test_unseen_creator_validation_never_substitutes_an_auxiliary_model(policy: str) -> None:
    rows = sample_rows()
    spec = specification(model="ols", split_policy=policy, holdout_id="reserved")
    split = designed_split(rows, spec)
    assert split["status"] == "ready", split
    result = validate_pipeline(rows, spec, split)
    assert result["status"] == "unsupported_creator_prediction"
    assert not result["evaluations"]


def test_exact_duplicate_groups_are_purged_across_time_and_creator_boundaries() -> None:
    rows = sample_rows()
    for i in (0, 1, 230):
        rows[i]["duplicate_group"] = "same-media-sha"
    spec = specification(model="ols", split_policy="chronological", holdout_id="duplicates")
    split = designed_split(rows, spec)
    by_id = {r["post_id"]: r for r in rows}
    train_groups = {by_id[i]["duplicate_group"] for i in split["train_post_ids"]} - {None}
    test_groups = {by_id[i]["duplicate_group"] for i in split["test_post_ids"]} - {None}
    assert not train_groups.intersection(test_groups)
    assert rows[0]["post_id"] in split["purged_post_ids"]


@pytest.mark.parametrize(
    "problem",
    ["small", "constant", "missing", "collinear", "late_outcome", "unknown_feature", "proxy"],
)
def test_explicit_insufficient_data_gates(problem: str) -> None:
    rows = sample_rows(20 if problem == "small" else 100, 1)
    spec = specification(model="ols", split_policy="chronological", holdout_id="gates")
    for row in rows:
        if problem == "constant":
            row["outcome"] = 1
        elif problem == "missing":
            row["features"]["caption_length"] = None
            row["feature_values"]["caption_length"]["eligible"] = False
        elif problem == "collinear":
            row["features"]["caption_length"] = row["features"]["duration_seconds"]
        elif problem == "late_outcome":
            row["outcome_available_at"] = "2099-01-01"
        elif problem == "unknown_feature":
            row["feature_values"]["caption_length"]["eligible"] = False
    if problem == "proxy":
        spec = specification(model="ols", maturity_policy="collection_proxy")
    if problem == "late_outcome":
        assert designed_split(rows, spec)["status"] == "insufficient_data"
    else:
        result = designed_regression(rows, spec)
        assert result["status"] == "insufficient_data", result


def test_pipeline_uses_declared_target_transform_and_poisson_count_gates() -> None:
    rows = sample_rows(120, 1)
    spec = specification(model="ols", target_transform="log1p")
    pipeline = fit_pipeline(rows, spec)
    assert pipeline.manifest["target_transform"] == "log1p"
    assert np.all(pipeline.predict(rows) > 0)
    with pytest.raises(ConfigurationError, match="integer"):
        fit_pipeline(rows, specification(model="poisson"))
    rng = np.random.default_rng(8)
    for row in rows:
        row["outcome"] = int(rng.poisson(100))
    assert fit_pipeline(rows, specification(model="poisson")).manifest["dispersion"] < 2
    rows[0]["outcome"] = 1000000
    with pytest.raises(ConfigurationError, match="overdispersion"):
        fit_pipeline(rows, specification(model="poisson"))
