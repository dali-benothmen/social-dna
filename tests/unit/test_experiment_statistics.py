"""Actual matched-block estimator on controlled data, not empirical validation."""

from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from socialdna.analytics.experiments import analyze
from socialdna.research.experiments import ExperimentSpec


def plan(*, outcomes: int = 1) -> ExperimentSpec:
    return ExperimentSpec.model_validate(
        {
            "key": "controlled",
            "domain": "production",
            "assignment_unit": "post",
            "assignment_method": "engine_block_randomized",
            "scope": {
                "platform": "demo",
                "surface": "aggregate",
                "native_format": "video",
                "language": "en",
                "market": "GB",
                "audience": "controlled",
                "niches": ["cooking"],
                "objective": "aggregate_attention",
                "traffic": "unknown",
                "period_start": "2026-08-01T00:00:00Z",
                "period_end": "2026-09-01T00:00:00Z",
                "basis": "Controlled numerical test",
            },
            "variants": [
                {"key": "a", "change": "Preparation first"},
                {"key": "b", "change": "Result preview first"},
            ],
            "units": [
                {
                    "key": f"p{i}-{j}",
                    "account": {"kind": "account", "id": f"c{i}", "revision_id": f"r{i}"},
                    "block": f"c{i}",
                    "starts_at": f"2026-08-0{5 + j}T00:00:00Z",
                }
                for i in range(24)
                for j in range(2)
            ],
            "outcomes": [
                {
                    "key": f"o{i}",
                    "definition": {
                        "kind": "behavioral_metric_definition",
                        "id": f"metric{i}",
                        "revision_id": f"m{i}",
                    },
                    "role": "primary" if i == 0 else "secondary",
                    "direction": "positive",
                    "minimum_meaningful_difference": 1,
                    "window_seconds": 86400,
                }
                for i in range(outcomes)
            ],
            "permutation_resamples": 999,
            "precision_rationale": "Controlled fixture only",
            "held_constant": ["Other creative details"],
            "interference_plan": "Independent controlled blocks",
            "authority": "Owned fixture",
            "ethics_and_permissions": "No participants",
        }
    )


def sample(spec: ExperimentSpec, *, effect: float = 10) -> dict[str, Any]:
    rng = np.random.default_rng(161)
    rows = []
    for i in range(24):
        base = rng.normal(100, 10)
        delta = effect + rng.normal(0, 1)
        for j, arm in enumerate(("a", "b")):
            rows.append(
                {
                    "unit_key": f"p{i}-{j}",
                    "block": f"c{i}",
                    "assigned": arm,
                    "values": {o.key: float(base + j * delta) for o in spec.outcomes},
                }
            )
    return {"rows": rows, "threats": []}


@pytest.mark.parametrize(
    ("effect", "disposition"),
    [(10, "supported_in_scope"), (-10, "contradicted_in_scope"), (0, "inconclusive")],
)
def test_fixed_assignment_pipeline_recovery_and_null(effect: float, disposition: str) -> None:
    spec = plan()
    data = sample(spec, effect=effect)
    result = analyze(spec, data)
    assert result["outcomes"][0]["disposition"] == disposition
    assert result == analyze(spec, data)
    assert result["mechanism_status"].startswith("not_identified")


def test_missing_secondary_remains_in_the_family() -> None:
    spec = plan(outcomes=3)
    data = sample(spec)
    for row in data["rows"]:
        row["values"]["o2"] = None
    result = analyze(spec, data)
    assert result["multiplicity"]["family_size"] == 3
    assert result["outcomes"][0]["disposition"] == "supported_in_scope"
    assert result["outcomes"][2]["p_value"] is None
    assert result["outcomes"][0]["assigned_units"] == 48
    small = analyze(spec, {"rows": data["rows"][:6], "threats": []})
    assert small["outcomes"][0]["p_value"] is None


def test_native_denominators_are_not_independent_impression_assignments() -> None:
    base = plan()
    raw = base.model_dump(mode="json")
    raw.update(assignment_method="source_native", assignment_unit="impression")
    raw["units"] = [
        {**u, "variant": arm} for u, arm in zip(raw["units"][:2], ("a", "b"), strict=True)
    ]
    spec = ExperimentSpec.model_validate(raw)
    rows = sample(base)["rows"][:2]
    for row in rows:
        row["exposures"] = 1000000
    result = analyze(spec, {"rows": rows, "threats": []})
    assert result["registered_units"] == 2
    assert result["outcomes"][0]["p_value"] is None
    assert result["claim_level"] == "descriptive_observational"


def test_pairing_and_mechanism_contracts_are_not_optional() -> None:
    raw = plan().model_dump(mode="json")
    raw["units"] = raw["units"][:-1]
    with pytest.raises(ValidationError, match="matched"):
        ExperimentSpec.model_validate(raw)
    raw = plan().model_dump(mode="json")
    raw["outcomes"][0]["role"] = "mechanism"
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(raw)
