from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str


class ResultEnvelope(BaseModel):
    """Versioned, stdout-safe result contract shared by every engine command."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    command: str
    status: Literal["success", "partial", "error"] = "success"
    run_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[Issue] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    errors: list[Issue] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: Literal["ok", "warning", "error", "deferred"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
