"""A pinned library study is neither a complete platform crawl nor certified research."""

from typing import Any, Literal

from pydantic import Field

from socialdna.domain.context import ContextModel
from socialdna.domain.evidence import EntityRef, EvidenceRef


class AccountStudyPost(ContextModel):
    post: EntityRef
    published_at: str | None
    fields: dict[str, str | None]
    evidence: EvidenceRef
    status: Literal["inspected", "media_analyzed", "media_reused", "failed", "unavailable"]
    media_report: EntityRef | None = None
    reason: str | None = None


class AccountStudy(ContextModel):
    schema_version: Literal["1.0"] = "1.0"
    workflow_id: str
    canonical_url: str
    goal: str
    mode: Literal["account", "research"]
    account: EntityRef
    manifest: EntityRef
    selection: Literal["recent_library_posts_not_ranked_by_outcome"] = (
        "recent_library_posts_not_ranked_by_outcome"
    )
    known_posts_count: int = Field(ge=0)
    selected_posts_count: int = Field(ge=0)
    omitted_by_limit: int = Field(ge=0)
    platform_inventory_complete: Literal[False] = False
    posts: tuple[AccountStudyPost, ...]
    contexts: tuple[dict[str, Any], ...] = ()
    changes: dict[str, Any]
    research_question: EntityRef | None = None
    research_state: Literal["not_requested", "draft"]
    coverage: Literal["account-library-assisted"] = "account-library-assisted"
    status: Literal["partial"] = "partial"
    request_fulfilled: Literal[False] = False
    limitations: tuple[str, ...]
    required_actions: tuple[dict[str, str], ...]
