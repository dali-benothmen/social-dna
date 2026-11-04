from pydantic import BaseModel, ConfigDict

from socialdna.core.enums import ClaimLevel
from socialdna.domain.evidence import EvidenceReference


class ClaimReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_level: ClaimLevel
    evidence: tuple[EvidenceReference, ...]
