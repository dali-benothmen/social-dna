"""Bounded literal proposals and temporal algebra over observable annotations."""

import bisect
import re
from typing import Any

from socialdna.domain.creative import (
    TECHNIQUE_MODALITIES,
    CreativeTechnique,
    FeatureRecipe,
    MediaAnchor,
)

_DEFINITIONS = {
    "finished_dish": (
        "A visibly prepared final dish",
        "Final serving state is visible",
        "Raw ingredients, intermediate cooking, thumbnails outside the video",
    ),
    "ingredient_display": (
        "Visible ingredients before preparation",
        "Recognizable unprepared ingredients",
        "A prepared meal alone",
    ),
    "preparation_instruction": (
        "A substantive preparation step or instruction",
        "An actual preparation action/instruction",
        "A title, promise or decorative montage alone",
    ),
    "utility_promise": (
        "An explicit textual promise of an outcome or utility",
        "Literal quoted wording with track/post provenance",
        "Inferred viewer benefit or emotion without wording",
    ),
    "text_overlay": (
        "Text visibly overlaid on a video frame",
        "Human-reviewed image text or an OCR proposal",
        "Supplied subtitles alone do not prove visible overlays",
    ),
    "sound_effect": (
        "An identifiable sound effect candidate",
        "Literal annotated audio event",
        "RMS/loudness alone does not identify an SFX",
    ),
    "cut": (
        "An editing cut at an original-media point",
        "Observed transition with its uncertainty",
        "A static frame without transition evidence",
    ),
    "warm_color": (
        "An explicitly reviewed warm-color appearance annotation",
        "Reviewed visual color characterization",
        "Brightness alone is not warmth or sensory appeal",
    ),
    "hashtag": (
        "A supplied normalized hashtag",
        "Captured exported hashtag text",
        "Hashtags are not ground-truth niche labels",
    ),
    "unclassified": (
        "An observable but unclassified creative cue",
        "Literal description and evidence",
        "Psychological diagnosis, intent or performance claims",
    ),
}
TECHNIQUES = {
    key: CreativeTechnique.model_validate(
        {
            "key": key,
            "modalities": sorted(TECHNIQUE_MODALITIES[key]),
            "definition": definition,
            "inclusion": inclusion,
            "exclusion": exclusion,
            "required_coverage": "Positive evidence supports presence; absence requires exhaustive "
            "human review of the declared technique/window",
            "procedure": "Record exact inputs, modality, uncertainty, reviewer and "
            "outcome-access protocol",
            "examples": [inclusion],
            "counterexamples": [exclusion],
        }
    )
    for key, (definition, inclusion, exclusion) in _DEFINITIONS.items()
}

_RECIPES = [
    (
        "creative.finished_dish_opening.v1",
        "presence",
        ["finished_dish"],
        ["visual"],
        "Reviewed final dish within [0,3000ms)",
    ),
    (
        "creative.result_first.v1",
        "first",
        ["finished_dish", "preparation_instruction"],
        ["visual"],
        "Final dish in opening, before substantive visual preparation; "
        "exhaustive visual review required",
    ),
    (
        "creative.ingredient_first.v1",
        "first",
        ["ingredient_display", "finished_dish", "preparation_instruction"],
        ["visual"],
        "Ingredients in opening before final dish/preparation; exhaustive visual review required",
    ),
    (
        "creative.spoken_promise.v1",
        "presence",
        ["utility_promise"],
        ["speech"],
        "Reviewed spoken wording, not an assumption from subtitles",
    ),
    (
        "creative.subtitle_promise.v1",
        "presence",
        ["utility_promise"],
        ["subtitle"],
        "Reviewed supplied subtitle wording; does not establish speech or visible overlay",
    ),
    (
        "creative.warm_color.v1",
        "presence",
        ["warm_color"],
        ["color", "visual"],
        "Explicit reviewed warm-color annotation, not brightness",
    ),
    (
        "creative.result_with_promise.v1",
        "conjunction",
        ["finished_dish", "utility_promise"],
        ["visual", "speech"],
        "Result-first visual opening AND reviewed spoken promise; preserve missing modality",
    ),
    (
        "creative.reveal_sfx_sync.v1",
        "synchronized",
        ["finished_dish", "sound_effect"],
        ["visual", "audio"],
        "Reviewed reveal and SFX onsets within 100ms; no semantic reinforcement claim",
    ),
    (
        "creative.caption_promise.v1",
        "presence",
        ["utility_promise"],
        ["caption"],
        "Reviewed untimed caption wording; not narration or an opening timestamp",
    ),
    (
        "creative.hashtag_count.v1",
        "hashtag_count",
        ["hashtag"],
        ["hashtag"],
        "Number of supplied normalized hashtags, not inferred topic membership",
    ),
]
RECIPES = {
    identity: FeatureRecipe.model_validate(
        {
            "id": identity,
            "operation": operation,
            "techniques": techniques,
            "modalities": modalities,
            "description": description,
            "unit": "count" if operation == "hashtag_count" else "binary",
        }
    )
    for identity, operation, techniques, modalities, description in _RECIPES
}
RECIPES["creative.cut_sfx_sync.v1"] = FeatureRecipe(
    id="creative.cut_sfx_sync.v1",
    operation="synchronized",
    techniques=("cut", "sound_effect"),
    modalities=("visual", "audio"),
    description="Reviewed visual cut and sound-effect onsets within 100 ms; temporal only",
)


def temporal_relation(
    left: MediaAnchor, right: MediaAnchor, relation: str, tolerance_ms: int = 100
) -> str | None:
    a, b = left.bounds(), right.bounds()
    if a is None or b is None:
        return None
    if relation == "precedes":
        gap = 1 if left.kind in ("point", "spatial") else 0
        verified, possible = a[3] + gap <= b[0], a[2] + gap <= b[1]
    elif relation == "simultaneous_within_tolerance":
        verified = max(abs(a[0] - b[1]), abs(a[1] - b[0])) <= tolerance_ms
        possible = max(0, a[0] - b[1], b[0] - a[1]) <= tolerance_ms
    elif relation == "overlaps":
        ap, bp = left.kind in ("point", "spatial"), right.kind in ("point", "spatial")
        if ap and bp:
            verified = a[0] == a[1] == b[0] == b[1]
            possible = max(a[0], b[0]) <= min(a[1], b[1])
        elif ap:
            verified, possible = a[0] >= b[1] and a[1] < b[2], a[1] >= b[0] and a[0] < b[3]
        elif bp:
            return temporal_relation(right, left, relation, tolerance_ms)
        else:
            verified, possible = a[3] > b[1] and b[3] > a[1], a[3] > b[0] and b[3] > a[0]
            # For universal overlap use the earliest feasible ends, not latest ends.
            verified = a[2] > b[1] and b[2] > a[1]
    else:
        raise ValueError("Unknown temporal relation")
    return "verified" if verified else ("possible" if possible else None)


def window_membership(anchor: MediaAnchor, end_ms: int) -> str:
    bounds = anchor.bounds()
    if bounds is None:
        return "unknown"
    if bounds[0] >= end_ms:
        return "outside"
    return "inside" if bounds[1] < end_ms else "possible"


def resample_candidates(
    times: list[int], anchors: list[MediaAnchor], *, opening_ms: int = 3000, limit: int = 12
) -> dict[int, str]:
    """Snap bounded requests to REAL source PTS; no fabricated frame timestamps."""
    if not times or limit == 0:
        return {}
    requests = {t for t in range(0, min(times[-1] + 1, opening_ms), 250)}
    for anchor in anchors:
        bounds = anchor.bounds()
        if bounds:
            for boundary in bounds:
                requests.update((max(0, boundary - 100), boundary, boundary + 100))
    indices = sorted(
        {
            min(bisect.bisect_left(times, time), len(times) - 1)
            for time in requests
            if time <= times[-1]
        }
    )
    if len(indices) > limit:
        indices = (
            [indices[round(i * (len(indices) - 1) / (limit - 1))] for i in range(limit)]
            if limit > 1
            else indices[:1]
        )
    # Preserve actual requested samples even for static frames; deduplication is
    # NOT temporal coverage. Existing extractor already preserves scene-keyframes.
    return dict.fromkeys(indices, "creative-targeted")


PROMISE = re.compile(
    r"\b(?:you(?:'|’)ll (?:learn|make|save)|learn how|in \d+ minutes|"
    r"ready in \d+|save (?:time|money))\b",
    re.IGNORECASE,
)


def literal_proposals(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Literal wording candidates only. No object, emotion or intent inference."""
    result = []
    for segment in segments:
        match = PROMISE.search(segment["text"])
        if not match:
            continue
        modality = segment["modality"]
        anchor = (
            MediaAnchor(kind="untimed", unknown_reason="Post text has no playback coordinate")
            if modality in ("caption", "hashtag")
            else MediaAnchor(
                start_min_ms=segment["start_ms"],
                start_max_ms=segment["start_ms"],
                end_min_ms=segment["end_ms"],
                end_max_ms=segment["end_ms"],
            )
        )
        result.append(
            {
                "key": "literal-" + segment["id"],
                "technique": "utility_promise",
                "description": "Literal wording candidate: " + match.group(),
                "modalities": [modality],
                "anchors": [anchor.model_dump(mode="json")],
                "inputs": segment["inputs"],
                "state": "proposed",
                "verdict": "present",
                "reliability": "low",
                "post": segment.get("post"),
            }
        )
        if len(result) == 64:
            break
    return result
