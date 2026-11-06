"""Bounded source-only workflows; task names are not Python dispatch expressions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.media import AnalysisOptions

TASK_NAMES = (
    "research",
    "ingest",
    "account",
    "analyze",
    "reconstruct",
    "psychology",
    "audience",
    "compare",
    "discover",
    "platform",
    "strategy",
    "experiment",
    "report",
    "evidence",
)
IMPLEMENTED_TASKS = ("ingest", "report", "analyze", "reconstruct")


class ReconstructionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    output: Literal["transcript", "audiovisual-script", "combined"] = "combined"
    track_ids: tuple[str, ...] = Field(default=(), max_length=100)
    start_ms: int = Field(default=0, strict=True, ge=0)
    end_ms: int | None = Field(default=None, strict=True, gt=0)
    allow_verbatim: bool = False
    creative_revision: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def valid_selection(self) -> "ReconstructionOptions":
        if self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("Reconstruction end must be after start")
        if len(set(self.track_ids)) != len(self.track_ids):
            raise ValueError("Select each track once")
        return self


class MediaInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: Literal["image", "video"]


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    mode: Literal["ingest", "report", "analyze", "reconstruct"] = "ingest"
    url: str | None = Field(default=None, max_length=2048)
    from_workflow: str | None = Field(default=None, min_length=1, max_length=36)
    goal: str = Field(
        default="Capture the source's native public metadata.", min_length=1, max_length=2000
    )
    question_scope: Literal["native_metadata", "content_measurements", "unassessed"] = "unassessed"
    max_attempts: int = Field(default=3, ge=1, le=3, strict=True)
    scope: Literal["content", "profile"] = "content"
    profile_revision: str | None = Field(default=None, min_length=1, max_length=36)
    audit_focus: Literal["balanced", "strengths", "improvements"] = "balanced"
    media: tuple[str, ...] = Field(default=(), max_length=20)
    permission_basis: Literal["creator_owned_original", "authorized_analysis"] | None = None
    copy_media: bool = False
    replace_media: bool = False
    subtitles: str | None = None
    analysis_options: AnalysisOptions = Field(default_factory=lambda: AnalysisOptions(no_ai=True))
    reconstruction: ReconstructionOptions = Field(default_factory=ReconstructionOptions)

    @model_validator(mode="after")
    def appropriate_input(self) -> "WorkflowRequest":
        if self.profile_revision and (self.mode != "analyze" or self.scope != "profile"):
            raise ValueError("Profile revisions require analyze profile scope")
        if (
            self.scope == "profile"
            and self.mode == "analyze"
            and (self.media or self.permission_basis or self.subtitles)
        ):
            raise ValueError("Profile inputs belong to an actual observed snapshot, not post media")
        if self.audit_focus != "balanced" and (self.mode != "analyze" or self.scope != "profile"):
            raise ValueError("Audit focus applies only to profile scope")
        if self.mode in ("ingest", "analyze") and (not self.url or self.from_workflow):
            raise ValueError("Ingest requires one URL and no saved-workflow reference")
        if self.mode == "report" and (not self.from_workflow or self.url):
            raise ValueError("Report requires --from and never fetches a supplied URL")
        if self.mode == "reconstruct" and bool(self.url) == bool(self.from_workflow):
            raise ValueError("Reconstruct requires either --url or --from, not both")
        if not self.goal.strip():
            raise ValueError("A goal must contain text")
        if self.mode not in ("analyze", "reconstruct") and (
            self.media or self.permission_basis or self.subtitles
        ):
            raise ValueError("Only content analysis accepts supplied media")
        if (
            self.mode == "reconstruct"
            and self.from_workflow
            and (self.media or self.permission_basis or self.subtitles)
        ):
            raise ValueError("Saved reconstruction selects existing tracks, not replacement media")
        if self.mode != "reconstruct" and self.reconstruction != ReconstructionOptions():
            raise ValueError("Reconstruction options apply only to reconstruct mode")
        if self.media and self.permission_basis is None:
            raise ValueError("Declare permission for supplied originals")
        if self.analysis_options.reason or self.analysis_options.creative_profile:
            raise ValueError("Remote reasoning/creative annotation is not a workflow operation")
        return self


class WorkflowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request: WorkflowRequest
    platform: Literal["youtube", "instagram", "tiktok"]
    target_kind: Literal["post", "account"]
    canonical_url: str
    external_id: str
    operations: tuple[str, ...]
    supported: bool
    policy_version: str
    response_byte_limit: int = Field(gt=0)
    request_timeout_seconds: float = Field(gt=0, le=60, allow_inf_nan=False)
    retention_days: int | None = Field(ge=1, le=29)
    limitations: tuple[str, ...]
    media_inputs: tuple[MediaInput, ...] = ()
    subtitles_sha256: str | None = None
    parent_report: EntityRef | None = None


class RequiredAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    message: str


class NativeField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    value: str | None
    availability: Literal["available", "not_returned"]
    evidence: EvidenceRef


class WorkflowReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    capture_id: str
    canonical_url: str
    platform: Literal["youtube"] = "youtube"
    coverage: Literal["source-only"] = "source-only"
    captured_at: str
    expires_at: str
    goal: str
    request_fulfilled: bool
    fields: tuple[NativeField, ...]
    source: dict[str, str]
    limitations: tuple[str, ...]
    required_actions: tuple[RequiredAction, ...] = ()
