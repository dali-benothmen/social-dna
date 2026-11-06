"""Bounded source-only workflows; task names are not Python dispatch expressions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialdna.domain.evidence import EvidenceRef
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
IMPLEMENTED_TASKS = ("ingest", "report", "analyze")


class MediaInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: Literal["image", "video"]


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    mode: Literal["ingest", "report", "analyze"] = "ingest"
    url: str | None = Field(default=None, max_length=2048)
    from_workflow: str | None = Field(default=None, min_length=1, max_length=36)
    goal: str = Field(
        default="Capture the source's native public metadata.", min_length=1, max_length=2000
    )
    question_scope: Literal["native_metadata", "content_measurements", "unassessed"] = "unassessed"
    max_attempts: int = Field(default=3, ge=1, le=3, strict=True)
    scope: Literal["content", "profile"] = "content"
    media: tuple[str, ...] = Field(default=(), max_length=20)
    permission_basis: Literal["creator_owned_original", "authorized_analysis"] | None = None
    copy_media: bool = False
    replace_media: bool = False
    subtitles: str | None = None
    analysis_options: AnalysisOptions = Field(default_factory=lambda: AnalysisOptions(no_ai=True))

    @model_validator(mode="after")
    def appropriate_input(self) -> "WorkflowRequest":
        if self.mode in ("ingest", "analyze") and (not self.url or self.from_workflow):
            raise ValueError("Ingest requires one URL and no saved-workflow reference")
        if self.mode == "report" and (not self.from_workflow or self.url):
            raise ValueError("Report requires --from and never fetches a supplied URL")
        if not self.goal.strip():
            raise ValueError("A goal must contain text")
        if self.mode != "analyze" and (self.media or self.permission_basis or self.subtitles):
            raise ValueError("Only content analysis accepts supplied media")
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
