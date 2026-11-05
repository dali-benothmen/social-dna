"""Controlled annotation fixtures test software semantics, not detector accuracy."""

from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.analytics.creative_recipes import evaluate_recipe
from socialdna.analyzers.creative import RECIPES, resample_candidates, temporal_relation
from socialdna.domain.creative import CreativeAnnotation, CreativeAnnotationSet, MediaAnchor


def anchor(start: int, end: int | None = None, *, uncertainty: int = 0) -> dict[str, Any]:
    if end is None:
        return {"kind": "point", "start_min_ms": start, "start_max_ms": start + uncertainty}
    return {
        "kind": "interval",
        "start_min_ms": start,
        "start_max_ms": start + uncertainty,
        "end_min_ms": end,
        "end_max_ms": end + uncertainty,
    }


def event(
    key: str, technique: str, start: int, end: int = 800, modality: str = "visual", **changes: Any
) -> dict[str, Any]:
    return {
        "annotation": {
            "key": key,
            "technique": technique,
            "modalities": [modality],
            "anchors": [anchor(start, end)],
            "state": "reviewed",
            "verdict": "present",
            **changes,
        }
    }


def bundle(*events: dict[str, Any], full: bool = True) -> dict[str, Any]:
    return {
        "events": list(events),
        "coverage": [
            {
                "coverage": {
                    "mode": "exhaustive_review" if full else "sampled",
                    "modality": modality,
                    "techniques": list(RECIPES_TECHNIQUES),
                    "intervals": [{"start_ms": 0, "end_ms": 3000}],
                }
            }
            for modality in ("visual", "speech", "audio", "color")
        ],
    }


RECIPES_TECHNIQUES = {
    "finished_dish",
    "preparation_instruction",
    "ingredient_display",
    "utility_promise",
    "sound_effect",
    "warm_color",
}


def value(recipe: str, data: dict[str, Any]) -> float | None:
    return evaluate_recipe(RECIPES["creative." + recipe + ".v1"], data)["value"]


@pytest.mark.parametrize(
    "data,expected",
    [
        (
            bundle(
                event("dish", "finished_dish", 0),
                event("prep", "preparation_instruction", 1000, 2000),
            ),
            1,
        ),
        (
            bundle(
                event("dish", "finished_dish", 1000, 1500),
                event("prep", "preparation_instruction", 0),
            ),
            0,
        ),
        (
            bundle(event("dish", "finished_dish", 0), event("prep", "preparation_instruction", 0)),
            None,
        ),
        (bundle(event("dish", "finished_dish", 0), full=False), None),
        (bundle(), 0),
        (bundle(full=False), None),
        (bundle(event("dish", "finished_dish", 0, state="proposed")), None),
        (bundle(event("dish", "finished_dish", 0, verdict="ambiguous")), None),
        (bundle(event("dish", "finished_dish", 0), event("unknown", "unclassified", 10)), None),
        (
            bundle(
                event("dish", "finished_dish", 0, anchors=[anchor(2900, 3200, uncertainty=200)])
            ),
            None,
        ),
    ],
)
def test_result_first_requires_review_and_unambiguous_order(
    data: dict[str, Any], expected: float | None
) -> None:
    assert value("result_first", data) == expected


def test_ingredient_first_and_modality_ablation() -> None:
    data = bundle(
        event("ingredient", "ingredient_display", 0),
        event("dish", "finished_dish", 1000, 1400),
        event("prep", "preparation_instruction", 1500, 2200),
        event("promise", "utility_promise", 100, 700, "speech"),
    )
    assert value("ingredient_first", data) == 1
    assert value("result_with_promise", data) == 1
    visual = {
        **data,
        "events": data["events"][:-1],
        "coverage": [c for c in data["coverage"] if c["coverage"]["modality"] != "speech"],
    }
    assert value("result_first", visual) == 1
    assert value("result_with_promise", visual) is None
    delayed = bundle(
        event("promise", "utility_promise", 3100, 3600, "speech"),
        event("subtitle", "utility_promise", 100, 700, "subtitle"),
    )
    assert value("spoken_promise", delayed) == 0
    assert value("subtitle_promise", delayed) == 1
    assert value("warm_color", bundle(full=False)) is None  # no brightness proxy


def test_synchrony_and_uncertain_opening_preserve_unknown() -> None:
    data = bundle(
        event("reveal", "finished_dish", 500), event("sfx", "sound_effect", 550, 700, "audio")
    )
    assert value("reveal_sfx_sync", data) == 1
    data["events"][1]["annotation"]["anchors"] = [anchor(560, 750, uncertainty=100)]
    assert value("reveal_sfx_sync", data) is None
    cut = bundle(
        event("cut", "cut", 500, anchors=[anchor(500)]),
        event("sfx", "sound_effect", 550, 700, "audio"),
    )
    assert value("cut_sfx_sync", cut) == 1
    data["events"][1]["annotation"]["anchors"] = [
        {"kind": "point", "unknown_reason": "missing audio localization"}
    ]
    assert value("reveal_sfx_sync", data) is None


@pytest.mark.parametrize(
    "raw",
    [
        anchor(10, 10),
        {"kind": "point", "start_min_ms": 0, "start_max_ms": 1, "end_min_ms": 2},
        {"kind": "interval", "start_min_ms": 0},
        {
            "kind": "interval",
            "start_min_ms": -1,
            "start_max_ms": 1,
            "end_min_ms": 2,
            "end_max_ms": 3,
        },
        {
            "kind": "interval",
            "start_min_ms": True,
            "start_max_ms": 1,
            "end_min_ms": 2,
            "end_max_ms": 3,
        },
        {"kind": "untimed", "start_min_ms": 0, "unknown_reason": "caption"},
        {"kind": "spatial", "start_min_ms": 0, "start_max_ms": 0, "box": [0, 0, 2, 1]},
        {"kind": "point"},
    ],
)
def test_invalid_bounds_are_rejected(raw: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MediaAnchor.model_validate(raw)


def test_interval_algebra_matches_all_feasible_integer_boundaries() -> None:
    # Includes overlapping uncertainty ranges: nominal centers would give wrong answers.
    anchors = [
        MediaAnchor.model_validate(anchor(start, end, uncertainty=uncertainty))
        for start, end, uncertainty in product(range(3), range(1, 4), range(2))
        if start < end + uncertainty
    ]
    anchors += [
        MediaAnchor.model_validate(anchor(start, uncertainty=uncertainty))
        for start, uncertainty in product(range(3), range(2))
    ]

    def feasible(a: MediaAnchor) -> list[tuple[int, int]]:
        assert a.start_min_ms is not None and a.start_max_ms is not None
        starts = range(a.start_min_ms, a.start_max_ms + 1)
        if a.kind == "point":
            return [(s, s) for s in starts]
        assert a.end_min_ms is not None and a.end_max_ms is not None
        return [(s, e) for s in starts for e in range(a.end_min_ms, a.end_max_ms + 1) if s < e]

    for a, b in product(anchors, repeat=2):
        cases = list(product(feasible(a), feasible(b)))
        for relation in ("precedes", "overlaps", "simultaneous_within_tolerance"):
            truths = []
            for (s, e), (t, u) in cases:
                if relation == "precedes":
                    truth = e < t if a.kind == "point" else e <= t
                elif relation == "simultaneous_within_tolerance":
                    truth = abs(s - t) <= 1
                elif a.kind == "point" and b.kind == "point":
                    truth = s == t
                elif a.kind == "point":
                    truth = t <= s < u
                elif b.kind == "point":
                    truth = s <= t < e
                else:
                    truth = s < u and t < e
                truths.append(truth)
            expected = "verified" if all(truths) else ("possible" if any(truths) else None)
            assert temporal_relation(a, b, relation, tolerance_ms=1) == expected


def test_budgeted_resampling_uses_actual_source_pts() -> None:
    times = [70, 153, 237, 401, 850, 1100, 2110, 2901]
    for budget in (0, 1, 4, 12):
        chosen = resample_candidates(
            times, [MediaAnchor.model_validate(anchor(400, 800))], limit=budget
        )
        assert len(chosen) <= budget
        assert all(0 <= i < len(times) for i in chosen)
        assert set(chosen.values()) <= {"creative-targeted"}
        assert chosen == resample_candidates(
            times, [MediaAnchor.model_validate(anchor(400, 800))], limit=budget
        )


def test_model_proposals_cannot_claim_review_or_blindness() -> None:
    document = {
        "key": "labels",
        "media_sha256": "a" * 64,
        "permission_basis": "owned",
        "protocol": {
            "origin": "model",
            "author": "local detector",
            "procedure": "v1",
            "outcome_access": "outcome_aware",
        },
    }
    with pytest.raises(ValidationError, match="provider"):
        CreativeAnnotationSet.model_validate(document)
    protocol = document["protocol"]
    assert isinstance(protocol, dict)
    protocol["provider"] = {
        "provider": "test",
        "model": "prepared",
        "revision": "sha256:123",
        "execution": "local",
    }
    assert CreativeAnnotationSet.model_validate(document).protocol.outcome_access == "outcome_aware"
    protocol["label_frozen_before_outcomes"] = True
    with pytest.raises(ValidationError, match="Outcome-aware"):
        CreativeAnnotationSet.model_validate(document)
    protocol["label_frozen_before_outcomes"] = False
    document["coverage"] = [
        {
            "modality": "visual",
            "techniques": ["finished_dish"],
            "mode": "exhaustive_review",
            "intervals": [{"start_ms": 0, "end_ms": 1000}],
            "limitation": "claimed exhaustive",
        }
    ]
    with pytest.raises(ValidationError, match="self-adjudicate"):
        CreativeAnnotationSet.model_validate(document)


def test_visual_technique_cannot_be_relabelled_as_speech() -> None:
    with pytest.raises(ValidationError, match="asserted modality"):
        CreativeAnnotation.model_validate(
            {
                "key": "dish",
                "technique": "finished_dish",
                "description": "Not visible evidence",
                "modalities": ["speech"],
                "anchors": [anchor(0, 100)],
            }
        )
