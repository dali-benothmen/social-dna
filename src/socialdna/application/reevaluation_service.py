"""Explicit bounded population refresh, checkpointed analyses and revision history."""

import json
from functools import partial
from typing import Any

from sqlalchemy import Connection, select

from socialdna.application.bootstrap import Application
from socialdna.application.investigation_service import evaluate, show_record
from socialdna.application.performance_service import (
    build_design_population,
    load_performance_report,
)
from socialdna.application.statistical_service import persist_designed_analysis
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.investigation import EvaluationSpec
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.research.reevaluation import ReevaluationContext, ReevaluationSpec, membership
from socialdna.storage import reevaluation_repository as repository
from socialdna.storage import research_repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def _ref(connection: Connection, identity: str, revision: str | None = None) -> EntityRef:
    repo = EvidenceRepository(connection)
    table = metadata.tables["entity_revisions"]
    statement = select(table).where(
        table.c.entity_id == identity, table.c.kind == "research_assessment"
    )
    if revision:
        statement = statement.where(table.c.id == revision)
    row = (
        connection.execute(statement.order_by(table.c.revision_no.desc()).limit(1))
        .mappings()
        .first()
    )
    if not row:
        raise ConfigurationError("Reevaluation requires an existing assessment identity/revision")
    return repo.ref(dict(row))


def _without_clock(spec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in spec.items() if k != "knowledge_cutoff"}


def _changed_rows(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before, after = ({r["post_id"]: r for r in rows} for rows in (old, new))
    result = []
    for identity in sorted(before.keys() | after.keys()):
        previous, current = before.get(identity), after.get(identity)
        if previous == current:
            continue
        result.append(
            {
                "post_id": identity,
                "change": "added"
                if previous is None
                else "removed"
                if current is None
                else "revised",
                **{
                    label: {
                        "snapshot_ids": row["snapshot_ids"],
                        "source_ids": row["source_ids"],
                        "feature_value_ids": sorted(
                            v["id"] for v in row["feature_values"].values()
                        ),
                        "availability": row["availability"],
                    }
                    if row
                    else None
                    for label, row in (("previous", previous), ("current", current))
                },
            }
        )
    return result


def _population(
    application: Application, item: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    selection = item["selector"]
    return build_design_population(
        application,
        CorrectedPerformanceSpec.model_validate(item["spec"]),
        account_ids=selection["account_ids"],
        post_ids=selection["post_ids"],
        roles=selection["roles"],
    )


def _checkpoint(
    request_id: str, index: int, connection: Connection, report: dict[str, Any]
) -> None:
    table = metadata.tables["reevaluation_requests"]
    raw = connection.scalar(select(table.c.progress_json).where(table.c.id == request_id))
    if raw is None:
        raise StorageIntegrityError("Missing reevaluation request checkpoint")
    progress = json.loads(raw)
    progress[str(index)] = report["run_id"]
    connection.execute(
        table.update()
        .where(table.c.id == request_id)
        .values(progress_json=canonical_json(progress))
    )


def reevaluate(
    application: Application,
    identity: str,
    spec: ReevaluationSpec | None = None,
    *,
    revision: str | None = None,
) -> dict[str, Any]:
    requests = metadata.tables["reevaluation_requests"]
    with application.database.transaction() as connection:
        previous = repository.head(connection, _ref(connection, identity, revision))
        payload = json.loads(EvidenceRepository(connection).entity(previous)["payload_json"])
        freshness = repository.refresh(connection, previous.revision_id)
        if freshness["pending_changes"]:
            raise ConfigurationError(
                "Freshness journal budget reached; run research status again before reevaluating"
            )
        pending = (
            connection.execute(
                select(requests)
                .where(
                    requests.c.previous_revision_id == previous.revision_id,
                    requests.c.status != "completed",
                )
                .order_by(requests.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        resume_plan = json.loads(pending["plan_json"]) if pending and spec is None else None
        request_id = pending["id"] if pending and resume_plan else None
    if resume_plan:
        plan = resume_plan
    else:
        options = spec or ReevaluationSpec()
        manifests = payload["population_manifests"]
        if len(manifests) > options.max_analyses:
            raise ConfigurationError("Reevaluation exceeds the explicitly allowed analysis budget")
        if options.designs and len(options.designs) != len(manifests):
            raise ConfigurationError(
                "Replacement designs must correspond to all prior analysis slots"
            )
        cutoff = utc_now()
        items, changes = [], list(freshness["reasons"])
        old_rows, new_rows = [], []
        for index, manifest in enumerate(manifests):
            report = load_performance_report(application, run_id=manifest["run_id"])
            old_spec = report["analysis_configuration"]["spec"]
            updated = (
                options.designs[index]
                if options.designs
                else CorrectedPerformanceSpec.model_validate(
                    {**old_spec, "knowledge_cutoff": cutoff}
                )
            )
            updated_spec = updated.model_dump(mode="json")
            # Renaming a family or holdout is never a way to reset a repeated look.
            for key in ("family_id", "family_terms", "holdout_id", "split_policy"):
                if updated_spec[key] != old_spec[key]:
                    raise ConfigurationError(
                        f"Cumulative reevaluation must preserve {key}; "
                        "register a genuinely new design separately"
                    )
            item = {
                "previous_run_id": report["run_id"],
                "selector": repository.selector(report),
                "spec": updated_spec,
                "target_type": report["target_type"],
                "target_id": report["target_id"],
            }
            rows, definitions, history_rows = _population(application, item)
            config = report["analysis_configuration"]
            item["input_hash"] = hash_config({"rows": rows, "definitions": definitions})
            item["reference_hash"] = hash_config({"rows": history_rows})
            item["refit"] = (
                item["input_hash"] != config["input_hash"]
                or item["reference_hash"] != config["reference_hash"]
                or _without_clock(updated_spec) != _without_clock(old_spec)
            )
            if item["refit"]:
                changes.append(
                    {
                        "kind": "analysis_inputs_changed",
                        "previous_run_id": report["run_id"],
                        "old_input_hash": config["input_hash"],
                        "new_input_hash": item["input_hash"],
                        "old_reference_hash": config["reference_hash"],
                        "new_reference_hash": item["reference_hash"],
                        "changed_spec_fields": [
                            k
                            for k in old_spec
                            if k != "knowledge_cutoff" and updated_spec[k] != old_spec[k]
                        ],
                        "changed_posts": _changed_rows(report["posts"], rows),
                        "changed_references": _changed_rows(
                            report["reference_population"], history_rows
                        ),
                    }
                )
            items.append(item)
            old_rows.extend(report["posts"])
            new_rows.extend(rows)
        protocol = options.protocol or EntityRef.model_validate(payload["protocol"])
        evidence = (
            options.evidence
            if options.evidence is not None
            else tuple(EvidenceRef.model_validate(r) for r in payload["specification"]["evidence"])
        )
        changed_protocol = protocol.model_dump() != payload["protocol"]
        changed_evidence = [r.model_dump() for r in evidence] != payload["specification"][
            "evidence"
        ]
        if (
            not any(item["refit"] for item in items)
            and not changed_protocol
            and not changed_evidence
        ):
            return {
                "status": "review_required" if freshness["state"] == "stale" else "unchanged",
                "assessment": previous.model_dump(),
                "analyses_run": 0,
                "freshness": freshness,
                "independent_confirmation": False,
            }
        if changed_protocol:
            changes.append(
                {
                    "kind": "protocol_replaced",
                    "old_revision_id": payload["protocol"]["revision_id"],
                    "new_revision_id": protocol.revision_id,
                }
            )
        if changed_evidence:
            changes.append({"kind": "supplementary_evidence_replaced"})
        # Validate new protocol/evidence before committing any expensive work.
        with application.database.transaction() as connection:
            from socialdna.application.evidence_service import EvidenceResolver

            for citation in (*research_repository.active(connection, protocol), *evidence):
                EvidenceResolver(connection).resolve(citation, purpose="new_claim")
            protocol_doc = json.loads(
                EvidenceRepository(connection).entity(protocol)["payload_json"]
            )["spec"]
            if protocol_doc["question"] != payload["question"] or {
                h["hypothesis"]["id"] for h in protocol_doc["hypotheses"]
            } != {j["hypothesis"]["id"] for j in payload["judgments"]}:
                raise ConfigurationError(
                    "A replacement protocol must retain the exact question and all rival identities"
                )
        plan = {
            "schema_version": "1.0",
            "policy_version": "cumulative-1",
            "protocol": protocol.model_dump(),
            "evidence": [r.model_dump() for r in evidence],
            "reason": options.reason,
            "items": items,
            "changes": changes,
            "membership": membership(old_rows, new_rows),
            "max_analyses": options.max_analyses,
        }
        request_id = stable_id("reevaluation-request", previous.revision_id, hash_config(plan))
        with application.database.transaction() as connection:
            from sqlalchemy.dialects.sqlite import insert

            connection.execute(
                insert(requests)
                .values(
                    id=request_id,
                    previous_revision_id=previous.revision_id,
                    plan_json=canonical_json(plan),
                    status="pending",
                    progress_json="{}",
                    created_at=utc_now(),
                )
                .on_conflict_do_nothing()
            )
    assert request_id is not None
    with application.database.transaction() as connection:
        request = EvidenceRepository(connection).get("reevaluation_requests", request_id)
        progress = json.loads(request["progress_json"])
        connection.execute(
            requests.update()
            .where(requests.c.id == request_id)
            .values(status="running", error_type=None)
        )
    executed = 0
    try:
        run_ids = []
        for index, item in enumerate(plan["items"]):
            if str(index) in progress:
                run_id = progress[str(index)]
            elif not item["refit"]:
                run_id = item["previous_run_id"]
            else:
                rows, definitions, history_rows = _population(application, item)
                if (
                    hash_config({"rows": rows, "definitions": definitions}) != item["input_hash"]
                    or hash_config({"rows": history_rows}) != item["reference_hash"]
                ):
                    raise ConfigurationError(
                        "Frozen reevaluation inputs changed; "
                        "do not silently resume on different data"
                    )
                report = persist_designed_analysis(
                    application,
                    rows,
                    definitions,
                    CorrectedPerformanceSpec.model_validate(item["spec"]),
                    item["target_type"],
                    item["target_id"],
                    comparing=item["target_type"] == "comparison",
                    batch=None,
                    history=history_rows,
                    reproduced_from=None,
                    population_selector=item["selector"],
                    on_saved=partial(_checkpoint, request_id, index),
                )
                run_id = report["run_id"]
                executed += 1
            run_ids.append(run_id)
        result = evaluate(
            application,
            EvaluationSpec.model_validate(
                {
                    "protocol": plan["protocol"],
                    "analysis_run_ids": run_ids,
                    "evidence": plan["evidence"],
                }
            ),
            reevaluation=ReevaluationContext(
                request_id, previous, plan["membership"], plan["changes"], plan["reason"]
            ),
        )
    except Exception as exc:
        with application.database.transaction() as connection:
            connection.execute(
                requests.update()
                .where(requests.c.id == request_id, requests.c.status != "completed")
                .values(status="failed", error_type=type(exc).__name__)
            )
        raise
    return {
        **result,
        "status": "success",
        "request_id": request_id,
        "previous_assessment": previous.model_dump(),
        "analyses_run": executed,
        "independent_confirmation": False,
    }


def history(application: Application, identity: str, *, limit: int | None = None) -> dict[str, Any]:
    if limit is not None and not 1 <= limit <= 100:
        raise ConfigurationError("History limit must be 1–100")
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        entities, assessments = (
            metadata.tables[n] for n in ("entity_revisions", "research_assessments")
        )
        rows = list(
            connection.execute(
                select(entities)
                .where(entities.c.entity_id == identity)
                .order_by(entities.c.revision_no.desc())
                .limit(1)
            ).mappings()
        )
        if not rows:
            raise ConfigurationError("Unknown research identity")
        ref = repo.ref(dict(rows[0]))
        if ref.kind == "hypothesis":
            question_revision = json.loads(repo.entity(ref)["payload_json"])["question"][
                "revision_id"
            ]
        elif ref.kind == "research_question":
            question_revision = ref.revision_id
        elif ref.kind == "research_assessment":
            question_revision = repo.get("research_assessments", ref.revision_id, "revision_id")[
                "question_revision_id"
            ]
        else:
            raise ConfigurationError("History needs a question, hypothesis or assessment")
        question_id = repo.get("entity_revisions", question_revision)["entity_id"]
        question_revisions = select(entities.c.id).where(
            entities.c.kind == "research_question",
            entities.c.entity_id == question_id,
        )
        revisions: list[str] = list(
            connection.scalars(
                select(assessments.c.revision_id)
                .where(assessments.c.question_revision_id.in_(question_revisions))
                .order_by(assessments.c.created_at.desc(), assessments.c.revision_id.desc())
                .limit(limit + 1 if limit is not None else None)
            )
        )
        truncated = limit is not None and len(revisions) > limit
        revisions = list(reversed(revisions[:limit] if limit is not None else revisions))
        refs = [repo.ref(repo.get("entity_revisions", r)) for r in revisions]
        requests = metadata.tables["reevaluation_requests"]
        attempts = [
            dict(r)
            for r in connection.execute(
                select(
                    requests.c.id,
                    requests.c.previous_revision_id,
                    requests.c.result_revision_id,
                    requests.c.status,
                    requests.c.error_type,
                )
                .where(requests.c.previous_revision_id.in_(revisions))
                .order_by(requests.c.created_at, requests.c.id)
                .limit(limit + 1 if limit is not None else None)
            ).mappings()
        ]
        transitions = metadata.tables["assessment_transitions"]
        links = [
            dict(r)
            for r in connection.execute(
                select(transitions)
                .where(transitions.c.previous_revision_id.in_(revisions))
                .order_by(transitions.c.created_at, transitions.c.request_id)
                .limit(limit + 1 if limit is not None else None)
            ).mappings()
        ]
        from socialdna.storage import experiment_repository

        experiment_table = metadata.tables["experiment_assessments"]
        experiment_feedback = []
        revision: str
        for revision in connection.scalars(
            select(experiment_table.c.revision_id)
            .where(experiment_table.c.question_revision_id.in_(question_revisions))
            .order_by(experiment_table.c.revision_id)
            .limit(limit + 1 if limit is not None else None)
        ):
            experiment_ref = repo.ref(repo.get("entity_revisions", revision))
            try:
                content = experiment_repository.content(connection, experiment_ref)
                experiment_feedback.append(
                    {
                        "ref": experiment_ref.model_dump(),
                        "eligible": True,
                        "judgments": content["judgments"],
                    }
                )
            except ConfigurationError:
                experiment_feedback.append(
                    {"ref": experiment_ref.model_dump(), "eligible": False, "judgments": None}
                )
    records = []
    for assessment in refs:
        record = show_record(application, assessment)
        content = record.pop("content")
        record["judgments"] = (
            [
                {
                    "hypothesis": j["hypothesis"],
                    "local_status": j["local_association"]["status"],
                    "mechanism_status": j["mechanism_status"],
                }
                for j in content["judgments"]
            ]
            if content
            else None
        )
        record["comparison"] = content.get("reevaluation") if content else None
        records.append(record)
    if limit is not None:
        truncated = truncated or any(
            len(items) > limit for items in (attempts, links, experiment_feedback)
        )
        attempts, links, experiment_feedback = (
            items[:limit] for items in (attempts, links, experiment_feedback)
        )
    return {
        "status": "success",
        "question_revision_id": question_revision,
        "question_id": question_id,
        "assessments": records,
        "transitions": links,
        "requests": attempts,
        "experiment_assessments": experiment_feedback,
        "truncated": truncated,
    }


def status(application: Application, *, limit: int = 100) -> dict[str, Any]:
    if not 1 <= limit <= 1000:
        raise ConfigurationError("Research status allows 1–1,000 assessments per call")
    table = metadata.tables["research_assessments"]
    watches = metadata.tables["assessment_watches"]
    with application.database.transaction() as connection:
        # Oldest cursor first makes bounded repeated scans fair, including after
        # an upgrade. It does not fit a model or touch an immutable assessment.
        identities: list[str] = list(
            connection.scalars(
                select(table.c.revision_id)
                .outerjoin(watches, watches.c.assessment_revision_id == table.c.revision_id)
                .where((watches.c.state.is_(None)) | (watches.c.state != "superseded"))
                .order_by(watches.c.cursor.asc().nullsfirst(), table.c.revision_id)
                .limit(limit + 1)
            )
        )
        rows = [
            {
                "assessment_revision_id": identity,
                **repository.refresh(connection, identity, limit=1000),
            }
            for identity in identities[:limit]
        ]
    return {
        "status": "partial"
        if len(identities) > limit or any(r["pending_changes"] for r in rows)
        else "success",
        "assessments": rows,
        "analyses_run": 0,
    }
