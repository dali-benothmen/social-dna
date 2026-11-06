"""Frozen finished-video compositions, not the inaccessible original writing document."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.workflows import ReconstructionOptions, RequiredAction

CueLane = Literal[
    "speech",
    "supplied_subtitle",
    "visible_text",
    "shot",
    "frame",
    "visual_measurement",
    "audio_measurement",
    "reviewed_creative",
]
CueQualification = Literal[
    "supplied_text",
    "model_estimate",
    "measured_proxy",
    "reviewed_annotation",
]


class ReconstructionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class WordTiming(ReconstructionModel):
    text: str
    start_ms: int | None
    end_ms: int | None
    confidence: float | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> "WordTiming":
        if (self.start_ms is None) != (self.end_ms is None) or (
            self.start_ms is not None
            and (self.start_ms < 0 or self.end_ms is None or self.end_ms <= self.start_ms)
        ):
            raise ValueError("Word timing is an original interval or unknown, never invented")
        return self


class TextTrackSnapshot(ReconstructionModel):
    id: str
    producer_task_id: str
    track_type: str
    source: str
    language: str | None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReconstructionCue(ReconstructionModel):
    id: str
    lane: CueLane
    subject: EntityRef
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1)
    producer_task_id: str | None = None
    track_id: str | None = None
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    text: str | None = None
    text_withheld: bool = False
    words: tuple[WordTiming, ...] = ()
    values: dict[str, Any] = Field(default_factory=dict)
    qualification: CueQualification

    @model_validator(mode="after")
    def ordered(self) -> "ReconstructionCue":
        if self.end_ms is not None and (self.start_ms is None or self.end_ms <= self.start_ms):
            raise ValueError("Cue end needs an ordered original interval")
        if self.text_withheld and (self.text is not None or self.words):
            raise ValueError("Withheld source text cannot leak through words")
        return self


class TrackDisagreement(ReconstructionModel):
    left: str
    right: str
    qualification: Literal["overlapping_track_text_differs_not_word_aligned"] = (
        "overlapping_track_text_differs_not_word_aligned"
    )


class VideoReconstruction(ReconstructionModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    canonical_url: str
    post_id: str
    parent_report: EntityRef
    analysis_record: EntityRef
    media: EntityRef
    run_id: str
    goal: str
    request_fulfilled: bool
    status: Literal["success", "partial"]
    coverage: Literal["finished-video-reconstruction-assisted"] = (
        "finished-video-reconstruction-assisted"
    )
    options: ReconstructionOptions
    duration_ms: int = Field(gt=0)
    media_clock: dict[str, Any]
    window_start_ms: int = Field(ge=0)
    window_end_ms: int = Field(gt=0)
    verbatim_permission_basis: str | None
    source_tracks: tuple[TextTrackSnapshot, ...]
    modality_coverage: dict[str, str]
    rows: tuple[ReconstructionCue, ...]
    transcript_row_ids: tuple[str, ...]
    audiovisual_row_ids: tuple[str, ...]
    disagreements: tuple[TrackDisagreement, ...]
    limitations: tuple[str, ...]
    required_actions: tuple[RequiredAction, ...]

    @model_validator(mode="after")
    def consistent(self) -> "VideoReconstruction":
        if not 0 <= self.window_start_ms < self.window_end_ms <= self.duration_ms:
            raise ValueError("Window must lie in the original presentation clock")
        identities = {row.id for row in self.rows}
        if (
            len(identities) != len(self.rows)
            or not set((*self.transcript_row_ids, *self.audiovisual_row_ids)) <= identities
        ):
            raise ValueError("Output rows must be unique actual cues")
        if any(d.left not in identities or d.right not in identities for d in self.disagreements):
            raise ValueError("Track differences need actual selected rows")
        if self.verbatim_permission_basis is None and any(
            row.text is not None or row.words for row in self.rows
        ):
            raise ValueError("Verbatim source text needs an explicit declared permission")
        return self
