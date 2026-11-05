from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.analytics.retention import metric_value
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.behavioral import (
    BehavioralMetricDefinition,
    MetricSeries,
    MetricValue,
    ObservationClock,
)

COHORT = {"kind": "audience_cohort", "id": "cohort", "revision_id": "revision"}
START, END = "2026-01-01T00:00:00Z", "2026-01-08T00:00:00Z"


def definition(**changes: Any) -> BehavioralMetricDefinition:
    return BehavioralMetricDefinition.model_validate(
        {
            "key": "demo.retention.v1",
            "platform": "demo",
            "subject_type": "post",
            "meaning": "retention",
            "semantics": "ratio",
            "unit": "repeat-inclusive watch ratio",
            "domain": "nonnegative",
            "measurement": "series",
            "numerator_definition": "watch events",
            "denominator_definition": "eligible plays",
            "population_basis": "plays",
            "replay_policy": "includes_replays",
            "source_definition_uri": "urn:owned:definition",
            "description": "Owned source definition, not a survival probability",
            **changes,
        }
    )


def clock() -> ObservationClock:
    return ObservationClock(window_start=START, window_end=END, data_cutoff=END, collected_at=END)


def component(value: int, label: str) -> dict[str, Any]:
    return {
        "value": value,
        "definition": label,
        "population_basis": "plays",
        "cohort": COHORT,
        "window_start": START,
        "window_end": END,
    }


@pytest.mark.parametrize(
    "numerator,denominator,expected", [(120, 100, 1.2), (0, 100, 0), (1, 0, None)]
)
def test_component_rates_preserve_replays_and_zero_denominators(
    numerator: int, denominator: int, expected: float | None
) -> None:
    from socialdna.domain.evidence import EntityRef

    value = MetricValue.model_validate(
        {
            "origin": "ratio_components",
            "numerator": component(numerator, "watch events"),
            "denominator": component(denominator, "eligible plays"),
        }
    )
    result = metric_value(value, definition(), EntityRef.model_validate(COHORT), clock())
    assert result["value"] == expected
    assert result["availability"] == ("available" if expected is not None else "unavailable")
    assert "not_estimated" in result["uncertainty"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("definition", "incompatible"),
        ("population_basis", "unique_viewers"),
        ("window_end", "2026-01-07T00:00:00Z"),
        ("cohort", {**COHORT, "id": "other"}),
    ],
)
def test_rate_components_cannot_borrow_denominators(field: str, value: Any) -> None:
    from socialdna.domain.evidence import EntityRef

    denominator = {**component(100, "eligible plays"), field: value}
    metric = MetricValue.model_validate(
        {
            "origin": "ratio_components",
            "numerator": component(20, "watch events"),
            "denominator": denominator,
        }
    )
    with pytest.raises(ConfigurationError, match="Incompatible component"):
        metric_value(metric, definition(), EntityRef.model_validate(COHORT), clock())


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf"), 2**53 + 1, 10**400])
def test_observations_require_finite_actual_numbers(value: Any) -> None:
    with pytest.raises(ValidationError):
        MetricValue(value=value)


def test_probabilities_and_completion_thresholds_are_not_generic_watch_ratios() -> None:
    from socialdna.domain.evidence import EntityRef

    probability = definition(semantics="probability", domain="bounded_probability")
    with pytest.raises(ConfigurationError, match="Probability"):
        metric_value(MetricValue(value=1.2), probability, EntityRef.model_validate(COHORT), clock())
    with pytest.raises(ValidationError, match="Completion"):
        definition(meaning="completion", semantics="probability", domain="bounded_probability")
    assert (
        definition(
            meaning="completion",
            semantics="probability",
            domain="bounded_probability",
            completion_threshold=0.95,
        ).completion_threshold
        == 0.95
    )


def test_series_preserve_coarse_bins_and_reject_implicit_overlap() -> None:
    raw = {
        "key": "coarse",
        "subject": {"kind": "post", "id": "p", "revision_id": "r"},
        "definition": {"kind": "behavioral_metric_definition", "id": "d", "revision_id": "r"},
        "cohort": COHORT,
        "clock": clock().model_dump(),
        "coordinate_kind": "normalized_progress",
        "resolution": "Two half-video intervals",
        "convention": "half_open_intervals",
        "completeness": "complete_for_declared_grid",
        "expected_bins": 2,
        "bins": [
            {"ordinal": 0, "start": 0, "end": 0.5, "measurement": {"value": 1.2}},
            {"ordinal": 1, "start": 0.5, "end": 1, "measurement": {"value": 0.9}},
        ],
    }
    series = MetricSeries.model_validate(raw)
    assert len(series.bins) == 2 and series.media is None
    raw["bins"][1]["start"] = 0.4
    with pytest.raises(ValidationError, match="overlapping"):
        MetricSeries.model_validate(raw)


@pytest.mark.parametrize("state", ["not_supplied", "not_permitted", "failed", "source_suppressed"])
def test_unavailable_derived_rates_never_compute_forbidden_values(state: str) -> None:
    from socialdna.domain.evidence import EntityRef

    value = MetricValue.model_validate(
        {
            "origin": "ratio_components",
            "availability": state,
            "reason": "Declared source restriction",
            "numerator": component(120, "watch events"),
            "denominator": component(100, "eligible plays"),
        }
    )
    result = metric_value(value, definition(), EntityRef.model_validate(COHORT), clock())
    assert result["value"] is None and result["availability"] == state


def test_suppressed_components_preserve_their_distinct_state() -> None:
    from socialdna.domain.evidence import EntityRef

    denominator = {
        **component(100, "eligible plays"),
        "value": None,
        "availability": "source_suppressed",
        "reason": "Provider privacy threshold",
    }
    value = MetricValue.model_validate(
        {
            "origin": "ratio_components",
            "numerator": component(120, "watch events"),
            "denominator": denominator,
        }
    )
    result = metric_value(value, definition(), EntityRef.model_validate(COHORT), clock())
    assert result["value"] is None and result["availability"] == "source_suppressed"


def test_account_size_joins_respect_world_and_actual_knowledge_clocks() -> None:
    from socialdna.analytics.metrics import account_size_as_of

    def observation(available: str, world: str, value: int) -> dict[str, Any]:
        return {
            "ref": {"revision_id": str(value)},
            "available_at": available,
            "spec": {"clock": {"data_cutoff": world, "window_end": world}},
            "result": {"value": value, "availability": "available"},
        }

    rows = [
        observation("2026-01-02", "2026-01-01", 100),
        observation("2026-01-10", "2026-01-08", 90),
    ]
    assert account_size_as_of(rows, "2026-01-08", "2026-01-08")["value"] == 100
    assert account_size_as_of(rows, "2026-01-08", "2026-01-11")["value"] == 90
    assert account_size_as_of(rows, "2026-01-08", "2026-01-08", exact=True)["value"] is None


def test_conflicting_account_endpoint_sources_are_not_silently_selected() -> None:
    from socialdna.analytics.metrics import account_size_as_of

    rows = [
        {
            "ref": {"revision_id": str(value)},
            "available_at": "2026-01-10",
            "spec": {"clock": {"data_cutoff": "2026-01-08", "window_end": "2026-01-08"}},
            "result": {"value": value, "availability": "available"},
        }
        for value in (90, 95)
    ]
    result = account_size_as_of(rows, "2026-01-08", "2026-01-11", exact=True)
    assert result["value"] is None and result["reason"] == "conflicting_endpoint_sources"


def test_behavioral_example_templates_match_versioned_contracts() -> None:
    from pathlib import Path

    from socialdna.domain.behavioral import AccountOutcomeSpec, BehavioralExport

    examples = Path(__file__).resolve().parents[2] / "examples" / "behavioral"
    for name in ("definitions.json", "observations.json"):
        BehavioralExport.model_validate_json((examples / name).read_text())
    AccountOutcomeSpec.model_validate_json((examples / "account-outcomes.json").read_text())
