"""Typed content compositions and frozen artifacts over existing evidence and runs."""

import json
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.content import ContentReport
from socialdna.domain.evidence import ContentLocator, EntityRef, EvidenceRef
from socialdna.domain.reconstruction import VideoReconstruction
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {"content_binding", "content_run", "content_report", "video_reconstruction"}


def save(
    connection: Connection,
    kind: str,
    workflow: str,
    key: str,
    payload: dict[str, Any],
    provenance: str,
) -> EntityRef:
    if kind not in KINDS:
        raise ConfigurationError("Unsupported content record kind")
    ref = EvidenceRepository(connection).save_entity(
        kind, stable_id(kind, workflow, key), payload, provenance, available_at=utc_now()
    )
    connection.execute(
        insert(metadata.tables["content_records"])
        .values(revision_id=ref.revision_id, workflow_id=workflow, run_id=payload.get("run_id"))
        .on_conflict_do_nothing()
    )
    return ref


def cite(connection: Connection, ref: EntityRef) -> EvidenceRef:
    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    evidence = repo.save_evidence(
        stable_id("content-citation", ref.revision_id),
        ContentLocator(subject=ref),
        row["provenance_id"],
        available_at=row["available_at"],
    )
    connection.execute(
        insert(metadata.tables["content_evidence_bindings"])
        .values(evidence_revision_id=evidence.revision_id, subject_revision_id=ref.revision_id)
        .on_conflict_do_nothing()
    )
    return evidence


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    row = repo.get("content_records", ref.revision_id, "revision_id")
    if row["workflow_id"] != payload["workflow_id"] or row["run_id"] != payload.get("run_id"):
        raise StorageIntegrityError("Content projection mismatch")
    if ref.kind == "content_report":
        ContentReport.model_validate(payload["result"])
    if ref.kind == "video_reconstruction":
        result = VideoReconstruction.model_validate(payload["result"])
        if result.run_id != row["run_id"] or result.media.id != payload["target_id"]:
            raise StorageIntegrityError("Reconstruction projection disagrees with its actual run")
    if row["run_id"]:
        run = repo.get("analysis_runs", row["run_id"])
        if run["target_id"] != payload["target_id"]:
            raise StorageIntegrityError("Content run targets different media/post")


def records(connection: Connection, workflow: str, kind: str) -> list[EntityRef]:
    rows, entities = metadata.tables["content_records"], metadata.tables["entity_revisions"]
    repo = EvidenceRepository(connection)
    return [
        repo.ref(dict(row))
        for row in connection.execute(
            select(entities)
            .join(rows, rows.c.revision_id == entities.c.id)
            .where(rows.c.workflow_id == workflow, entities.c.kind == kind)
            .order_by(entities.c.recorded_at, entities.c.id)
        ).mappings()
    ]


def active(connection: Connection, ref: EntityRef) -> dict[str, Any]:
    EvidenceResolver(connection).resolve(cite(connection, ref), purpose="new_claim")
    result: dict[str, Any] = json.loads(EvidenceRepository(connection).entity(ref)["payload_json"])
    return result


def freeze(
    app: Application,
    connection: Connection,
    ref: EntityRef,
    document: dict[str, Any],
    markdown: str,
) -> None:
    for role, text, mime in (
        ("json", canonical_json(document), "application/json"),
        ("markdown", markdown, "text/markdown"),
    ):
        artifact = app.artifacts.put_bytes(
            connection, text.encode(), kind="content-report", mime_type=mime
        )
        app.artifacts.add_reference(
            connection, artifact, owner_type="entity_revision", owner_id=ref.revision_id, role=role
        )


def load(app: Application, ref: EntityRef, report_format: str) -> dict[str, Any]:
    if report_format not in ("json", "markdown"):
        raise ConfigurationError("Report format must be json or markdown")
    with app.database.transaction() as connection:
        payload = active(connection, ref)
        refs = metadata.tables["artifact_references"]
        identity = connection.scalar(
            select(refs.c.artifact_id).where(
                refs.c.owner_id == ref.revision_id, refs.c.role == report_format
            )
        )
        if not identity:
            raise StorageIntegrityError("Frozen content artifact is missing")
        asset = app.artifacts.get(connection, identity)
        if not app.artifacts.verify(asset):
            raise StorageIntegrityError("Frozen content artifact failed verification")
        text = app.artifacts.path_for(asset["relative_path"]).read_text(encoding="utf-8")
        document = json.loads(text) if report_format == "json" else text
        if report_format == "json" and document != payload["result"]:
            raise StorageIntegrityError("Frozen content report differs from its producer")
    return {
        "workflow_id": payload["workflow_id"],
        "status": payload["result"]["status"],
        "coverage": payload["result"]["coverage"],
        "format": report_format,
        "content": document,
        "report": ref.model_dump(),
        "network_attempted": False,
        "limitations": payload["result"]["limitations"],
        "required_actions": payload["result"].get("required_actions", []),
    }
