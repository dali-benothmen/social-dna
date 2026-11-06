"""Assisted content reports never assert verified publisher ownership."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from socialdna.domain.evidence import EntityRef
from socialdna.domain.workflows import RequiredAction


class ContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    position: int
    kind: Literal["image", "video", "carousel"]
    run_id: str
    report: dict[str, Any]
    markdown: str


class ContentReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    canonical_url: str
    post_id: str
    binding: EntityRef
    goal: str
    request_fulfilled: bool
    coverage: Literal["media-enriched-assisted"] = "media-enriched-assisted"
    status: Literal["success", "partial"]
    analyses: tuple[ContentItem, ...]
    limitations: tuple[str, ...]
    required_actions: tuple[RequiredAction, ...] = ()
