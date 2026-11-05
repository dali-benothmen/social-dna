"""Small pinned recipe grammar over observed cues, with explicit unknown states."""

from typing import Any

from socialdna.analyzers.creative import temporal_relation, window_membership
from socialdna.domain.creative import FeatureRecipe, MediaAnchor
from socialdna.domain.production import ProductionRecipe


def _covers(bundle: dict[str, Any], technique: str, modality: str, end_ms: int) -> bool:
    intervals = sorted(
        (interval["start_ms"], interval["end_ms"])
        for item in bundle["coverage"]
        if item["coverage"]["mode"] == "exhaustive_review"
        and item["coverage"]["modality"] == modality
        and technique in item["coverage"]["techniques"]
        for interval in item["coverage"]["intervals"]
    )
    end = 0
    for start, stop in intervals:
        if start > end:
            break
        end = max(end, stop)
    return end >= end_ms


def _events(
    bundle: dict[str, Any], technique: str, modalities: tuple[str, ...], proposals: bool
) -> tuple[list[dict[str, Any]], bool]:
    found, ambiguous = [], False
    for item in bundle["events"]:
        event = item["annotation"]
        if event["technique"] != technique or not set(event["modalities"]).intersection(modalities):
            continue
        if (
            event["state"] == "disputed"
            or event["verdict"] == "ambiguous"
            or (event["state"] != "reviewed" and not proposals)
        ):
            ambiguous = True
        else:
            found.append(item)
    return found, ambiguous


def _presence(
    bundle: dict[str, Any],
    technique: str,
    modalities: tuple[str, ...],
    window: int,
    proposals: bool,
) -> tuple[float | None, str]:
    events, ambiguous = _events(bundle, technique, modalities, proposals)
    for item in events:
        for raw in item["annotation"]["anchors"]:
            anchor = MediaAnchor.model_validate(raw)
            if anchor.kind == "untimed" and set(modalities).intersection(("caption", "hashtag")):
                return 1.0, "observed_present"
            membership = window_membership(anchor, window)
            if membership == "inside":
                return 1.0, "observed_present"
            if membership in ("unknown", "possible"):
                ambiguous = True
    if ambiguous:
        return None, "ambiguous_or_unreviewed"
    if any(_covers(bundle, technique, modality, window) for modality in modalities):
        return 0.0, "reviewed_absent"
    return None, "not_detected_with_coverage"


def _first(
    bundle: dict[str, Any], primary: str, competitors: tuple[str, ...], window: int
) -> tuple[float | None, str]:
    if not all(
        _covers(bundle, technique, "visual", window) for technique in (primary, *competitors)
    ):
        return None, "insufficient_review_coverage"
    if any(
        item["annotation"]["technique"] == "unclassified"
        and "visual" in item["annotation"]["modalities"]
        for item in bundle["events"]
    ):
        return None, "unclassified_visual_cue"
    primaries, ambiguous = _events(bundle, primary, ("visual",), False)
    others = []
    for technique in competitors:
        found, uncertain = _events(bundle, technique, ("visual",), False)
        others.extend(found)
        ambiguous = ambiguous or uncertain
    anchors = [
        MediaAnchor.model_validate(raw)
        for item in primaries
        for raw in item["annotation"]["anchors"]
    ]
    competing = [
        MediaAnchor.model_validate(raw) for item in others for raw in item["annotation"]["anchors"]
    ]
    if ambiguous or any(anchor.bounds() is None for anchor in (*anchors, *competing)):
        return None, "ambiguous_or_unreviewed"
    eligible = [a for a in anchors if window_membership(a, window) != "outside"]
    if not eligible:
        return 0.0, "reviewed_absent"
    if any(window_membership(a, window) == "possible" for a in eligible):
        return None, "opening_boundary_uncertain"
    competing_bounds = [bounds for anchor in competing if (bounds := anchor.bounds()) is not None]
    eligible_bounds = [bounds for anchor in eligible if (bounds := anchor.bounds()) is not None]
    for anchor in eligible:
        a = anchor.bounds()
        assert a is not None
        if all(a[1] < b[0] for b in competing_bounds):
            return 1.0, "reviewed_onset_before_preparation"
    if all(any(b[1] < a[0] for b in competing_bounds) for a in eligible_bounds):
        return 0.0, "reviewed_other_first"
    return None, "ordering_uncertain"


def dependencies(recipe: FeatureRecipe | ProductionRecipe) -> set[str]:
    result: set[str] = set(recipe.techniques)
    if recipe.operation == "conjunction":
        result.add("preparation_instruction")
    return result


def evaluate_recipe(
    recipe: FeatureRecipe, bundle: dict[str, Any], *, proposals: bool = False
) -> dict[str, Any]:
    if bundle.get("reason"):
        return {"value": None, "coverage": "unknown", "reason": bundle["reason"]}
    window = min(recipe.opening_ms, bundle.get("duration_ms", recipe.opening_ms))
    if recipe.operation == "first":
        value, reason = _first(bundle, recipe.techniques[0], tuple(recipe.techniques[1:]), window)
    elif recipe.operation == "conjunction":
        left, _ = _first(bundle, "finished_dish", ("preparation_instruction",), window)
        right, _ = _presence(bundle, "utility_promise", ("speech",), window, proposals)
        value, reason = (
            (left * right, "reviewed_multimodal_conjunction")
            if left is not None and right is not None
            else (None, "missing_or_ambiguous_component")
        )
    elif recipe.operation == "synchronized":
        visual_technique, audio_technique = recipe.techniques
        visual_events, la = _events(bundle, visual_technique, ("visual",), proposals)
        audio_events, ra = _events(bundle, audio_technique, ("audio",), proposals)
        statuses = [
            temporal_relation(a, b, "simultaneous_within_tolerance", recipe.tolerance_ms)
            for x in visual_events
            for y in audio_events
            for a in [MediaAnchor.model_validate(raw) for raw in x["annotation"]["anchors"]]
            for b in [MediaAnchor.model_validate(raw) for raw in y["annotation"]["anchors"]]
            if window_membership(a, window) == "inside" and window_membership(b, window) == "inside"
        ]
        if "verified" in statuses:
            value, reason = 1.0, "reviewed_onsets_synchronous"
        elif (
            "possible" in statuses
            or la
            or ra
            or any(
                window_membership(MediaAnchor.model_validate(raw), window)
                in ("possible", "unknown")
                for item in visual_events + audio_events
                for raw in item["annotation"]["anchors"]
            )
        ):
            value, reason = None, "synchrony_uncertain"
        elif _covers(bundle, visual_technique, "visual", window) and _covers(
            bundle, audio_technique, "audio", window
        ):
            value, reason = 0.0, "reviewed_no_synchronous_pair"
        else:
            value, reason = None, "missing_or_ambiguous_component"
    else:
        value, reason = _presence(
            bundle, recipe.techniques[0], recipe.modalities, window, proposals
        )
    return {
        "value": value,
        "coverage": "observed" if value is not None else "unknown",
        "reason": reason,
    }
