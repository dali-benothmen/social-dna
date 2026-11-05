"""Typed binding validation for actual canonical search/pattern producers."""

import json

from socialdna.core.exceptions import StorageIntegrityError
from socialdna.domain.evidence import EntityRef
from socialdna.storage.evidence_repository import EvidenceRepository


def validate_projection(repository: EvidenceRepository, ref: EntityRef) -> None:
    binding = repository.get("discovery_bindings", ref.revision_id, "revision_id")
    row = repository.get("discovery_rounds", binding["round_id"])
    # Read the immutable payload directly: invoking entity() here would recurse.
    payload = json.loads(repository.get("entity_revisions", ref.revision_id)["payload_json"])
    role = binding["role"]
    if ref.kind == "creative_pattern":
        valid = role == "pattern" and payload["search"]["revision_id"] == row["result_revision_id"]
    elif role == "registration":
        valid = (
            row["registration_revision_id"] == ref.revision_id
            and payload["spec"]["key"] == row["id"]
        )
    else:
        valid = (
            role == "result"
            and row["result_revision_id"] == ref.revision_id
            and payload["registration"]["revision_id"] == row["registration_revision_id"]
        )
    if not valid:
        raise StorageIntegrityError("Discovery projection/role does not match the canonical record")
