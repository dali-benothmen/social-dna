"""Compose frozen, cited native reports without network requests or model inference."""

import json
from typing import Any

from sqlalchemy import select

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json
from socialdna.domain.workflows import NativeField, RequiredAction, WorkflowReport
from socialdna.ingestion.connectors.youtube import ENDPOINT
from socialdna.reporting.workflow import render
from socialdna.storage import context_repository as context
from socialdna.storage import workflow_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

LIMITATIONS = (
    "One specified post; no account enumeration, audiovisual media, captions or comments acquired.",
    "Only native fields returned by the official API are reported; "
    "omitted fields are unknown, not zero.",
    "Capture time is retrieval time. The API did not supply a "
    "measurement timestamp/window for these counts.",
    "No private retention, saves, impressions, traffic attribution, "
    "follower conversion or app installs were accessed.",
    "No derived scores/rates, cross-creator aggregation, psychological "
    "explanation or content-quality judgment was computed.",
    "Source use is limited to native inspection/reporting; "
    "generic analytics and semantic indexing are blocked.",
    "Source expiry/withdrawal can withhold this report. "
    "A later refresh is new explicit evidence, not a retry.",
)


def generate(
    application: Application, identity: str, report_format: str = "json"
) -> dict[str, Any]:
    if report_format not in {"json", "markdown"}:
        raise ConfigurationError("Workflow report format must be json or markdown")
    content_ref = None
    with application.database.transaction() as connection:
        _, workflow_plan = repository.get(connection, identity)
        for item in repository.bindings(connection, identity):
            if item["role"] == "report":
                repo = EvidenceRepository(connection)
                ref = repo.ref(repo.get("entity_revisions", item["revision_id"]))
                if ref.kind == "video_reconstruction":
                    content_ref = ref
                    break
                if ref.kind == "content_report":
                    content_ref = ref
    if workflow_plan.request.mode == "reconstruct" and (
        content_ref is None or content_ref.kind != "video_reconstruction"
    ):
        raise ConfigurationError("No frozen reconstruction script yet; run/resume this workflow")
    if content_ref:
        from socialdna.storage.content_repository import load

        return {**load(application, content_ref, report_format), "workflow_id": identity}
    with application.database.transaction() as connection:
        _, plan = repository.get(connection, identity)
        bound = repository.bindings(connection, identity)
        capture_binding = next((item for item in bound if item["role"] == "capture"), None)
        if capture_binding is None:
            raise ConfigurationError("This workflow has no committed source capture; run it first")
        capture_id = capture_binding["capture_id"]
        ref, manifest = repository.load_capture(connection, capture_id)
        evidence_repo = EvidenceRepository(connection)
        subject = json.loads(evidence_repo.entity(ref)["payload_json"])
        if saved := next((item for item in bound if item["role"] == "report"), None):
            report_ref = evidence_repo.ref(
                evidence_repo.get("entity_revisions", saved["revision_id"])
            )
            EvidenceResolver(connection).resolve(
                context.cite(connection, report_ref), purpose="native_report"
            )
            document = json.loads(evidence_repo.entity(report_ref)["payload_json"])["result"]
            report = WorkflowReport.model_validate(document)
        else:
            fields = []
            for path, value in manifest.fields.items():
                pointer = "manifest/fields/" + path.replace("~", "~0").replace("/", "~1")
                citation = (
                    context.cite(connection, ref, field=pointer, start=0, end=len(value))
                    if value
                    else context.cite(connection, ref)
                )
                EvidenceResolver(connection).resolve(citation, purpose="native_report")
                fields.append(
                    NativeField(
                        path=path,
                        value=value,
                        availability="available" if value is not None else "not_returned",
                        evidence=citation,
                    )
                )
            fulfilled = plan.request.question_scope == "native_metadata" or (
                plan.request.goal == "Capture the source's native public metadata."
            )
            report = WorkflowReport(
                workflow_id=identity,
                capture_id=capture_id,
                canonical_url=manifest.source_url,
                captured_at=manifest.captured_at,
                expires_at=manifest.expires_at,
                goal=plan.request.goal,
                request_fulfilled=fulfilled,
                fields=tuple(fields),
                source={
                    "provider": manifest.provider,
                    "endpoint": ENDPOINT,
                    "policy_version": manifest.policy_version,
                    "permission_basis": "public_permitted",
                },
                limitations=LIMITATIONS,
                required_actions=()
                if fulfilled
                else (
                    RequiredAction(
                        code="additional_evidence_required",
                        message="This capture supports native metadata only. Supply independently "
                        "authorized original media or analytics exports for the existing local "
                        "analysis workflows; automatic URL media/research tasks are not shipped.",
                    ),
                ),
            )
            from socialdna.domain.evidence import EntityRef

            account = EntityRef.model_validate(subject["account"])
            post = EntityRef.model_validate(subject["post"])
            report_ref = context.save(
                connection,
                "workflow_report",
                identity,
                {"clock": {"captured_at": manifest.captured_at}, "workflow_id": identity},
                evidence_repo.entity(ref)["provenance_id"],
                account=account,
                post=post,
                entities=(ref,),
                evidence=tuple(field.evidence for field in fields),
                result=report.model_dump(mode="json"),
            )
            repository.bind(connection, identity, "report", report_ref, capture_id)
            for name, content, mime in (
                ("json", canonical_json(report.model_dump(mode="json")), "application/json"),
                ("markdown", render(report), "text/markdown"),
            ):
                artifact = application.artifacts.put_bytes(
                    connection, content.encode(), kind="workflow-report-" + name, mime_type=mime
                )
                application.artifacts.add_reference(
                    connection,
                    artifact,
                    owner_type="entity_revision",
                    owner_id=report_ref.revision_id,
                    role=name,
                )
            context.cite(connection, report_ref)
        references = metadata.tables["artifact_references"]
        artifact_id = connection.scalar(
            select(references.c.artifact_id).where(
                references.c.owner_id == report_ref.revision_id,
                references.c.role == report_format,
            )
        )
        if not artifact_id:
            raise StorageIntegrityError("The frozen workflow report artifact is missing")
        asset_row = application.artifacts.get(connection, artifact_id)
        if not application.artifacts.verify(asset_row):
            raise StorageIntegrityError(
                "The frozen workflow report artifact failed integrity verification"
            )
        artifact_path = application.artifacts.path_for(asset_row["relative_path"])
        text = artifact_path.read_text(encoding="utf-8")
        content = json.loads(text) if report_format == "json" else text
        if report_format == "json" and content != report.model_dump(mode="json"):
            raise StorageIntegrityError(
                "Workflow report artifact differs from its canonical producer"
            )
    return {
        "workflow_id": identity,
        "status": "success" if report.request_fulfilled else "partial",
        "format": report_format,
        "content": content,
        "report": report_ref.model_dump(),
        "coverage": "source-only",
        "limitations": list(report.limitations),
        "required_actions": [item.model_dump() for item in report.required_actions],
    }
