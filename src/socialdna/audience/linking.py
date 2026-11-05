import re
from typing import Literal

from pydantic import Field, model_validator

from socialdna.audience.collections import AudienceModel
from socialdna.domain.evidence import EntityRef, EvidenceRef


class LinkAlternative(AudienceModel):
    target: EntityRef
    reason: str = Field(min_length=1, max_length=1000)


class ContentLink(AudienceModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    reaction_key: str
    target: EntityRef
    target_evidence: EvidenceRef | None = None
    origin: Literal["explicit_reference", "human_interpretation", "model_proposal"]
    reference_kind: Literal["timestamp", "quote"] | None = None
    reference_text: str | None = Field(default=None, min_length=1, max_length=2000)
    target_quote_evidence: EvidenceRef | None = None
    description: str = Field(min_length=1, max_length=2000)
    uncertainty: Literal["low", "medium", "high", "unknown"] = "unknown"
    alternatives: tuple[LinkAlternative, ...] = Field(default=(), max_length=10)
    state: Literal["proposed", "reviewed", "disputed"] = "proposed"
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def qualified(self) -> "ContentLink":
        if self.target.kind not in ("post", "creative_event"):
            raise ValueError("Audience links target exact post or creative-event revisions")
        if self.target.kind == "creative_event" and self.target_evidence is None:
            raise ValueError("An event target requires its exact creative evidence")
        if self.state == "reviewed" and not self.reviewer:
            raise ValueError("Reviewed links require a reviewer")
        if self.origin == "explicit_reference":
            if not self.reference_kind or not self.reference_text:
                raise ValueError("Explicit links need literal source reference text")
            if self.reference_kind == "timestamp":
                parse_reference_time(self.reference_text)
            elif self.target_quote_evidence is None:
                raise ValueError("An explicit quote needs literal target-text evidence")
        elif (
            self.reference_kind is not None
            or self.reference_text is not None
            or self.target_quote_evidence is not None
        ):
            raise ValueError("Inferred links cannot acquire fabricated explicit reference anchors")
        if self.origin == "model_proposal" and self.state != "proposed":
            raise ValueError("Model links cannot self-adjudicate")
        return self


def parse_reference_time(text: str) -> int:
    match = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?", text)
    if not match:
        raise ValueError("Use a literal mm:ss or hh:mm:ss reference, not publication time")
    hours, minutes, seconds, fraction = match.groups()
    if int(seconds) >= 60 or (hours is not None and int(minutes) >= 60):
        raise ValueError("Invalid playback reference")
    return (int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(
        (fraction or "").ljust(3, "0")
    )
