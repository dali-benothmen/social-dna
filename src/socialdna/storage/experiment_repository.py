"""Canonical experiment typed projections, reads and idempotent immutable saves."""

import json
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.domain.evidence import EntityRef
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {
    "experiment_registration",
    "experiment_results",
    "experiment_analysis",
    "experiment_assessment",
}
TABLES = {
    "experiment_registration": "experiment_registrations",
    "experiment_results": "experiment_results",
    "experiment_analysis": "experiment_analyses",
    "experiment_assessment": "experiment_assessments",
}


def put(connection: Connection, table: str, **values: Any) -> None:
    connection.execute(insert(metadata.tables[table]).values(**values).on_conflict_do_nothing())


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    projection = repo.get(TABLES[ref.kind], ref.revision_id, "revision_id")
    if ref.kind == "experiment_registration":
        if (
            projection["protocol_hash"] != hash_config(payload["spec"])
            or projection["registered_at"] != payload["registered_at"]
        ):
            raise StorageIntegrityError("Experiment registration projection mismatch")
        return
    if (
        projection.get("registration_revision_id")
        and projection["registration_revision_id"] != payload["registration"]["revision_id"]
    ):
        raise StorageIntegrityError("Experiment registration binding mismatch")
    if ref.kind == "experiment_results":
        table = metadata.tables["experiment_measurement_bindings"]
        actual = {
            (
                r["unit_key_hash"],
                r["outcome_key_hash"],
                r["subject_revision_id"],
                r["measurement_revision_id"],
            )
            for r in repo.connection.execute(
                select(table).where(table.c.results_revision_id == ref.revision_id)
            ).mappings()
        }
        expected = {
            (
                hash_config({"key": u["unit_key"]}),
                hash_config({"key": key}),
                u["subject"]["revision_id"],
                value["revision_id"],
            )
            for u in payload["spec"]["units"]
            for key, value in u["outcomes"].items()
        }
        if expected != actual:
            raise StorageIntegrityError("Experiment measured-unit bindings mismatch")
    elif ref.kind == "experiment_analysis":
        if (
            projection["results_revision_id"] != payload["results"]["revision_id"]
            or projection["attempt_id"] != payload["attempt_id"]
        ):
            raise StorageIntegrityError("Experiment analysis binding mismatch")
    elif ref.kind == "experiment_assessment":
        bindings = metadata.tables["experiment_hypotheses"]
        actual_hypotheses: set[str] = set(
            repo.connection.scalars(
                select(bindings.c.hypothesis_revision_id).where(
                    bindings.c.assessment_revision_id == ref.revision_id
                )
            )
        )
        if actual_hypotheses != {j["hypothesis"]["revision_id"] for j in payload["judgments"]}:
            raise StorageIntegrityError("Experiment hypothesis bindings mismatch")
        if any(
            projection[key] != payload[field]["revision_id"]
            for key, field in (
                ("analysis_revision_id", "analysis"),
                ("prior_revision_id", "prior"),
                ("question_revision_id", "question"),
            )
        ):
            raise StorageIntegrityError("Experiment assessment lineage mismatch")


def content(connection: Connection, ref: EntityRef) -> dict[str, Any]:
    from socialdna.application.evidence_service import EvidenceResolver
    from socialdna.storage.research_repository import cite

    EvidenceResolver(connection).resolve(cite(connection, ref), purpose="new_claim")
    return dict(json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]))
