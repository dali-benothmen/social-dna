from uuid import UUID

from pydantic import BaseModel, ConfigDict

from socialdna.core.time import MediaInterval


class EvidenceReference(BaseModel):
    """Citation identity; actual evidence persistence arrives with the timeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: UUID
    interval: MediaInterval | None = None
