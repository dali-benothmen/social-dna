from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.analytics.production_recipes import evaluate_recipe
from socialdna.analyzers.production import RECIPES
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.production import ProductionAnnotationSet


def document() -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "key": "craft",
        "media_sha256": "a" * 64,
        "permission_basis": "Owned controlled fixture",
        "protocol": {
            "origin": "human",
            "author": "reviewer",
            "procedure": "continuous craft review",
            "outcome_access": "blinded",
        },
        "coverage": [
            {
                "modality": "visual",
                "techniques": ["shot", "cut", "subtitle_design", "camera_angle", "shot_size"],
                "mode": "exhaustive_review",
                "intervals": [{"start_ms": 0, "end_ms": 4000}],
                "limitation": "Controlled fixture",
            },
            {
                "modality": "audio",
                "techniques": ["music_beat"],
                "mode": "exhaustive_review",
                "intervals": [{"start_ms": 0, "end_ms": 4000}],
                "limitation": "Reviewed click track",
            },
        ],
        "events": [event("shot", f"shot-{i}", i * 1000, (i + 1) * 1000) for i in range(4)],
    }


def event(
    technique: str, key: str, start: int, end: int | None = None, value: str | None = None
) -> dict[str, Any]:
    return {
        "key": key,
        "technique": technique,
        "value": value,
        "description": "Controlled reviewed cue",
        "modalities": ["audio" if technique == "music_beat" else "visual"],
        "state": "reviewed",
        "reviewer": "reviewer",
        "anchors": [
            {
                "kind": "point" if end is None else "interval",
                "start_min_ms": start,
                "start_max_ms": start,
                **({"end_min_ms": end, "end_max_ms": end} if end is not None else {}),
            }
        ],
    }


def bundle(raw: dict[str, Any]) -> dict[str, Any]:
    spec = ProductionAnnotationSet.model_validate(raw)
    return {
        "duration_ms": 4000,
        "coverage": [{"coverage": c.model_dump(mode="json")} for c in spec.coverage],
        "events": [{"annotation": e.model_dump(mode="json")} for e in spec.events],
    }


def test_numeric_craft_recipes_are_exact_and_do_not_double_count() -> None:
    raw = document()
    raw["events"].extend(
        [
            event("cut", "cut", 1000),
            event("music_beat", "beat", 1050),
            event("subtitle_design", "a", 0, 2000, "readable"),
            event("subtitle_design", "b", 1000, 3000, "high_contrast"),
            event("camera_angle", "low", 0, 2000, "low"),
            event("camera_angle", "high", 2000, 4000, "high"),
            event("shot_size", "close", 0, 4000, "close"),
        ]
    )
    expected = {
        "shot_duration_mean": 1,
        "shot_duration_median": 1,
        "pacing_change": 0,
        "cuts_per_minute": 15,
        "subtitle_occupancy": 0.75,
        "cut_to_beat_rate": 1,
        "angle_changes": 1,
        "close_up_presence": 1,
    }
    for key, value in expected.items():
        assert evaluate_recipe(RECIPES[f"creative.{key}.v2"], bundle(raw))["value"] == value


@pytest.mark.parametrize(
    "change", ["sparse", "ambiguous", "uncertain_time", "gap", "overlap", "missing"]
)
def test_duration_never_invents_precision_or_unobserved_coverage(change: str) -> None:
    raw = document()
    if change == "sparse":
        raw["coverage"][0].update(mode="sampled")
    elif change == "ambiguous":
        raw["events"][0]["verdict"] = "ambiguous"
    elif change == "uncertain_time":
        raw["events"][0]["anchors"][0]["start_max_ms"] = 10
    elif change == "gap":
        raw["events"].pop(1)
    elif change == "overlap":
        raw["events"][0]["anchors"][0]["end_min_ms"] = raw["events"][0]["anchors"][0][
            "end_max_ms"
        ] = 1500
    else:
        raw["events"] = []
    assert evaluate_recipe(RECIPES["creative.shot_duration_mean.v2"], bundle(raw))["value"] is None


def test_cut_beat_denominators_and_duplicates_are_not_fabricated() -> None:
    raw = document()
    assert evaluate_recipe(RECIPES["creative.cut_to_beat_rate.v2"], bundle(raw))["value"] is None
    raw["events"] += [event("cut", "a", 1000), event("cut", "b", 1000)]
    assert evaluate_recipe(RECIPES["creative.cuts_per_minute.v2"], bundle(raw))["value"] is None


@pytest.mark.parametrize("position", [0, 4000])
def test_clip_endpoints_are_not_editorial_cuts(position: int) -> None:
    raw = document()
    raw["events"].append(event("cut", "boundary", position))
    assert evaluate_recipe(RECIPES["creative.cuts_per_minute.v2"], bundle(raw))["value"] is None


@pytest.mark.parametrize(
    ("technique", "recipe"),
    [("camera_angle", "angle_changes"), ("shot_size", "close_up_presence")],
)
def test_mixed_categories_do_not_establish_a_precise_sequence_or_absence(
    technique: str, recipe: str
) -> None:
    raw = document()
    raw["events"].append(event(technique, "mixed", 0, 4000, "mixed"))
    assert evaluate_recipe(RECIPES[f"creative.{recipe}.v2"], bundle(raw))["value"] is None


@pytest.mark.parametrize(
    "change", ["v1", "unknown", "category", "self_review", "motion", "sound_image"]
)
def test_version_and_interpretation_boundaries(change: str) -> None:
    raw = document()
    if change == "v1":
        raw["schema_version"] = "1.0"
        with pytest.raises(ValidationError):
            CreativeAnnotationSet.model_validate(raw)
        return
    if change == "unknown":
        raw["events"][0]["technique"] = "professional_quality"
    elif change == "category":
        raw["events"][0].update(technique="camera_angle", value="viral")
    elif change == "self_review":
        raw["protocol"]["origin"] = "deterministic"
    elif change == "motion":
        raw["events"][0].update(technique="camera_movement", value="moving")
    else:
        raw["events"][0].update(technique="sound_image_relation", value="reviewed_alignment")
    with pytest.raises(ValidationError):
        ProductionAnnotationSet.model_validate(raw)
