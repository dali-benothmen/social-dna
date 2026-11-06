"""Render evidence-qualified original proposals, never promise outcomes or execute tests."""

import json
import re
from typing import Any

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef
from socialdna.memory.documents import current_revision, entity_active
from socialdna.research.recommendations import RecommendationSpec
from socialdna.storage import context_repository as context
from socialdna.storage import research_repository as research
from socialdna.storage.evidence_repository import EvidenceRepository


def _scope(source: dict[str, Any], target: dict[str, Any]) -> bool:
    fields = (
        "platform",
        "surface",
        "native_format",
        "language",
        "market",
        "audience",
        "objective",
        "traffic",
    )
    return all(source.get(k) == target.get(k) for k in fields) and set(target["niches"]).issubset(
        source.get("niches", [])
    )


def _source(
    connection: Any, item: Any, spec: RecommendationSpec
) -> tuple[dict[str, Any], list[str]]:
    resolved = EvidenceResolver(connection).resolve(item.evidence, purpose="new_claim")
    repo = EvidenceRepository(connection)
    raw = json.loads(repo.entity(resolved.subject)["payload_json"])
    kind = resolved.subject.kind
    lane, scope, outcomes, copied = (
        raw.get("claim_level", "literal_observation_not_effect"),
        None,
        None,
        [],
    )
    if kind == "experiment_analysis":
        registered = json.loads(
            repo.entity(EntityRef.model_validate(raw["registration"]))["payload_json"]
        )
        lane, scope, outcomes = (
            raw["claim_level"],
            registered["spec"]["scope"],
            raw["analysis"]["outcomes"],
        )
    elif kind in ("discovery_search", "creative_pattern"):
        lane = raw["claim_level"]
        scope = raw.get("scope_conditions") or raw.get("spec", {}).get("scope")
        outcomes = raw.get("result", {}).get("outer")
        if kind == "creative_pattern":
            parent = json.loads(
                repo.entity(EntityRef.model_validate(raw["search"]))["payload_json"]
            )
            outcomes = parent["result"].get("outer")
    elif kind in ("research_assessment", "research_finding", "statistical_analysis"):
        lane = raw.get("claim_level", "observational_finding_not_causal")
        outcomes = raw.get("judgments", raw.get("local_association"))
    elif kind == "platform_statement":
        lane = "official_guidance_not_local_effect"
        document = context.read(connection, EntityRef.model_validate(raw["spec"]["document"]))
        if (
            document["spec"]["platform"] != spec.scope.platform
            or raw["spec"]["surface"] != spec.scope.surface
        ):
            raise ConfigurationError("Official guidance cannot be pooled across platforms/surfaces")
    elif kind == "profile_review":
        lane = "qualitative_profile_rubric_not_measured_conversion"
    elif kind == "funnel_context":
        lane = "measured_aggregate_funnel_not_profile_effect"
    elif kind == "study_finding":
        lane = "reviewed_external_literature_not_local_replication"
    if resolved.locator_kind == "statistical_result":
        lane = "observational_statistical_result_not_causal"
        locator = resolved.locator.model_dump(mode="json") if resolved.locator else {}
        report = json.loads(repo.get("statistical_analyses", locator["analysis_id"])["result_json"])
        outcomes = report["results"]
    if resolved.locator_kind == "post_text":
        copied.append(raw.get("caption") or "")
    if resolved.locator:
        locator = resolved.locator.model_dump(mode="json")
        if resolved.locator_kind in ("post_text", "media_span"):
            copied.append(locator.get("quote") or locator.get("excerpt") or "")
    return {
        "evidence": item.evidence.model_dump(),
        "subject": resolved.subject.model_dump(),
        "role": item.role,
        "declared_applicability": item.applicability,
        "rationale": item.rationale,
        "lane": lane,
        "tested_outcomes_and_failures": outcomes,
        "scope_match": _scope(scope, spec.scope.model_dump(mode="json"))
        if scope
        else "unverified_or_source_declared",
        "source_current": current_revision(connection, resolved.subject),
        "available_at": resolved.available_at,
    }, copied


def create(app: Application, spec: RecommendationSpec) -> dict[str, Any]:
    identity = stable_id("research", "recommendation", spec.key)
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        previous = repo.latest("recommendation", identity)
        if previous:
            prior = json.loads(entity_active(connection, previous)["payload_json"])
            if prior["spec"] == spec.model_dump(mode="json"):
                return show(app, previous, connection=connection)
            if spec.supersedes != previous:
                raise ConfigurationError(
                    "A changed recommendation needs the exact supersedes revision"
                )
        elif spec.supersedes:
            raise ConfigurationError("No prior recommendation exists for this key")
        sources, source_texts = [], []
        for item in spec.evidence:
            result, copied = _source(connection, item, spec)
            sources.append(result)
            source_texts.extend(copied)
        contexts = []
        context_evidence = []
        context_refs = {ref.revision_id: ref for ref in spec.context}
        # Citing context evidence must not bypass its actual platform/account scope
        # merely by omitting the same entity from the optional context list.
        for source in sources:
            subject = EntityRef.model_validate(source["subject"])
            if subject.kind in context.KINDS:
                context_refs[subject.revision_id] = subject
        for ref in context_refs.values():
            if ref.kind not in context.KINDS:
                raise ConfigurationError(
                    "Growth context must use a delivered C1 canonical producer"
                )
            captured = context.read(connection, ref)
            account = json.loads(
                repo.entity(EntityRef.model_validate(captured["account"]))["payload_json"]
            )
            if (
                account["platform"] != spec.scope.platform
                or account.get("niche") not in spec.scope.niches
            ):
                raise ConfigurationError("Recommendation context belongs to another platform/niche")
            data = captured["spec"]
            scoped = data.get("scope", data)
            for key in ("surface", "native_format", "language", "audience", "market"):
                if (
                    key in scoped
                    and scoped[key] is not None
                    and scoped[key] != getattr(spec.scope, key)
                ):
                    raise ConfigurationError(
                        "Recommendation context language/surface/audience mismatch"
                    )
            contexts.append(ref)
            context_evidence.append(context.cite(connection, ref))
        source_kinds = {r["subject"]["kind"] for r in sources} | {r.kind for r in contexts}
        required = {
            "publishing": {"publication_context", "publishing_window", "context_report"},
            "distribution": {
                "platform_statement",
                "platform_capabilities",
                "distribution_observation",
            },
            "profile": {"profile_snapshot", "profile_review", "funnel_context"},
        }
        if spec.domain in required and not source_kinds.intersection(required[spec.domain]):
            raise ConfigurationError(
                "This strategy branch requires its delivered C1 evidence/context"
            )
        text = " ".join(a.change for a in spec.actions)
        if re.search(
            r"\bguarantee\w*\b|exact ranking weights|algorithm bypass|proven mediator",
            text.casefold(),
        ):
            raise ConfigurationError(
                "Recommendations cannot guarantee outcomes or claim hidden weights/mediators"
            )
        tokens = re.findall(r"\w+", text.casefold())
        grams = {tuple(tokens[i : i + 8]) for i in range(max(0, len(tokens) - 7))}
        for source_text in source_texts:
            words = re.findall(r"\w+", source_text.casefold())
            if any(tuple(words[i : i + 8]) in grams for i in range(max(0, len(words) - 7))):
                raise ConfigurationError(
                    "Copied source language: propose an original alternative, not a creator script"
                )
        caveats = [
            *spec.uncertainty,
            "Proposed strategy and next test, not a guaranteed lift or executed intervention.",
            "Applicability is source-declared; originality checks cover only cited creator spans.",
            "Search, recommendation and conversion differ; attention is not sustained growth.",
            "Treatment effects do not establish psychological mediation.",
        ]
        if spec.domain == "profile":
            caveats.append(
                "Public profile quality is not measured follows, installs or business conversion."
            )
        if spec.domain == "production" and source_kinds <= {"post", "media", "publication_context"}:
            caveats.append(
                "Craft suggestion is an unvalidated heuristic; "
                "no measured craft/outcome link supplied."
            )
        if not any(e.role == "counterevidence" for e in spec.evidence):
            caveats.append(
                "No counterevidence citation supplied; this is not proof that none exists."
            )
        if any(s["scope_match"] is False or not s["source_current"] for s in sources):
            caveats.append(
                "At least one source is out of exact scope or stale; do not generalize its effect."
            )
        payload = {
            "spec": spec.model_dump(mode="json"),
            "scope_conditions": spec.scope.model_dump(mode="json"),
            "sources": sources,
            "context_evidence": [r.model_dump() for r in context_evidence],
            "evidence_date": max(
                (s["available_at"] or "unknown" for s in sources), default="unknown"
            ),
            "decision": "test_first",
            "claim_level": spec.requested_claim,
            "actions": [a.model_dump() for a in spec.actions],
            "next_test": spec.next_test,
            "limitations": caveats,
            "expected_lift": None,
            "external_execution_authorized": False,
            "summary": "Evidence-qualified original " + spec.domain + " strategy; test first",
        }
        provenance = research.provenance(connection, "recommendation:" + spec.key, payload)
        ref = research.save(
            connection,
            "recommendation",
            spec.key,
            payload,
            provenance,
            entities=tuple(contexts),
            evidence=tuple(e.evidence for e in spec.evidence) + tuple(context_evidence),
        )
        artifact = app.artifacts.put_bytes(
            connection,
            canonical_json(payload).encode(),
            kind="recommendation-report",
            mime_type="application/json",
        )
        app.artifacts.add_reference(
            connection,
            artifact,
            owner_type="recommendation",
            owner_id=ref.revision_id,
            role="frozen",
        )
        return show(app, ref, connection=connection)


def show(app: Application, ref: EntityRef, *, connection: Any = None) -> dict[str, Any]:
    if connection is None:
        with app.database.transaction() as opened:
            return show(app, ref, connection=opened)
    if ref.kind != "recommendation":
        raise ConfigurationError("Expected an actual recommendation revision")
    payload = json.loads(entity_active(connection, ref)["payload_json"])
    return {
        "ref": ref.model_dump(),
        "evidence": research.cite(connection, ref).model_dump(),
        "content": payload,
        "operational_freshness": "current"
        if current_revision(connection, ref)
        else "stale_frozen_context",
    }
