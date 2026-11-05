"""Immutable source-counter meanings; no fake profile/link/post metric subjects."""

from typing import Any

from sqlalchemy import Connection
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.domain.evidence import EntityRef
from socialdna.domain.profile import FunnelBinding
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def bind_events(
    connection: Connection, ref: EntityRef, bindings: tuple[FunnelBinding, ...]
) -> None:
    table = metadata.tables["funnel_event_bindings"]
    repo = EvidenceRepository(connection)
    for binding in bindings:
        expected = {
            "signal": binding.signal,
            "uniqueness": binding.uniqueness,
            "event_code_hash": hash_config(binding.source_event_code),
        }
        connection.execute(
            insert(table)
            .values(
                definition_revision_id=binding.definition.revision_id,
                context_revision_id=ref.revision_id,
                **expected,
            )
            .on_conflict_do_nothing()
        )
        row = repo.get(
            "funnel_event_bindings", binding.definition.revision_id, "definition_revision_id"
        )
        if any(row[key] != value for key, value in expected.items()):
            raise ConfigurationError(
                "A captured source counter cannot be relabeled or change uniqueness; "
                "supply a genuinely new source definition"
            )


def validate_bindings(repo: EvidenceRepository, payload: dict[str, Any]) -> None:
    for binding in payload["spec"]["bindings"]:
        row = repo.get(
            "funnel_event_bindings", binding["definition"]["revision_id"], "definition_revision_id"
        )
        if (
            row["signal"] != binding["signal"]
            or row["uniqueness"] != binding["uniqueness"]
            or row["event_code_hash"] != hash_config(binding["source_event_code"])
        ):
            raise StorageIntegrityError("Funnel source-event projection mismatch")
