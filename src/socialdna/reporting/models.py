from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VideoReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    report_type: Literal["video"] = "video"
    run_id: str
    media_id: str
    status: Literal["success", "partial"]
    title: str
    metadata: dict[str, Any]
    analysis_configuration: dict[str, Any]
    feature_definitions: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    timeline: dict[str, Any]
    limitations: list[str] = Field(default_factory=list)
    interpretation: str = (
        "Signal measurements and explicitly labeled model estimates/hypotheses; "
        "no verified psychological or performance claims."
    )
