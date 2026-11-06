"""R1 draft registration and citation reports, deliberately without evaluation."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Connection, create_engine, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.pool import StaticPool

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.evidence_service import ClaimValidator, EvidenceResolver
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.research import ResearchRegistration
from socialdna.reporting.research import render_research
from socialdna.storage.backup import assert_recovery_ready
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata


def _spec(path: Path) -> ResearchRegistration:
    try:
        if path.stat().st_size > 1_000_000:
            raise ConfigurationError("Research specification exceeds the 1 MB limit")
        value = ResearchRegistration.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid research specification: {exc}") from exc
    refs = [*value.evidence, *(ref for item in value.hypotheses for ref in item.evidence)]
    if len(refs) > 100:
        raise ConfigurationError("A draft registration supports at most 100 citation references")
    return value


def register_research(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = _spec(path)
    refs = [*spec.evidence, *(ref for item in spec.hypotheses for ref in item.evidence)]
    if dry_run:
        if refs:
            assert_recovery_ready(DataPaths(settings.data_dir))
            database = DataPaths(settings.data_dir).database
            if not database.is_file():
                raise ConfigurationError(
                    "Referenced evidence requires an existing R1 data directory"
                )
            with immutable_snapshot(database) as snapshot:
                engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: snapshot)
                try:
                    with engine.connect() as connection:
                        for ref in refs:
                            EvidenceResolver(connection).resolve(ref, purpose="new_claim")
                finally:
                    engine.dispose()
        return {"valid": True, "written": False, "dry_run": True, "evaluation_ready": False}
    with open_application(settings) as application:
        return register_into_application(application, spec)


def register_into_application(
    application: Application, spec: ResearchRegistration
) -> dict[str, Any]:
    """Use the same draft writer from orchestrators without files or nested writer locks."""
    refs = [*spec.evidence, *(ref for item in spec.hypotheses for ref in item.evidence)]
    if len(refs) > 100:
        raise ConfigurationError("A draft registration supports at most 100 citation references")
    with application.database.transaction() as connection:
        ClaimValidator(connection).validate("hypothesis", tuple(refs), draft=True)
        repository = EvidenceRepository(connection)
        provenance_id = _provenance(
            connection, "research_registration", spec.model_dump(mode="json")
        )
        question_id = stable_id("research-question", spec.key)
        question = repository.save_entity(
            "research_question",
            question_id,
            spec.model_dump(mode="json", exclude={"hypotheses"}),
            provenance_id,
            available_at=utc_now(),
        )
        _link(connection, question, question, spec.evidence)
        hypotheses = []
        for draft in spec.hypotheses:
            hypothesis = repository.save_entity(
                "hypothesis",
                stable_id("hypothesis", question_id, draft.key),
                {**draft.model_dump(mode="json"), "question": question.model_dump()},
                provenance_id,
                available_at=utc_now(),
            )
            _link(connection, hypothesis, question, draft.evidence)
            hypotheses.append(hypothesis.model_dump())
        return {
            "written": True,
            "dry_run": False,
            "question": question.model_dump(),
            "hypotheses": hypotheses,
            "evaluation_ready": False,
            "limitations": ["Draft registration only; no hypothesis has been evaluated."],
        }


def _provenance(connection: Connection, method: str, payload: dict[str, Any]) -> str:
    identity = stable_id(method, hash_config(payload))
    connection.execute(
        insert(metadata.tables["provenance_records"])
        .values(
            id=identity,
            method=method,
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json({"schema_version": "1.0"}),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    return identity


def _link(
    connection: Connection, owner: EntityRef, scope: EntityRef, refs: tuple[EvidenceRef, ...]
) -> None:
    if scope.kind != "research_question":
        raise ConfigurationError("Research evidence requires a question scope")
    for ref in refs:
        EvidenceResolver(connection).resolve(ref, purpose="new_claim")
        connection.execute(
            insert(metadata.tables["evidence_links"])
            .values(
                owner_revision_id=owner.revision_id,
                evidence_revision_id=ref.revision_id,
                scope_revision_id=scope.revision_id,
                role="context",
            )
            .on_conflict_do_nothing()
        )


def show_research(
    application: Application, identity: str, *, revision_id: str | None = None
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        ref: EntityRef | None
        if revision_id:
            row = repository.get("entity_revisions", revision_id)
            if row["entity_id"] != identity:
                raise ConfigurationError("Research identity/revision mismatch")
            ref = repository.ref(row)
        else:
            ref = next(
                (
                    candidate
                    for kind in (
                        "research_question",
                        "hypothesis",
                        "citation_report",
                        "literature_source",
                        "study_finding",
                        "psychological_construct",
                        "operationalization",
                        "research_protocol",
                        "research_assessment",
                        "research_finding",
                        "experiment_brief",
                    )
                    if (candidate := repository.latest(kind, identity))
                ),
                None,
            )
            if ref is None:
                raise ConfigurationError("Unknown research identity")
        from socialdna.storage.research_repository import KINDS

        if ref.kind in KINDS:
            from socialdna.application.investigation_service import show_record
            from socialdna.storage.reevaluation_repository import head

            if ref.kind == "research_assessment" and not revision_id:
                ref = head(connection, ref)
            return show_record(application, ref)
        if ref.kind not in ("research_question", "hypothesis", "citation_report"):
            raise ConfigurationError("Not a registered research entity")
        row = repository.entity(ref)
        payload = json.loads(row["payload_json"])
        if ref.kind == "citation_report":
            payload = _current_report(connection, payload)
            return {"ref": ref.model_dump(), "content": payload, "status": payload["status"]}
        citations = [
            EvidenceResolver(connection)
            .resolve(EvidenceRef.model_validate(item))
            .model_dump(mode="json")
            for item in payload.get("evidence", [])
        ]
        table = metadata.tables["entity_revisions"]
        hypotheses = []
        if ref.kind == "research_question":
            for item in connection.execute(
                select(table)
                .where(
                    table.c.kind == "hypothesis",
                    func.json_extract(table.c.payload_json, "$.question.revision_id")
                    == ref.revision_id,
                )
                .order_by(table.c.entity_id)
            ).mappings():
                hypotheses.append(
                    {
                        "ref": repository.ref(dict(item)).model_dump(),
                        "specification": json.loads(item["payload_json"]),
                    }
                )
            seen = {item["ref"]["revision_id"] for item in citations}
            for hypothesis in hypotheses:
                for raw_ref in hypothesis["specification"]["evidence"]:
                    if raw_ref["revision_id"] not in seen:
                        citations.append(
                            EvidenceResolver(connection)
                            .resolve(EvidenceRef.model_validate(raw_ref))
                            .model_dump(mode="json")
                        )
                        seen.add(raw_ref["revision_id"])
        return {
            "ref": ref.model_dump(),
            "specification": payload,
            "hypotheses": hypotheses,
            "citations": citations,
            "evaluation_ready": False,
            "freshness": "stale" if any(not item["eligible"] for item in citations) else "current",
            "limitations": [
                "Registered draft; statistical and mechanism evaluation are unavailable in R1."
            ],
        }


def _current_report(connection: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    citations = [
        EvidenceResolver(connection)
        .resolve(EvidenceRef.model_validate(item["ref"]))
        .model_dump(mode="json")
        for item in payload["citations"]
    ]
    missing = [item for item in citations if not item["eligible"]]
    audience = []
    behavioral = []
    for item in citations:
        locator = item["locator"]
        if item["eligible"] and locator and locator["kind"] == "behavioral_record":
            ref = EntityRef.model_validate(locator["subject"])
            behavioral.append(
                {
                    "ref": item["ref"],
                    "subject": ref.model_dump(),
                    "data": json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]),
                }
            )
        if item["eligible"] and locator and locator["kind"] == "audience_record":
            ref = EntityRef.model_validate(locator["subject"])
            audience.append(
                {
                    "ref": item["ref"],
                    "subject": ref.model_dump(),
                    "data": json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]),
                }
            )
    return {
        **payload,
        **({"audience_evidence": audience} if audience or "audience_evidence" in payload else {}),
        **(
            {"behavioral_evidence": behavioral}
            if behavioral or "behavioral_evidence" in payload
            else {}
        ),
        "citations": citations,
        "status": "partial" if missing else "success",
        "freshness": "stale" if missing else "current",
        "limitations": [
            *payload["base_limitations"],
            *[
                f"Citation {item['ref']['id']} withheld: {'; '.join(item['limitations'])}"
                for item in missing
            ],
        ],
    }


def generate_research_report(
    application: Application,
    identity: str,
    *,
    report_format: str = "json",
    revision_id: str | None = None,
) -> dict[str, Any]:
    if report_format not in ("json", "markdown"):
        raise ConfigurationError("Research report format must be json or markdown")
    question = show_research(application, identity, revision_id=revision_id)
    if question["ref"]["kind"] == "research_assessment":
        from socialdna.application.investigation_service import assessment_report

        return assessment_report(
            application, EntityRef.model_validate(question["ref"]), report_format
        )
    if question["ref"]["kind"] != "research_question":
        raise ConfigurationError("A citation report requires a research question")
    refs = {item["ref"]["revision_id"]: item["ref"] for item in question["citations"]}
    for hypothesis in question["hypotheses"]:
        for item in hypothesis["specification"]["evidence"]:
            refs[item["revision_id"]] = item
    with application.database.transaction() as connection:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "report_type": "research_registration",
            "question": {"ref": question["ref"], "specification": question["specification"]},
            "hypotheses": question["hypotheses"],
            "evaluation_ready": False,
            "citations": [{"ref": ref} for _, ref in sorted(refs.items())],
            "base_limitations": [
                "Draft hypotheses are not findings; "
                "no statistical or psychological evaluation was performed.",
                "Comment expressions are not verified behavior; "
                "metric values do not establish causation.",
                "Legacy capture does not reconstruct "
                "unknown historical wording or feature availability.",
            ],
        }
        payload = _current_report(connection, payload)
        provenance_id = _provenance(connection, "research_citation_report", payload)
        repository = EvidenceRepository(connection)
        report = repository.save_entity(
            "citation_report",
            stable_id("citation-report", question["ref"]["revision_id"]),
            payload,
            provenance_id,
            available_at=utc_now(),
        )
        for citation in payload["citations"]:
            connection.execute(
                insert(metadata.tables["evidence_links"])
                .values(
                    owner_revision_id=report.revision_id,
                    evidence_revision_id=citation["ref"]["revision_id"],
                    scope_revision_id=question["ref"]["revision_id"],
                    role="context" if citation["eligible"] else "excluded",
                )
                .on_conflict_do_nothing()
            )
        json_content = canonical_json(payload)
        markdown = render_research(payload)
        artifacts = {}
        for name, content in (("json", json_content), ("markdown", markdown)):
            artifact_id = application.artifacts.put_bytes(
                connection,
                content.encode("utf-8"),
                kind="research-report",
                mime_type="application/json" if name == "json" else "text/markdown",
            )
            application.artifacts.add_reference(
                connection,
                artifact_id,
                owner_type="entity_revision",
                owner_id=report.revision_id,
                role=name,
            )
            row = application.artifacts.get(connection, artifact_id)
            artifacts[name] = {
                "id": artifact_id,
                "path": str(application.artifacts.path_for(row["relative_path"])),
            }
    return {
        "ref": report.model_dump(),
        "status": payload["status"],
        "format": report_format,
        "artifact": artifacts[report_format],
        "content": payload if report_format == "json" else markdown,
        "limitations": payload["limitations"],
    }
