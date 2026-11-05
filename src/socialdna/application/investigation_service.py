"""Prepared rival protocols and one immutable, evidence-constrained assessment path."""

import json
from typing import Any

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import ClaimValidator, EvidenceResolver
from socialdna.application.performance_service import load_performance_report
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.investigation import EvaluationSpec, ResearchProtocol
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.psychology import constructs, hypotheses, operationalizations
from socialdna.research.reevaluation import ReevaluationContext
from socialdna.research.reevaluation import compare as compare_assessments
from socialdna.storage import reevaluation_repository as reevaluations
from socialdna.storage import research_repository as research
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def prepare(application: Application, spec: ResearchProtocol) -> dict[str, Any]:
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        repo.entity(spec.question)
        revisions = metadata.tables["entity_revisions"]
        declared: set[str] = set(
            connection.scalars(
                select(revisions.c.entity_id).where(
                    revisions.c.kind == "hypothesis",
                    func.json_extract(revisions.c.payload_json, "$.question.revision_id")
                    == spec.question.revision_id,
                )
            )
        )
        if declared != {p.hypothesis.id for p in spec.hypotheses}:
            raise ConfigurationError(
                "A bounded protocol must retain all registered rival hypotheses"
            )
        entities = [spec.question]
        evidence: list[EvidenceRef] = []
        literature = []
        for plan in spec.hypotheses:
            draft = json.loads(repo.entity(plan.hypothesis)["payload_json"])
            if draft["question"] != spec.question.model_dump():
                raise ConfigurationError(
                    "Rival hypothesis belongs to a different question revision"
                )
            constructs.validate(connection, plan)
            literature.append(operationalizations.applicability(connection, plan))
            entities.extend(
                [
                    plan.hypothesis,
                    *(
                        [plan.construct_ref, plan.operationalization]
                        if plan.construct_ref and plan.operationalization
                        else []
                    ),
                ]
            )
            evidence.extend(r.finding for r in plan.literature)
        for ref in entities:
            if ref.kind in research.KINDS:
                for citation in research.active(connection, ref):
                    EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        payload = {
            "spec": spec.model_dump(mode="json"),
            "question": spec.question.model_dump(),
            "literature_reviews": literature,
            "registration_status": "prepared_protocol_not_preregistration_or_experiment",
        }
        provenance = research.provenance(connection, "protocol:" + spec.key, payload)
        ref = research.save(
            connection,
            "research_protocol",
            spec.key,
            payload,
            provenance,
            entities=tuple(entities),
            evidence=tuple(evidence),
        )
        connection.execute(
            insert(metadata.tables["research_protocols"])
            .values(
                revision_id=ref.revision_id,
                question_revision_id=spec.question.revision_id,
            )
            .on_conflict_do_nothing()
        )
        return {
            "protocol": ref.model_dump(),
            "evaluation_ready": True,
            "literature_reviews": literature,
            "written": True,
        }


def _scope_evidence(
    connection: Connection, ref: EvidenceRef, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    resolved = EvidenceResolver(connection).resolve(ref, purpose="new_claim")
    locator = resolved.locator
    assert locator is not None
    payload = locator.model_dump(mode="json")
    post_ids = {r["post_id"] for r in rows}
    account_ids = {r["account_id"] for r in rows}
    repo = EvidenceRepository(connection)
    document = json.loads(repo.entity(resolved.subject)["payload_json"])
    if locator.kind in ("media_span", "creative_event", "creative_coverage"):
        links = metadata.tables["post_media"]
        linked: set[str] = set(
            connection.scalars(
                select(links.c.post_id).where(links.c.media_asset_id == payload["media"]["id"])
            )
        )
        eligible = bool(post_ids & linked)
    elif locator.kind in ("comment_span", "post_text"):
        eligible = payload.get("post", payload["subject"])["id"] in post_ids
    elif locator.kind == "audience_record":
        collection = json.loads(
            repo.entity(EntityRef.model_validate(payload["collection"]))["payload_json"]
        )
        eligible = bool(collection["spec"]["posts"]) and all(
            p["id"] in post_ids for p in collection["spec"]["posts"]
        )
    elif locator.kind == "behavioral_record":
        if resolved.subject.kind == "metric_bin":
            document = json.loads(
                repo.entity(EntityRef.model_validate(document["series"]))["payload_json"]
            )
        subject = document.get("spec", {}).get("subject")
        eligible = bool(
            subject and subject["id"] in (post_ids if subject["kind"] == "post" else account_ids)
        )
    elif locator.kind == "metric_snapshot":
        eligible = payload["measured_subject"]["id"] in post_ids | account_ids
    elif locator.kind == "context_record":
        members = document.get("spec", {}).get("posts", [])
        post = document.get("post")
        eligible = (
            resolved.subject.kind in ("publication_context", "publishing_window", "trend_context")
            and document["account"]["id"] in account_ids
            and (post["id"] in post_ids if post else all(p["id"] in post_ids for p in members))
        )
    else:
        eligible = False
    if not eligible:
        raise ConfigurationError("Supplementary evidence is outside the frozen analysis population")
    return {
        "ref": ref.model_dump(),
        "kind": locator.kind,
        "subject": resolved.subject.model_dump(),
        "data": document,
        "qualification": "Supplementary observation; not a mediator or causal attribution.",
    }


def evaluate(
    application: Application,
    spec: EvaluationSpec,
    *,
    reevaluation: ReevaluationContext | None = None,
) -> dict[str, Any]:
    reports = [load_performance_report(application, run_id=run) for run in spec.analysis_run_ids]
    for report in reports:
        if report.get("schema_version") != "2.0":
            raise ConfigurationError("Research requires an explicit version-2 frozen analysis")
        CorrectedPerformanceSpec.model_validate(report["analysis_configuration"]["spec"])
        if len(report["posts"]) + len(report["reference_population"]) > 10000:
            raise ConfigurationError("Research evaluation exceeds the 10,000-row budget")
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        previous = (
            json.loads(repo.entity(reevaluation.previous)["payload_json"]) if reevaluation else None
        )
        protocol_row = repo.entity(spec.protocol)
        protocol_citations = research.active(connection, spec.protocol)
        for citation in protocol_citations:
            EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        protocol = ResearchProtocol.model_validate(json.loads(protocol_row["payload_json"])["spec"])
        rows = [r for report in reports for r in report["posts"]]
        dependencies = [spec.protocol]
        refs = [*spec.evidence, *protocol_citations]
        statistical_citations: dict[str, list[dict[str, Any]]] = {}
        for report in reports:
            statistical_citations[report["run_id"]] = []
            for citation in report["statistical_evidence"]:
                ref = EvidenceRef.model_validate(citation["ref"])
                resolved = EvidenceResolver(connection).resolve(ref, purpose="new_claim")
                dependencies.append(resolved.subject)
                refs.append(ref)
                assert resolved.locator is not None
                statistical_citations[report["run_id"]].append(
                    {"ref": ref.model_dump(), "locator": resolved.locator.model_dump()}
                )
            ledger = report["test_ledger"]
            analysis_table = metadata.tables["statistical_analyses"]
            analysis_id = connection.scalar(
                select(analysis_table.c.id).where(analysis_table.c.run_id == report["run_id"])
            )
            attempt = repo.get("test_attempts", ledger["attempt_id"])
            if (
                attempt["status"] != "completed"
                or attempt["family_id"] != ledger["family_id"]
                or attempt["analysis_id"] != analysis_id
            ):
                raise ConfigurationError(
                    "Research requires the completed original test-family attempt"
                )
        historical_refs = []
        if previous:
            analyses = metadata.tables["statistical_analyses"]
            for manifest in previous["population_manifests"]:
                historical = json.loads(
                    connection.execute(
                        select(analyses.c.result_json).where(
                            analyses.c.run_id == manifest["run_id"]
                        )
                    ).scalar_one()
                )
                for citation in historical["statistical_evidence"]:
                    ref = EvidenceRef.model_validate(citation["ref"])
                    EvidenceResolver(connection).resolve(ref, purpose="new_claim")
                    refs.append(ref)
                    historical_refs.append(ref.model_dump())
        supplements = [_scope_evidence(connection, r, rows) for r in spec.evidence]
        judgments: list[dict[str, Any]] = []
        for plan in protocol.hypotheses:
            local = hypotheses.association(plan, reports)
            literature = operationalizations.applicability(connection, plan)
            roles = [
                {
                    "evidence": r.finding.model_dump(),
                    "role": "context",
                    "target": "reviewed_literature_applicability",
                }
                for r in plan.literature
            ]
            for observation in local["observations"]:
                for item in statistical_citations[observation["run_id"]]:
                    locator = item["locator"]
                    if locator.get("term") == plan.prediction.feature or (
                        observation["term"] is None
                        and locator.get("diagnostic") in ("regression", "comparison")
                    ):
                        roles.append(
                            {
                                "evidence": item["ref"],
                                "role": {
                                    "consistent": "supporting",
                                    "contrary": "contradicting",
                                }.get(observation["status"], "non_discriminating"),
                                "target": "local_prediction_only_not_psychological_mediation",
                            }
                        )
            judgments.append(
                {
                    "hypothesis": plan.hypothesis.model_dump(),
                    "hypothesis_statement": json.loads(
                        repo.entity(plan.hypothesis)["payload_json"]
                    )["statement"],
                    "prediction": plan.prediction.model_dump(mode="json"),
                    "literature": literature,
                    "local_association": local,
                    "evidence_roles": roles,
                    "mechanism_status": "not_applicable"
                    if plan.explanation == "contextual"
                    else "unsupported_literature"
                    if literature["status"] == "unsupported"
                    else "non_discriminating",
                    "extraction_reliability": hypotheses.measurement_quality(plan, reports),
                    "generalization": [
                        {
                            "run_id": r["run_id"],
                            "validation": r["results"]["validation"],
                            "scope": r["analysis_configuration"]["spec"]["population"],
                        }
                        for r in reports
                    ],
                    "causal_identification": "not_identified",
                    "confounders": list(plan.confounders),
                    "scope_conditions": list(plan.scope_conditions),
                    "what_would_change_conclusion": plan.prediction.falsifier,
                    "counterexamples": [
                        hypotheses.examples(r, plan.prediction.feature)
                        for r in reports
                        if r["analysis_configuration"]["spec"]["metric_key"]
                        == plan.prediction.metric_key
                    ],
                }
            )
        claim = (
            "association"
            if any(j["local_association"]["claim_level"] == "association" for j in judgments)
            else "hypothesis"
        )
        if spec.expected_claim_level == "association" and claim != "association":
            raise ConfigurationError("Available analyses cannot support the requested association")
        refs = list({r.revision_id: r for r in refs}.values())
        ClaimValidator(connection).validate_research(claim, tuple(refs))
        dependencies = list({r.revision_id: r for r in dependencies}.values())
        experiment_proposal = {
            "status": "proposed_not_executed",
            "variants": list(protocol.treatment_variants),
            "design": protocol.experiment_design,
            "predictions": [
                {
                    "hypothesis": p.hypothesis.model_dump(),
                    "measure": p.prediction.discriminating_measurement,
                    "falsifier": p.prediction.falsifier,
                }
                for p in protocol.hypotheses
            ],
            "design_requirements": [
                "Register actual assignment unit and primary outcomes.",
                "Measure competing constructs with reviewed instruments.",
                "Check carryover, attrition, audience allocation and spillover.",
                "No posting, recruitment or spending is authorized.",
            ],
            "limitation": "A creative effect alone cannot establish the proposed mediator.",
        }
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "report_type": "research_assessment",
            "question": protocol.question.model_dump(),
            "question_text": json.loads(repo.entity(protocol.question)["payload_json"])["question"],
            "protocol": spec.protocol.model_dump(),
            "specification": spec.model_dump(mode="json"),
            "claim_level": claim,
            "input_hash": hash_config(spec.model_dump(mode="json")),
            "judgments": judgments,
            "supplementary_evidence": supplements,
            "experiment_proposal": experiment_proposal,
            "population_manifests": [
                {
                    "run_id": r["run_id"],
                    "configuration": r["analysis_configuration"],
                    "post_ids": [p["post_id"] for p in r["posts"]],
                    "reference_post_ids": [p["post_id"] for p in r["reference_population"]],
                    "test_ledger": r["test_ledger"],
                    "independent_confirmation": False,
                }
                for r in reports
            ],
            "context": {
                k: getattr(protocol, k)
                for k in (
                    "production_context",
                    "distribution_context",
                    "publishing_context",
                    "profile_context",
                )
            },
            "limitations": [
                "No psychological mediator or causal effect is identified by this assessment.",
                "Literature, measured content, expressed reactions and behavior are distinct.",
                "Analysis attempts/holdouts are reused, not new independent confirmation.",
                "Unavailable owner analytics are not inferred from comments or public counters.",
                "Context/applicability are human-supplied, not automatically verified.",
                "Assessment inputs are frozen; freshness is tracked separately from this report.",
            ],
        }
        if reevaluation:
            assert previous is not None
            if previous["question"] != payload["question"] or {
                j["hypothesis"]["id"] for j in previous["judgments"]
            } != {j["hypothesis"]["id"] for j in judgments}:
                raise ConfigurationError(
                    "Reevaluation must retain the exact question and rival identities"
                )
            payload["reevaluation"] = compare_assessments(previous, payload, reevaluation)
            old_refs = {r["revision_id"] for r in previous["evidence_inputs"]}
            current_refs = {r.revision_id for r in refs}
            payload["reevaluation"]["evidence_revisions"] = {
                "reused": sorted(old_refs & current_refs),
                "new": sorted(current_refs - old_refs),
                "removed": sorted(old_refs - current_refs),
                "historical_comparison_inputs": historical_refs,
                "qualification": "New citation revisions are not independent new observations.",
            }
            for judgment, transition in zip(
                judgments, payload["reevaluation"]["transitions"], strict=True
            ):
                judgment["assessment_disposition"] = transition["disposition"]
            payload["input_hash"] = hash_config(
                {
                    "spec": spec.model_dump(mode="json"),
                    "request_id": reevaluation.request_id,
                }
            )
            payload["limitations"].extend(payload["reevaluation"]["limitations"])
        provenance = research.provenance(connection, "evaluation", payload)
        assessment = research.save(
            connection,
            "research_assessment",
            payload["input_hash"],
            payload,
            provenance,
            entities=tuple(dependencies),
            evidence=tuple(refs),
        )
        connection.execute(
            insert(metadata.tables["research_assessments"])
            .values(
                revision_id=assessment.revision_id,
                protocol_revision_id=spec.protocol.revision_id,
                question_revision_id=protocol.question.revision_id,
                input_hash=payload["input_hash"],
                created_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        for index, (entity_revision, citation_revision) in enumerate(
            [
                *((r.revision_id, None) for r in dependencies),
                *((None, r.revision_id) for r in refs),
            ]
        ):
            connection.execute(
                insert(metadata.tables["assessment_dependencies"])
                .values(
                    assessment_revision_id=assessment.revision_id,
                    ordinal=index,
                    entity_revision_id=entity_revision,
                    evidence_revision_id=citation_revision,
                    role="frozen_input",
                )
                .on_conflict_do_nothing()
            )
        assessment_citation = research.cite(connection, assessment)
        findings = []
        for judgment in judgments:
            finding = research.save(
                connection,
                "research_finding",
                assessment.revision_id + judgment["hypothesis"]["revision_id"],
                {
                    "assessment": assessment.model_dump(),
                    "question": protocol.question.model_dump(),
                    **judgment,
                    "claim_level": judgment["local_association"]["claim_level"],
                },
                provenance,
                entities=(assessment,),
                evidence=(assessment_citation,),
            )
            for link in judgment["evidence_roles"]:
                connection.execute(
                    insert(metadata.tables["evidence_links"])
                    .values(
                        owner_revision_id=finding.revision_id,
                        evidence_revision_id=link["evidence"]["revision_id"],
                        scope_revision_id=protocol.question.revision_id,
                        role=link["role"],
                    )
                    .on_conflict_do_nothing()
                )
            findings.append(
                {
                    "ref": finding.model_dump(),
                    "evidence": research.cite(connection, finding).model_dump(),
                }
            )
        brief = research.save(
            connection,
            "experiment_brief",
            assessment.revision_id,
            {
                "assessment": assessment.model_dump(),
                **experiment_proposal,
            },
            provenance,
            entities=(assessment,),
            evidence=(assessment_citation,),
        )
        research.cite(connection, brief)
        reevaluations.track(connection, assessment, payload, reports)
        if reevaluation:
            reevaluations.complete(
                connection, reevaluation.request_id, reevaluation.previous, assessment
            )
        return {
            "assessment": assessment.model_dump(),
            "findings": findings,
            "experiment_brief": brief.model_dump(),
            "claim_level": claim,
            "written": True,
        }


def show_record(application: Application, ref: EntityRef) -> dict[str, Any]:
    with application.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        try:
            payload = json.loads(repo.entity(ref)["payload_json"])
            dependencies = research.active(connection, ref)
            for citation in dependencies:
                EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        except ConfigurationError as exc:
            return {
                "ref": ref.model_dump(),
                "status": "withheld",
                "content": None,
                "limitations": [str(exc)],
                "freshness": "ineligible",
            }
        freshness = {"state": "pinned_inputs", "reasons": [], "pending_changes": False}
        if ref.kind == "research_assessment":
            freshness = reevaluations.refresh(connection, ref.revision_id)
        elif ref.kind in ("research_finding", "experiment_brief"):
            freshness = reevaluations.refresh(connection, payload["assessment"]["revision_id"])
        return {
            "ref": ref.model_dump(),
            "status": "success",
            "content": payload,
            "freshness": freshness["state"],
            "freshness_details": freshness,
        }


def assessment_report(
    application: Application, ref: EntityRef, report_format: str = "json"
) -> dict[str, Any]:
    from socialdna.reporting.investigation import render_assessment

    if report_format not in ("json", "markdown") or ref.kind != "research_assessment":
        raise ConfigurationError("An assessment report needs an assessment and JSON/Markdown")
    record = show_record(application, ref)
    if record["status"] != "success":
        raise ConfigurationError("Research evidence is ineligible; report content is withheld")
    payload = record["content"]
    with application.database.transaction() as connection:
        citations = [
            EvidenceResolver(connection)
            .resolve(EvidenceRef.model_validate(raw))
            .model_dump(mode="json")
            for raw in payload["evidence_inputs"]
        ]
        bibliography = []
        repo = EvidenceRepository(connection)
        for citation in citations:
            if citation["locator_kind"] == "study_excerpt":
                source = EntityRef.model_validate(citation["locator"]["source_document"])
                document = json.loads(repo.entity(source)["payload_json"])["spec"]
                bibliography.append(
                    {
                        k: document[k]
                        for k in (
                            "title",
                            "url",
                            "doi",
                            "authors",
                            "year",
                            "reviewer",
                            "verification_note",
                        )
                    }
                )
                finding = json.loads(
                    repo.entity(EntityRef.model_validate(citation["subject"]))["payload_json"]
                )["spec"]
                bibliography[-1]["reviewed_finding"] = {
                    k: finding[k]
                    for k in (
                        "summary",
                        "design",
                        "population",
                        "exposure",
                        "outcome",
                        "direction",
                        "limitations",
                    )
                }
                bibliography[-1]["evidence"] = citation["ref"]
        content = {
            **payload,
            "citations": citations,
            "bibliography": bibliography,
            "assessment": ref.model_dump(),
        }
        result = {}
        for name, text in (
            ("json", canonical_json(content)),
            ("markdown", render_assessment(content)),
        ):
            artifact = application.artifacts.put_bytes(
                connection,
                text.encode(),
                kind="research-assessment-report",
                mime_type="application/json" if name == "json" else "text/markdown",
            )
            application.artifacts.add_reference(
                connection,
                artifact,
                owner_type="entity_revision",
                owner_id=ref.revision_id,
                role=name,
            )
            row = application.artifacts.get(connection, artifact)
            result[name] = {
                "id": artifact,
                "path": str(application.artifacts.path_for(row["relative_path"])),
            }
    return {
        "ref": ref.model_dump(),
        "status": "success",
        "format": report_format,
        "freshness": record["freshness"],
        "freshness_details": record.get("freshness_details"),
        "content": content if report_format == "json" else render_assessment(content),
        "artifact": result[report_format],
        "limitations": payload["limitations"],
    }
