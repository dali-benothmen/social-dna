"""Versioned host-neutral availability, not a claim of scientific validity."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CapabilityState = Literal["available", "unavailable", "planned", "optional_prepared"]


class CapabilityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: CapabilityState
    reason: str
    commands: list[list[str]] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    engine_version: str
    scope: Literal["interface_and_local_preflight"] = "interface_and_local_preflight"
    capabilities: list[CapabilityEntry]
    policy: dict[str, bool]
    resource_limits: dict[str, int | float]
    limitations: list[str]
