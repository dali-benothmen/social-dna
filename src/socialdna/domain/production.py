"""Professional craft annotations v2; legacy creative v1 remains a closed schema."""

from typing import Literal

from pydantic import Field, model_validator

from socialdna.core.time import MediaInterval
from socialdna.domain.creative import (
    TECHNIQUE_MODALITIES,
    AnnotationProtocol,
    CreativeAnnotation,
    CreativeInput,
    CreativeModel,
    MediaAnchor,
    Modality,
    SamplingCoverage,
    Technique,
)
from socialdna.domain.evidence import EntityRef

CraftTechnique = Literal[
    "shot",
    "shot_size",
    "camera_angle",
    "composition",
    "camera_movement",
    "subject_movement",
    "lighting_appearance",
    "color_look",
    "focus_depth",
    "transition",
    "subtitle_design",
    "visual_effect",
    "music_bed",
    "music_beat",
    "sound_mix",
    "sound_image_relation",
]
ProductionTechnique = Technique | CraftTechnique

# Categories describe reviewed visible/audible appearances, not recovered rigs,
# lens metadata, original grades, intent, narrative effects or production quality.
CRAFT_VALUES: dict[str, tuple[str, ...]] = {
    "shot": (),
    "shot_size": ("extreme_wide", "wide", "medium", "close", "extreme_close", "mixed", "uncertain"),
    "camera_angle": ("eye_level", "high", "low", "overhead", "dutch", "mixed", "uncertain"),
    "composition": ("centered", "thirds", "negative_space", "symmetrical", "mixed", "uncertain"),
    "camera_movement": (
        "static",
        "pan",
        "tilt",
        "dolly_like",
        "handheld_like",
        "zoom_like",
        "uncertain",
    ),
    "subject_movement": ("static", "moving", "uncertain"),
    "lighting_appearance": (
        "bright_even",
        "high_contrast",
        "low_key",
        "backlit",
        "mixed",
        "uncertain",
    ),
    "color_look": ("warm", "cool", "neutral", "saturated", "muted", "mixed", "uncertain"),
    "focus_depth": ("shallow_appearance", "deep_appearance", "focus_shift", "uncertain"),
    "transition": ("dissolve", "fade", "wipe", "match_transition", "other", "uncertain"),
    "subtitle_design": ("readable", "small", "occluded", "high_contrast", "other", "uncertain"),
    "visual_effect": ("composite", "speed_change", "graphic", "other", "uncertain"),
    "music_bed": (),
    "music_beat": (),
    "sound_mix": ("speech_clear", "speech_masked", "balanced_appearance", "uncertain"),
    "sound_image_relation": ("reviewed_alignment", "reviewed_contrast", "uncertain"),
}
CRAFT_MODALITIES: dict[str, set[str]] = {
    key: {"audio"}
    if key in ("music_bed", "music_beat", "sound_mix")
    else {"visual", "audio"}
    if key == "sound_image_relation"
    else {"visual", "subtitle", "overlay"}
    if key == "subtitle_design"
    else {"visual", "motion"}
    if key in ("camera_movement", "subject_movement")
    else {"visual", "color"}
    if key == "color_look"
    else {"visual"}
    for key in CRAFT_VALUES
}


class ProductionAnnotation(CreativeModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    technique: ProductionTechnique
    value: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=3000)
    modalities: tuple[Modality, ...] = Field(min_length=1, max_length=9)
    anchors: tuple[MediaAnchor, ...] = Field(min_length=1, max_length=20)
    inputs: tuple[CreativeInput, ...] = Field(default=(), max_length=40)
    state: Literal["proposed", "reviewed", "disputed"] = "proposed"
    verdict: Literal["present", "ambiguous"] = "present"
    reliability: Literal["low", "medium", "high"] = "low"
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)
    post: EntityRef | None = None

    @model_validator(mode="after")
    def coherent(self) -> "ProductionAnnotation":
        # Reuse v1's timing/input/review invariants without broadening its labels.
        CreativeAnnotation.model_validate(
            {
                **self.model_dump(exclude={"value"}),
                "technique": self.technique
                if self.technique in TECHNIQUE_MODALITIES
                else "unclassified",
            }
        )
        allowed = CRAFT_MODALITIES.get(
            self.technique, TECHNIQUE_MODALITIES.get(self.technique, set())
        )
        if set(self.modalities) - allowed:
            raise ValueError("Craft technique does not support the asserted modality")
        if self.technique == "sound_image_relation" and set(self.modalities) != {"visual", "audio"}:
            raise ValueError("A sound/image interpretation requires both observed modalities")
        values = CRAFT_VALUES.get(self.technique, ())
        if (values and self.value not in values) or (not values and self.value is not None):
            raise ValueError("Craft annotation needs an exact technique-specific value")
        if self.value == "uncertain" and self.verdict != "ambiguous":
            raise ValueError("Uncertain craft interpretations must remain ambiguous")
        return self


class ProductionCoverage(CreativeModel):
    modality: Modality
    techniques: tuple[ProductionTechnique, ...] = Field(min_length=1)
    mode: Literal["exhaustive_review", "sampled", "unknown"]
    intervals: tuple[MediaInterval, ...] = Field(default=(), max_length=100)
    sample_times_ms: tuple[int, ...] = Field(default=(), max_length=1000)
    limitation: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def coherent(self) -> "ProductionCoverage":
        SamplingCoverage.model_validate({**self.model_dump(), "techniques": ["unclassified"]})
        if len(set(self.techniques)) != len(self.techniques):
            raise ValueError("Coverage techniques must be unique")
        for technique in self.techniques:
            modalities = CRAFT_MODALITIES.get(technique, TECHNIQUE_MODALITIES.get(technique, set()))
            if self.modality not in modalities:
                raise ValueError("Coverage modality does not match its technique")
        return self


class ProductionAnnotationSet(CreativeModel):
    schema_version: Literal["2.0"] = "2.0"
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    permission_basis: str = Field(min_length=1, max_length=2000)
    protocol: AnnotationProtocol
    coverage: tuple[ProductionCoverage, ...] = Field(default=(), max_length=40)
    events: tuple[ProductionAnnotation, ...] = Field(default=(), max_length=512)
    tolerance_ms: int = Field(default=100, strict=True, ge=0, le=1000)

    @model_validator(mode="after")
    def coherent(self) -> "ProductionAnnotationSet":
        if len({event.key for event in self.events}) != len(self.events):
            raise ValueError("Event keys must be unique")
        identities = [(c.modality, tuple(sorted(c.techniques))) for c in self.coverage]
        if len(set(identities)) != len(identities):
            raise ValueError("Coverage modality/technique scopes must be unique")
        if self.protocol.origin != "human" and (
            any(c.mode == "exhaustive_review" for c in self.coverage)
            or any(e.state == "reviewed" for e in self.events)
        ):
            raise ValueError(
                "Model/rule proposals cannot certify human review or exhaustive coverage"
            )
        if not self.permission_basis.strip():
            raise ValueError("Permission basis cannot be blank")
        return self


class ProductionDefinition(CreativeModel):
    key: CraftTechnique
    version: Literal["2.0"] = "2.0"
    modalities: tuple[Modality, ...]
    values: tuple[str, ...]
    definition: str
    inclusion: str
    exclusion: str
    required_coverage: str
    procedure: str
    examples: tuple[str, ...]
    counterexamples: tuple[str, ...]


class ProductionRecipe(CreativeModel):
    id: str
    version: Literal["2.0"] = "2.0"
    operation: Literal[
        "shot_mean",
        "shot_median",
        "pacing_change",
        "cuts_per_minute",
        "subtitle_occupancy",
        "cut_beat_rate",
        "angle_changes",
        "close_up_presence",
    ]
    techniques: tuple[ProductionTechnique, ...]
    modalities: tuple[Modality, ...]
    opening_ms: int = 2147483647
    tolerance_ms: int = 100
    unit: Literal["seconds", "ratio", "per_minute", "count", "binary"]
    missingness: Literal["preserve_unknown"] = "preserve_unknown"
    role: Literal["observable_content"] = "observable_content"
    boundary_convention: Literal["half_open_original_ms"] = "half_open_original_ms"
    description: str
