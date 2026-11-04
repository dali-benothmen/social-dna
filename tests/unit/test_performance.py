from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
import scipy.stats as stats
import statsmodels.api as sm
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from statsmodels.stats.multitest import multipletests

from socialdna.analytics.baselines import creator_baselines, robust_summary
from socialdna.analytics.cohorts import in_population, match_pairs
from socialdna.analytics.metrics import outcome, select_snapshot
from socialdna.analytics.statistics import (
    adjust_fdr,
    analyze_rows,
    bootstrap_median,
    correlations,
    regression,
)
from socialdna.analytics.validation import audit_split, predictive_validation
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.research import PerformanceSpec, Population
from socialdna.ingestion.tabular import RECORD_ADAPTER, timestamp


def rows(n: int = 100, creators: int = 1) -> list[dict[str, Any]]:
    rng = np.random.default_rng(54)
    result = []
    for index in range(n):
        x = float(rng.uniform(1, 20))
        creator = index % creators
        result.append(
            {
                "post_id": f"post-{index:04}",
                "creator_id": f"creator-{creator}",
                "creator_identity": "supplied",
                "platform": "demo",
                "niche": "education",
                "topics": ["learning"],
                "content_type": "video",
                "window_seconds": None,
                "published_at": (
                    datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=index)
                ).isoformat(),
                "outcome": float(10 + 2 * x + creator * 0.5 + rng.normal()),
                "availability": "available",
                "features": {"duration_seconds": x, "caption_length": float(index)},
                "age_seconds": 7 * 86400,
                "role": "left" if index < n // 2 else "right",
            }
        )
    return result


def test_baselines_hand_calculation_and_no_self_reference() -> None:
    summary = robust_summary([1, 2, 3, 100])
    assert summary["median"] == 2.5 and summary["mad"] == 1
    sample = rows(4)
    for row, value in zip(sample, [1, 2, 3, 100], strict=True):
        row["outcome"] = value
    baseline = creator_baselines(sample)[0]
    assert baseline["leave_one_out_scores"][-1]["median_ratio"] == 50
    assert robust_summary([])["median"] is None


@given(st.lists(st.floats(min_value=0, max_value=1e8, allow_nan=False), min_size=1, max_size=30))
def test_median_and_mad_never_outside_support(values: list[float]) -> None:
    result = robust_summary(values)
    assert min(values) <= result["median"] <= max(values)
    assert result["mad"] >= 0


def test_missing_metrics_and_zero_denominators_are_not_zero_engagement() -> None:
    spec = PerformanceSpec(
        metric_key="demo.likes.v1",
        numerator_keys=("demo.shares.v1",),
        denominator_key="demo.views.v1",
    )
    available = {
        "value": 10,
        "availability": "available",
        "observed_at": "t",
        "window_start": None,
        "window_end": None,
    }
    selected = {
        "demo.likes.v1": available,
        "demo.shares.v1": None,
        "demo.views.v1": {**available, "value": 100},
    }
    assert outcome(selected, spec) == (None, "missing_required_metric")
    selected["demo.shares.v1"] = {**available, "value": 0}
    assert outcome(selected, spec) == (0.1, "available")
    selected["demo.views.v1"]["value"] = 0
    assert outcome(selected, spec) == (None, "nonpositive_denominator")


def test_snapshot_age_alignment_supersession_and_conflict() -> None:
    spec = PerformanceSpec(metric_key="demo.views.v1")
    base = {
        "id": "old",
        "observed_at": "2026-01-08T00:00:00Z",
        "window_start": None,
        "window_end": None,
        "value": 10,
        "availability": "available",
        "post_age_seconds": 7 * 86400,
        "supersedes_id": None,
    }
    ancient = {**base, "id": "ancient", "post_age_seconds": 2 * 365 * 86400}
    assert select_snapshot([ancient], spec)[0] is None
    correction = {**base, "id": "new", "value": 15, "supersedes_id": "old"}
    assert select_snapshot([base, correction], spec)[0]["value"] == 15
    other_source = {**base, "id": "other-source", "value": 20}
    assert select_snapshot([base, other_source], spec) == (None, "conflicting_sources")


@pytest.mark.parametrize("value", [True, "10", -2, float("inf"), float("nan")])
def test_invalid_metric_numbers(value: Any) -> None:
    with pytest.raises(ValidationError):
        RECORD_ADAPTER.validate_python(
            {
                "record_type": "metric_snapshot",
                "platform": "demo",
                "subject_external_id": "p",
                "metric_key": "demo.views.v1",
                "observed_at": "2026-01-01T00:00:00Z",
                "value": value,
            }
        )


def test_timezone_normalization() -> None:
    assert timestamp("2026-01-01T01:00:00+01:00") == "2026-01-01T00:00:00.000000Z"
    with pytest.raises(ValueError):
        timestamp("2026-01-01T00:00:00")


def test_population_and_matching_use_no_outcomes() -> None:
    sample = rows(10)
    assert in_population(sample[0], Population(platforms=("demo",), topics=("learning",)))
    assert not in_population(sample[0], Population(niches=("other",)))
    assert not in_population(sample[0], Population(min_duration_seconds=99))
    spec = PerformanceSpec(metric_key="demo.views.v1", duration_caliper_seconds=100)
    pairs = match_pairs(sample, spec)
    assert len(pairs) == 5
    for row in sample:
        row["outcome"] = 12345
    assert match_pairs(sample, spec) == pairs
    sample[-1]["creator_id"] = "different"
    assert len(match_pairs(sample, spec)) == 4


def test_seeded_cluster_bootstrap_and_fdr() -> None:
    spec = PerformanceSpec(metric_key="demo.views.v1", bootstrap_resamples=200)
    result = bootstrap_median([1, 2, 3, 4, 5, 6], ["a", "a", "b", "b", "c", "c"], spec)
    assert result == bootstrap_median([1, 2, 3, 4, 5, 6], ["a", "a", "b", "b", "c", "c"], spec)
    assert result["ci_low"] <= 3.5 <= result["ci_high"]
    assert bootstrap_median([1, 2], ["a", "a"], spec)["ci_low"] is None
    results = [{"p_value": 0.001}, {"p_value": 0.02}, {"p_value": 0.5}, {"p_value": None}]
    adjust_fdr(results)
    assert [row["adjusted_p_value"] for row in results[:3]] == pytest.approx(
        multipletests([0.001, 0.02, 0.5], method="fdr_by")[1]
    )
    assert "adjusted_p_value" not in results[-1]


def test_ols_matches_statsmodels_and_has_influence_diagnostics() -> None:
    sample = rows()
    spec = PerformanceSpec(metric_key="demo.views.v1", features=("duration_seconds",), model="ols")
    result = regression(sample, spec)
    expected = (
        sm.OLS(
            [r["outcome"] for r in sample],
            sm.add_constant([r["features"]["duration_seconds"] for r in sample]),
        )
        .fit()
        .get_robustcov_results(cov_type="HAC", maxlags=3)
    )
    assert result["status"] == "fitted"
    assert [row["estimate"] for row in result["terms"]] == pytest.approx(expected.params)
    assert [row["ci_low"] for row in result["terms"]] == pytest.approx(expected.conf_int()[:, 0])
    assert "influential_post_ids" in result["diagnostics"]


@pytest.mark.parametrize("problem", ["small", "constant", "collinear", "few_clusters"])
def test_regression_rejects_unstable_inputs(problem: str) -> None:
    sample = rows(10 if problem == "small" else 100, 3 if problem == "few_clusters" else 1)
    features = ("duration_seconds",)
    if problem == "constant":
        for row in sample:
            row["outcome"] = 1
    elif problem == "collinear":
        features = ("duration_seconds", "caption_length")
        for row in sample:
            row["features"]["caption_length"] = row["features"]["duration_seconds"]
    result = regression(
        sample, PerformanceSpec(metric_key="demo.views.v1", model="ols", features=features)
    )
    assert result["status"] == "insufficient_data" and not result["terms"]


def test_cluster_models_are_real_and_guarded() -> None:
    sample = rows(240, 24)
    spec = PerformanceSpec(metric_key="demo.views.v1", model="gee", features=("duration_seconds",))
    result = regression(sample, spec)
    assert result["status"] == "fitted"
    design = sm.add_constant([row["features"]["duration_seconds"] for row in sample])
    expected = sm.GEE(
        [row["outcome"] for row in sample],
        design,
        groups=[row["creator_id"] for row in sample],
        family=sm.families.Gaussian(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    assert [row["estimate"] for row in result["terms"]] == pytest.approx(expected.params)
    mixed = regression(sample, spec.model_copy(update={"model": "mixed"}))
    assert mixed["status"] == "fitted", mixed
    assert abs(mixed["terms"][1]["estimate"] - 2) < 0.2
    assert regression(rows(30), spec)["status"] == "insufficient_data"


def test_poisson_and_overdispersion_gate() -> None:
    sample = rows(120)
    rng = np.random.default_rng(2)
    for row in sample:
        row["outcome"] = int(rng.poisson(np.exp(1 + 0.02 * row["features"]["duration_seconds"])))
    spec = PerformanceSpec(
        metric_key="demo.views.v1", model="poisson", features=("duration_seconds",)
    )
    assert regression(sample, spec)["status"] == "fitted"
    sample[0]["outcome"] = 100000
    result = regression(sample, spec)
    assert result["status"] == "insufficient_data" and "overdispersion" in result["reason"]


def test_correlation_uses_creator_aggregate_test_and_keeps_post_estimate_separate() -> None:
    sample = rows(240, 24)
    spec = PerformanceSpec(
        metric_key="demo.views.v1", features=("duration_seconds",), bootstrap_resamples=200
    )
    result = correlations(sample, spec)[0]
    assert result["estimate"] == pytest.approx(
        stats.spearmanr(
            [r["features"]["duration_seconds"] for r in sample], [r["outcome"] for r in sample]
        ).statistic
    )
    assert result["p_value"] is None
    assert result["diagnostics"]["creator_aggregate_adjusted_p_value"] is not None


def test_validation_fails_creator_future_target_and_duplicate_leakage() -> None:
    sample = rows(40, 5)
    with pytest.raises(ConfigurationError, match="Creator leakage"):
        audit_split(
            sample,
            list(range(20)),
            list(range(20, 40)),
            grouped=True,
            chronological=False,
            feature_names=("duration_seconds",),
        )
    with pytest.raises(ConfigurationError, match="Future"):
        audit_split(
            sample,
            [20, 21],
            [1, 2],
            grouped=False,
            chronological=True,
            feature_names=("duration_seconds",),
        )
    with pytest.raises(ConfigurationError, match="Target-derived"):
        audit_split(
            sample, [0, 1], [2, 3], grouped=False, chronological=True, feature_names=("views",)
        )
    sample[0]["feature_available_at"] = {"duration_seconds": "2099-01-01"}
    with pytest.raises(ConfigurationError, match="after publication"):
        audit_split(
            sample,
            [0, 1],
            [2, 3],
            grouped=False,
            chronological=True,
            feature_names=("duration_seconds",),
        )
    sample[0].pop("feature_available_at")
    sample[2]["post_id"] = sample[0]["post_id"]
    with pytest.raises(ConfigurationError, match="duplication"):
        audit_split(
            sample,
            [0, 1],
            [2, 3],
            grouped=False,
            chronological=True,
            feature_names=("duration_seconds",),
        )


def test_production_validation_fits_preprocessing_on_train_only() -> None:
    sample = rows(100, 10)
    for row in sample[80:]:
        row["features"]["duration_seconds"] = 1e9
    result = predictive_validation(sample, ("duration_seconds",), 42)
    evaluations = {row["split"]: row for row in result["evaluations"]}
    assert evaluations["chronological"]["training_medians"][0] < 100
    grouped = evaluations["creator_held_out"]
    creators = {row["post_id"]: row["creator_id"] for row in sample}
    assert not {creators[p] for p in grouped["train_post_ids"]}.intersection(
        creators[p] for p in grouped["test_post_ids"]
    )


def test_chronological_training_purges_late_collected_outcomes() -> None:
    sample = rows(100)
    sample[0]["outcome_available_at"] = "2099-01-01"
    with pytest.raises(ConfigurationError, match="outcomes were unavailable"):
        audit_split(
            sample,
            [0, 1],
            [80, 81],
            grouped=False,
            chronological=True,
            feature_names=("duration_seconds",),
        )
    result = predictive_validation(sample, ("duration_seconds",), 42)
    chronological = result["evaluations"][0]
    assert sample[0]["post_id"] not in chronological["train_post_ids"]


def test_perfect_prediction_is_not_published_as_certain_regression() -> None:
    sample = rows(100)
    for row in sample:
        row["outcome"] = 2 * row["features"]["duration_seconds"]
    result = regression(
        sample,
        PerformanceSpec(metric_key="demo.views.v1", model="ols", features=("duration_seconds",)),
    )
    assert result["status"] == "insufficient_data" and "Perfect prediction" in result["reason"]


def test_small_samples_are_descriptive_and_outliers_stay_visible() -> None:
    sample = rows(6)
    sample[0]["outcome"] = 1e12
    result = analyze_rows(sample, PerformanceSpec(metric_key="demo.views.v1"))
    assert result["claim_level"] == "observation"
    assert result["outcome"]["max"] == 1e12
    assert any("insufficient_data" in value for value in result["limitations"])
