"""Versioned professional vocabulary and pinned, human-review-first recipes."""

from socialdna.domain.production import (
    CRAFT_MODALITIES,
    CRAFT_VALUES,
    ProductionDefinition,
    ProductionRecipe,
)

DESCRIPTIONS = {
    "shot": "A reviewed continuous shot interval between editorial boundaries",
    "shot_size": "Apparent framing scale, not a recovered focal length",
    "camera_angle": "Reviewed apparent viewpoint relative to the subject",
    "composition": "Visible framing arrangement under the declared rubric",
    "camera_movement": "Reviewed camera-motion appearance, distinct from subject motion",
    "subject_movement": "Visible subject movement, not proof of camera movement",
    "lighting_appearance": "Visible illumination/contrast, not a recovered lighting rig",
    "color_look": "Rendered color appearance, not original grading settings or intent",
    "focus_depth": "Visible depth/focus cues, not recovered aperture or lens metadata",
    "transition": "Reviewed visible transition type, distinct from an instantaneous cut",
    "subtitle_design": "Visible subtitle interval and reviewed readability/style appearance",
    "visual_effect": "Reviewed visible effect appearance without inferring production software",
    "music_bed": "Reviewed audible music interval, not inferred licensing or intent",
    "music_beat": "A human-reviewed musical beat point, not an arbitrary audio onset",
    "sound_mix": "Reviewed audible speech/music balance under the declared listening conditions",
    "sound_image_relation": "Reviewed sound/image interpretation, not inferred reinforcement",
}
TECHNIQUES = {
    key: ProductionDefinition.model_validate(
        {
            "key": key,
            "modalities": sorted(CRAFT_MODALITIES[key]),
            "values": CRAFT_VALUES[key],
            "definition": description,
            "inclusion": "Literal visible/audible evidence and a permitted anchored category.",
            "exclusion": "No hidden settings, intent, psychological effect or quality inference.",
            "required_coverage": "Full-window human review for absence/duration summaries.",
            "procedure": "Use original time/coordinates, uncertainty, review and outcome access.",
            "examples": [description],
            "counterexamples": [
                "Sparse frames cannot establish unobserved motion or continuous absence."
            ],
        }
    )
    for key, description in DESCRIPTIONS.items()
}

_RECIPES = [
    (
        "shot_duration_mean",
        "shot_mean",
        ["shot"],
        ["visual"],
        "seconds",
        "Mean duration of exhaustive exact reviewed shots",
    ),
    (
        "shot_duration_median",
        "shot_median",
        ["shot"],
        ["visual"],
        "seconds",
        "Median duration of exhaustive exact reviewed shots",
    ),
    (
        "pacing_change",
        "pacing_change",
        ["shot"],
        ["visual"],
        "ratio",
        "Last-half versus first-half mean shot duration minus one",
    ),
    (
        "cuts_per_minute",
        "cuts_per_minute",
        ["cut"],
        ["visual"],
        "per_minute",
        "Reviewed cut count per original-media minute",
    ),
    (
        "subtitle_occupancy",
        "subtitle_occupancy",
        ["subtitle_design"],
        ["visual"],
        "ratio",
        "Union of reviewed subtitle-visible intervals / clip duration",
    ),
    (
        "cut_to_beat_rate",
        "cut_beat_rate",
        ["cut", "music_beat"],
        ["visual", "audio"],
        "ratio",
        "Fraction of reviewed cuts within 100 ms of a reviewed musical beat",
    ),
    (
        "angle_changes",
        "angle_changes",
        ["camera_angle"],
        ["visual"],
        "count",
        "Changes between ordered reviewed camera-angle intervals",
    ),
    (
        "close_up_presence",
        "close_up_presence",
        ["shot_size"],
        ["visual"],
        "binary",
        "Reviewed close/extreme-close framing presence, not quality",
    ),
]
RECIPES = {
    f"creative.{name}.v2": ProductionRecipe.model_validate(
        {
            "id": f"creative.{name}.v2",
            "operation": operation,
            "techniques": techniques,
            "modalities": modalities,
            "unit": unit,
            "description": description,
        }
    )
    for name, operation, techniques, modalities, unit, description in _RECIPES
}
