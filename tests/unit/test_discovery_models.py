"""Controlled model/split behavior; not empirical validity of social-media claims."""

from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from socialdna.application.discovery_confirmation import evaluate
from socialdna.core.exceptions import ConfigurationError
from socialdna.research import discovery
from socialdna.research.candidates import Candidate, ConfirmationSpec, DiscoverySpec


def candidate(kind: str, **changes: Any) -> Candidate:
    return Candidate.model_validate(
        {
            "key": kind,
            "kind": kind,
            "features": ["x", "z"] if kind == "interaction" else ["x"],
            "proposal_source": "prespecified controlled fixture",
            "prediction": "controlled association",
            **changes,
        }
    )


def options(**changes: Any) -> DiscoverySpec:
    # A real source adapter rejects x/z; pure numerical tests supply canonical-shaped rows.
    return DiscoverySpec.model_validate(
        {
            "key": "controlled",
            "family_id": "controlled",
            "holdout_id": "untouched",
            "as_of": "2026-11-01T00:00:00Z",
            "input": {
                "kind": "posts",
                "analysis": {
                    "metric_key": "demo.views.v1",
                    "design": "descriptive",
                    "estimand": "descriptive",
                    "feature_policy": "retrospective_content",
                    "knowledge_cutoff": "2026-11-01T00:00:00Z",
                    "publication_cutoff": "2026-10-01T00:00:00Z",
                    "sampling_frame": "Controlled canonical rows",
                    "features": ["caption_length"],
                    "covariates": ["caption_length"],
                    "family_id": "unused-source-only",
                    "family_terms": ["caption_length"],
                },
            },
            "scope": {
                "platform": "demo",
                "surface": "aggregate",
                "native_format": "video",
                "language": "en",
                "market": "GB",
                "audience": "controlled",
                "niches": ["cooking", "other"],
                "objective": "aggregate_attention",
                "traffic": "unknown",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-10-01T00:00:00Z",
                "basis": "declared test population",
            },
            "candidates": [
                candidate("main").model_dump(),
                candidate("interaction").model_dump(),
                candidate("quadratic").model_dump(),
            ],
            **changes,
        }
    )


def rows(kind: str = "interaction", creators: int = 36) -> list[dict[str, Any]]:
    rng = np.random.default_rng(120)
    result = []
    for creator in range(creators):
        for i in range(10):
            x, z = rng.uniform(-2, 2, size=2)
            niche = "cooking" if creator < creators - 6 else "other"
            signal = x * z if kind == "interaction" else x * x if kind == "quadratic" else 0
            if niche == "other":
                signal *= -1
            result.append(
                {
                    "unit_id": f"p{creator:02}-{i}",
                    "post_id": f"p{creator:02}-{i}",
                    "creator_id": f"c{creator:02}",
                    "niche": niche,
                    "published_at": f"2026-01-{i + 1:02}T00:00:00Z",
                    "outcome_end": f"2026-01-{i + 2:02}T00:00:00Z",
                    "outcome_available_at": "2026-11-01T00:00:00Z",
                    "features": {"x": x, "z": z, "redundant": x},
                    "outcome": float(100 + 20 * signal + rng.normal(0, 0.5)),
                    "duplicate_group": None,
                    "forecast": False,
                    "evidence": [],
                }
            )
    return result


def execute(*args: Any) -> dict[str, Any]:
    try:
        return args[-1]()
    except ConfigurationError as exc:
        return {"status": "insufficient_data", "reason": str(exc)}


@pytest.mark.parametrize("kind", ["interaction", "quadratic"])
def test_actual_selected_pipeline_recovers_nonlinearity_and_failed_transfer(kind: str) -> None:
    data, spec = rows(kind), options(transfer_niches=["other"])
    split = discovery.partitions(data, spec)
    result = discovery.run(data, spec, split, execute)
    assert result["selected"] == kind
    tested = result["outer"]["evaluations"]
    assert tested["in_scope"]["mae"] < tested["in_scope"]["baseline_mae"] * 0.1
    assert tested["transfer"]["mae"] > tested["transfer"]["baseline_mae"]
    assert tested["transfer"]["counterexamples"]["count"] > 0
    assert result["independent_confirmation"] is False
    assert result == discovery.run(data, spec, split, execute)
    # Changing only outer outcomes cannot affect transforms, alpha or candidate selection.
    changed = [
        {**r, "outcome": r["outcome"] + 10000}
        if r["unit_id"] in split["test"] + split["transfer"]
        else r
        for r in data
    ]
    second = discovery.run(changed, spec, split, execute)
    assert second["selected"] == result["selected"] and second["candidates"] == result["candidates"]


def test_spline_knots_scaling_and_regularization_are_training_only() -> None:
    data = rows("quadratic")
    model = discovery.fit(data[:200], candidate("spline", alphas=[1.0, 10.0]), 1.0)
    before = model.manifest.copy()
    predicted = model.predict(data[200:])
    assert len(predicted) == len(data[200:]) and model.manifest == before
    assert model.manifest["knots"] and discovery.contrast(model, data[:200])["p_value"] is None
    with pytest.raises(ConfigurationError, match="Aliased"):
        discovery.fit(data, candidate("main", adjusters=["redundant"]), 0)
    assert discovery.fit(data, candidate("main", adjusters=["redundant"]), 1).predict(
        data
    ).shape == (360,)


def test_duplicates_creator_niche_separation_and_small_cluster_refusals() -> None:
    data, spec = rows(), options(transfer_niches=["other"])
    data[0]["duplicate_group"] = data[-1]["duplicate_group"] = "same-bytes"
    split = discovery.partitions(data, spec)
    assert data[0]["unit_id"] in split["purged"]
    by_id = {r["unit_id"]: r for r in data}
    assert not {by_id[i]["creator_id"] for i in split["train"]}.intersection(
        {by_id[i]["creator_id"] for i in split["test"] + split["transfer"]}
    )
    result = discovery.run(
        rows(creators=4), spec, discovery.partitions(rows(creators=4), spec), execute
    )
    assert result["selected"] is None and len(result["candidates"]) == 3
    assert all(c["training"]["status"] == "insufficient_data" for c in result["candidates"])
    with pytest.raises(ConfigurationError, match="Supplied creator"):
        discovery.fit(
            [{**r, "creator_identity": "account_proxy"} for r in data], candidate("main"), 0
        )


def test_chronological_splits_purge_overlapping_outcomes_and_unknown_forecasts() -> None:
    data, spec = rows(), options(split="joint")
    split = discovery.partitions(data, spec)
    by_id = {r["unit_id"]: r for r in data}
    assert all(by_id[i]["outcome_end"] < split["threshold"] for i in split["train"])
    for row in data:
        row["forecast"] = True
    assert discovery.partitions(data, spec)["train"] == []


def test_fixed_budget_grammar_and_null_family_correction() -> None:
    with pytest.raises(ValidationError, match="budget"):
        options(max_fits=3)
    with pytest.raises(ValidationError):
        candidate("interaction", features=["x", "x"])
    data, spec = rows("null", creators=40), options(transfer_niches=["other"])
    result = discovery.run(data, spec, discovery.partitions(data, spec), execute)
    assert result["multiplicity"]["family_size"] == 3
    assert all(c["training"]["contrast"]["adjusted_p_value"] > 0.05 for c in result["candidates"])


def test_independent_contrast_preserves_support_contradiction_and_insufficiency() -> None:
    base = options()
    spec = ConfirmationSpec.model_validate(
        {
            "key": "confirmation",
            "family_id": "confirmation",
            "discovery": {"kind": "discovery_search", "id": "prior", "revision_id": "revision"},
            "input": base.input.model_dump(mode="json"),
            "scope": base.scope.model_dump(mode="json"),
            "as_of": base.as_of,
            "holdout_id": "new-cohort",
            "direction": "positive",
            "minimum_absolute_effect": 5,
            "interpretation": "Positive raw product coefficient above five",
        }
    )
    source = rows(creators=36)
    positive = [
        {**r, "outcome": 100 + 20 * r["features"]["x"] * r["features"]["z"] + (i % 3) * 0.2}
        for i, r in enumerate(source)
    ]
    negative = [{**r, "outcome": 200 - r["outcome"]} for r in positive]
    supported = evaluate(positive, candidate("interaction"), spec)
    contradicted = evaluate(negative, candidate("interaction"), spec)
    assert supported["disposition"] == "supports_prespecified_contrast"
    assert contradicted["disposition"] == "contradicts_prespecified_direction"
    assert evaluate(positive[:20], candidate("interaction"), spec)["status"] == "insufficient_data"
