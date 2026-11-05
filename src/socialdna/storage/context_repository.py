"""First-use context bindings; SQLite owns snapshots, citations and report inputs."""

import json
from typing import Any

from sqlalchemy import Connection
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import ContextLocator, EntityRef, EvidenceRef
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {
    "publication_context",
    "publishing_window",
    "trend_context",
    "context_report",
    "platform_document",
    "platform_statement",
    "platform_capabilities",
    "distribution_observation",
}


def save(
    connection: Connection,
    kind: str,
    key: str,
    spec: dict[str, Any],
    provenance: str,
    *,
    account: EntityRef,
    post: EntityRef | None = None,
    entities: tuple[EntityRef, ...] = (),
    evidence: tuple[EvidenceRef, ...] = (),
    result: dict[str, Any] | None = None,
) -> EntityRef:
    repo = EvidenceRepository(connection)
    if kind not in KINDS or account.kind != "account":
        raise ConfigurationError("Unsupported context kind or account scope")
    repo.entity(account)
    if post:
        captured = json.loads(repo.entity(post)["payload_json"])
        if post.kind != "post" or captured["account_id"] != account.id:
            raise ConfigurationError("Context post belongs to a different account")
    capture = spec.get("captured_at") or spec.get("clock", {}).get("captured_at") or utc_now()
    if capture > utc_now():
        raise ConfigurationError("Context capture cannot be in the future")
    payload = {
        "spec": spec,
        "account": account.model_dump(),
        "post": post.model_dump() if post else None,
        "entity_inputs": [r.model_dump() for r in (account, *((post,) if post else ()), *entities)],
        "evidence_inputs": [r.model_dump() for r in evidence],
        "result": result,
    }
    identity = stable_id("context", kind, account.id, post.id if post else "", key)
    previous = repo.latest(kind, identity)
    if previous and json.loads(repo.entity(previous)["payload_json"]) == payload:
        return previous
    ref = repo.save_entity(
        kind,
        identity,
        payload,
        provenance,
        available_at=utc_now(),
    )
    connection.execute(
        insert(metadata.tables["context_records"])
        .values(
            revision_id=ref.revision_id,
            account_revision_id=account.revision_id,
            post_revision_id=post.revision_id if post else None,
            captured_at=capture,
        )
        .on_conflict_do_nothing()
    )
    return ref


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    row = repo.get("context_records", ref.revision_id, "revision_id")
    account = repo.get("entity_revisions", row["account_revision_id"])
    if account["kind"] != "account" or account["entity_id"] != payload["account"]["id"]:
        raise StorageIntegrityError("Context account binding has the wrong kind or identity")
    if row["post_revision_id"]:
        post = repo.get("entity_revisions", row["post_revision_id"])
        if (
            post["kind"] != "post"
            or json.loads(post["payload_json"])["account_id"] != account["entity_id"]
        ):
            raise StorageIntegrityError("Context post binding has wrong ownership")
    if row["account_revision_id"] != payload["account"]["revision_id"] or (
        row["post_revision_id"] != (payload["post"]["revision_id"] if payload["post"] else None)
    ):
        raise StorageIntegrityError("Context ownership projection mismatch")
    capture = payload["spec"].get("captured_at") or payload["spec"].get("clock", {}).get(
        "captured_at"
    )
    if capture and row["captured_at"] != capture:
        raise StorageIntegrityError("Context capture projection mismatch")


def field_value(payload: dict[str, Any], field: str) -> str:
    # Exact bounded pointer into a typed producer's spec, never an executable path.
    value: Any = payload["spec"]
    for part in field.split("/"):
        if isinstance(value, list) and part.isdecimal():
            index = int(part)
            if index >= len(value):
                raise ConfigurationError("Unknown context field ordinal")
            value = value[index]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ConfigurationError("Unknown context field")
    if not isinstance(value, str):
        raise ConfigurationError("Text citations require an actual captured string field")
    return value


def validate_locator(repo: EvidenceRepository, locator: ContextLocator) -> None:
    payload = json.loads(repo.entity(locator.subject)["payload_json"])
    if locator.subject.kind not in KINDS:
        raise StorageIntegrityError("Context locator has a wrong-kind subject")
    if locator.quote is not None:
        if locator.field is None or locator.start_char is None or locator.end_char is None:
            raise ConfigurationError("Exact context text requires field, start, end and quote")
        text = field_value(payload, locator.field)
        if not 0 <= locator.start_char < locator.end_char <= len(text) or (
            text[locator.start_char : locator.end_char] != locator.quote
        ):
            raise ConfigurationError("Context text must match its Unicode code-point span")
    elif (
        locator.start_char is not None or locator.end_char is not None or locator.field is not None
    ):
        raise ConfigurationError("Partial context text locators are not allowed")
    if locator.artifact_id:
        thumbnails = payload["spec"].get("thumbnails", [])
        if not any(t["artifact_id"] == locator.artifact_id for t in thumbnails):
            raise ConfigurationError("Artifact does not belong to this context variant")
        asset = repo.get("artifact_objects", locator.artifact_id)
        if not any(
            t["artifact_id"] == asset["id"] and t["sha256"] == asset["sha256"] for t in thumbnails
        ):
            raise StorageIntegrityError("Context asset hash binding mismatch")


def cite(
    connection: Connection,
    ref: EntityRef,
    *,
    field: str | None = None,
    start: int | None = None,
    end: int | None = None,
    artifact_id: str | None = None,
) -> EvidenceRef:
    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    text = field_value(json.loads(row["payload_json"]), field) if field else None
    locator = ContextLocator(
        subject=ref,
        field=field,
        start_char=start,
        end_char=end,
        quote=text[start:end]
        if text is not None and start is not None and end is not None
        else None,
        artifact_id=artifact_id,
    )
    validate_locator(repo, locator)
    result = repo.save_evidence(
        stable_id("context-evidence", hash_config(locator.model_dump())),
        locator,
        row["provenance_id"],
        available_at=row["available_at"],
    )
    connection.execute(
        insert(metadata.tables["context_evidence_bindings"])
        .values(
            evidence_revision_id=result.revision_id,
            subject_revision_id=ref.revision_id,
        )
        .on_conflict_do_nothing()
    )
    return result


def read(connection: Connection, ref: EntityRef, as_of: str | None = None) -> dict[str, Any]:
    from socialdna.application.evidence_service import EvidenceResolver

    EvidenceResolver(connection).resolve(cite(connection, ref), purpose="new_claim", as_of=as_of)
    return dict(json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]))
