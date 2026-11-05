"""Pure source-value and grid operations. No pseudo-viewer sample sizes."""

import math
from typing import Any

from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.behavioral import (
    BehavioralMetricDefinition,
    MetricValue,
    ObservationClock,
)
from socialdna.domain.evidence import EntityRef


def metric_value(
    value: MetricValue,
    definition: BehavioralMetricDefinition,
    cohort: EntityRef,
    clock: ObservationClock,
) -> dict[str, Any]:
    components = [c for c in (value.numerator, value.denominator) if c]
    for component in components:
        expected = (
            definition.numerator_definition
            if component is value.numerator
            else definition.denominator_definition
        )
        if (
            component.definition != expected
            or component.cohort != cohort
            or component.window_start != clock.window_start
            or component.window_end != clock.window_end
            or component.population_basis != definition.population_basis
        ):
            raise ConfigurationError(
                "Incompatible component definition, cohort, window or population basis"
            )
    number, state, reason = value.value, value.availability, value.reason
    if value.availability != "available":
        number = None
    elif value.origin == "ratio_components":
        if definition.semantics not in ("ratio", "probability"):
            raise ConfigurationError(
                "Only ratio/probability definitions can derive component rates"
            )
        assert value.numerator and value.denominator
        if any(c.availability != "available" for c in components):
            missing = next(c for c in components if c.availability != "available")
            number, state, reason = (
                None,
                missing.availability,
                "missing_required_component: " + str(missing.reason),
            )
        elif value.denominator.value is not None and value.denominator.value <= 0:
            number, state, reason = None, "unavailable", "nonpositive_denominator"
        else:
            assert value.numerator.value is not None and value.denominator.value is not None
            number = value.numerator.value / value.denominator.value
    elif (
        value.denominator
        and value.denominator.value == 0
        and definition.semantics in ("ratio", "probability")
    ):
        number, state, reason = None, "unavailable", "nonpositive_denominator"
    if number is not None:
        if not math.isfinite(number) or abs(number) > 2**53:
            raise ConfigurationError("Metric value exceeds finite, lossless storage range")
        if definition.domain != "signed" and number < 0:
            raise ConfigurationError("This metric definition does not permit negative values")
        if definition.domain == "bounded_probability" and number > 1:
            raise ConfigurationError("Probability values must be in [0,1]")
        if definition.semantics == "count" and not float(number).is_integer():
            raise ConfigurationError("Count measurements require integer values")
    return {
        "value": number,
        "availability": state,
        "reason": reason,
        "denominator_known": value.denominator is not None and value.denominator.value is not None,
        "uncertainty": "not_estimated; aggregate bins are not independent viewers",
    }


def compatible_series(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    a, b = left["spec"], right["spec"]
    reasons = []
    for key in ("definition", "cohort", "coordinate_kind", "convention", "resolution"):
        if a[key] != b[key]:
            reasons.append("different_" + key)
    if left.get("cohort_known") is not True or right.get("cohort_known") is not True:
        reasons.append("unknown_cohort")
    for row in (left, right):
        spec = row["spec"]
        if spec["overlapping_bins"] or spec["completeness"] != "complete_for_declared_grid":
            reasons.append("incomplete_or_overlapping_grid")
        if spec["clock"]["data_cutoff"] != spec["clock"]["window_end"]:
            reasons.append("unknown_or_incomplete_source_freshness")
    if left["post_age_window_seconds"] != right["post_age_window_seconds"]:
        reasons.append("unaligned_post_age_windows")

    def grid(row: dict[str, Any]) -> list[tuple[Any, ...]]:
        return [(b["ordinal"], b["start"], b["end"], b["point"]) for b in row["spec"]["bins"]]

    if grid(left) != grid(right):
        reasons.append("different_source_grid; no_implicit_rebinning")
    return sorted(set(reasons))


def compare_series(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    reasons = compatible_series(left, right)
    differences = []
    if not reasons:
        for a, b in zip(left["bins"], right["bins"], strict=True):
            av, bv = a["result"]["value"], b["result"]["value"]
            differences.append(
                {
                    "ordinal": a["spec"]["ordinal"],
                    "difference": av - bv if av is not None and bv is not None else None,
                    "left_evidence": a["evidence"],
                    "right_evidence": b["evidence"],
                }
            )
    return {
        "status": "available" if not reasons else "incompatible",
        "reasons": reasons,
        "differences": differences,
        "independent_viewers": None,
        "confidence_interval": None,
        "interpretation": "descriptive differences on the exact source grid; not a causal effect",
    }
