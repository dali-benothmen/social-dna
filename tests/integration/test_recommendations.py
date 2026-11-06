"""Non-cooking strategies consume actual C1 producers, not invented effect sizes."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from test_platform_research import platform_export
from test_profile_conversion import profile_export

from socialdna.application import (
    audience_service,
    context_service,
    platform_service,
    profile_service,
)
from socialdna.application import recommendation_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.context import ContextExport
from socialdna.domain.evidence import EntityRef
from socialdna.domain.profile import CRITERIA
from socialdna.memory import documents, graph, lexical
from socialdna.research.recommendations import RecommendationSpec
from socialdna.storage.creative_repository import cite_post_text
from socialdna.storage.evidence_repository import EvidenceRepository


def proposed(
    domain: str, evidence: dict[str, Any], context: list[dict[str, Any]], *, platform: str = "demo"
) -> RecommendationSpec:
    objective = (
        "recommendation"
        if domain == "distribution"
        else "conversion"
        if domain == "profile"
        else "aggregate_attention"
    )
    target = {
        "production": "shot_size",
        "publishing": "title",
        "distribution": "retention",
        "profile": "bio",
    }[domain]
    return RecommendationSpec.model_validate(
        {
            "key": "education-" + domain,
            "domain": domain,
            "scope": {
                "platform": platform,
                "surface": "shorts" if domain == "distribution" else "aggregate",
                "native_format": "video",
                "language": "en",
                "market": "US",
                "audience": "Owned education viewers",
                "niches": ["education"],
                "objective": objective,
                "traffic": "organic" if domain == "distribution" else "unknown",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-12-01T00:00:00Z",
                "basis": "Actual owned source frame; not a universal creator population",
            },
            "actions": [
                {
                    "target": target,
                    "change": {
                        "production": "Frame the small teaching prop tightly "
                        "during the demonstration.",
                        "publishing": "Name the specific skill demonstrated in the title "
                        "rather than using a vague teaser.",
                        "distribution": "Try a shorter setup that introduces the lesson's "
                        "practical payoff immediately.",
                        "profile": "State the learner level and lesson topic "
                        "before the optional link invitation.",
                    }[domain],
                    "hold_constant": "Keep the underlying lesson, duration "
                    "and audience frame fixed.",
                    "measure": "Use permitted source-specific measurements; "
                    "report missing owner analytics.",
                    "falsifier": "A suitable registered comparison with worse "
                    "or indistinguishable outcomes.",
                }
            ],
            "evidence": [
                {
                    "evidence": evidence,
                    "role": "support",
                    "applicability": "indirect",
                    "rationale": "Source-qualified context, "
                    "not demonstrated effectiveness of this new wording",
                }
            ],
            "context": context,
            "counterevidence_search": "Reviewed the supplied record "
            "and retained unavailable comparative outcomes.",
            "uncertainty": ["No causal effect for this proposed education variant is established."],
            "next_test": "Register a creator-blocked comparison and the actual outcome "
            "before authorized execution.",
        }
    )


def inputs(
    app: Any, domain: str, platform: str
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        account = repo.latest("account", stable_id("account", platform, "0001"))
        post = repo.latest("post", stable_id("post", platform, "p0"))
        assert account and post
        citation = cite_post_text(connection, post, "caption")
    if domain == "production":
        return citation.model_dump(), [], None
    if domain == "publishing":
        export = ContextExport.model_validate(
            {
                "dataset_id": "education-publishing",
                "source_uri": "urn:owned:education",
                "permission_basis": "Owned supplied metadata",
                "records": [
                    {
                        "record_type": "publication_context",
                        "key": "captured",
                        "account": account.model_dump(),
                        "post": post.model_dump(),
                        "clock": {"captured_at": "2026-02-01T00:00:00Z"},
                        "published_original": "2026-01-01T00:00:00Z",
                        "native_format": "video",
                        "language": "en",
                        "language_basis": "source",
                        "title": {"state": "present", "value": "A concrete education lesson"},
                        "description": {"state": "not_collected"},
                        "caption": {"state": "not_collected"},
                        "niche": "education",
                        "audience": "Owned education viewers",
                    }
                ],
            }
        )
        imported = context_service.import_into_application(app, export)
    elif domain == "profile":
        profile = {
            "record_type": "profile_snapshot",
            "key": "public",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-02-01T00:00:00Z"},
            "username": {"state": "present", "value": "learnwithus"},
            "bio": {"state": "present", "value": "Practical lessons for new learners"},
            **{k: {"state": "not_collected"} for k in ("display_name", "category", "positioning")},
            "declaration_basis": "unknown",
            "photo_state": "not_collected",
            "links_state": "not_collected",
            "pins_state": "not_collected",
        }
        snapshot = profile_service.import_into_application(app, profile_export([profile]))[
            "records"
        ][0]
        review = {
            "record_type": "profile_review",
            "key": "public-review",
            "account": account.model_dump(),
            "snapshot": snapshot["ref"],
            "reviewer": "Human source reviewer",
            "procedure": "Literal public-field review, not measured conversion",
            "reviewed_at": utc_now(),
            "outcome_access": "unknown",
            "criteria": [
                {
                    "key": k,
                    "verdict": "unknown",
                    "rationale": "No adequate comparative evidence supplied",
                }
                for k in CRITERIA
            ],
        }
        imported = profile_service.import_into_application(app, profile_export([review]))
    else:
        # Existing C1 fixture's permitted 16-word excerpt, not an algorithm-weight claim.
        text = "The Shorts Feed is personalized to reflect what we think you want to see next."
        document = {
            "record_type": "platform_document",
            "key": "official-source",
            "account": account.model_dump(),
            "platform": "youtube",
            "surfaces": ["shorts"],
            "publisher": "YouTube",
            "url": "https://support.google.com/youtube/answer/16089387?hl=en",
            "title": "YouTube recommendation guidance",
            "source_text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "capture_scope": "permitted_excerpt",
            "clock": {"captured_at": "2026-02-01T00:00:00Z"},
            "review_status": "reviewed",
            "reviewer": "Source reviewer",
            "review_basis": "Existing controlled permitted-excerpt fixture; "
            "not live ranking evidence",
        }
        doc = platform_service.import_into_application(app, platform_export([document]))["records"][
            0
        ]["ref"]
        statement = {
            "record_type": "platform_statement",
            "key": "official-statement",
            "account": account.model_dump(),
            "document": doc,
            "surface": "shorts",
            "start_char": 0,
            "end_char": len(text),
            "quote": text,
            "interpretation": "Official personalized-surface guidance, "
            "not a local causal experiment",
            "limitation": "No weights or guaranteed reach",
        }
        imported = platform_service.import_into_application(app, platform_export([statement]))
    record = imported["records"][0]
    return record["evidence"], [record["ref"]], imported["source_id"]


@pytest.mark.parametrize("domain", ["production", "publishing", "distribution", "profile"])
def test_nonpsychological_education_recommendation_domains_are_qualified(
    settings: Settings, account_export: Path, domain: str
) -> None:
    platform = "youtube" if domain == "distribution" else "demo"
    raw = json.loads(account_export.read_text())
    for row in raw["records"]:
        row["platform"] = platform
        for key in ("key", "metric_key"):
            if key in row:
                row[key] = row[key].replace("demo.", platform + ".")
    account_export.write_text(json.dumps(raw))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        evidence, context, source_id = inputs(app, domain, platform)
        spec = proposed(domain, evidence, context, platform=platform)
        result = service.create(app, spec)
        assert service.create(app, spec) == result
        body = result["content"]
        assert body["decision"] == "test_first" and body["expected_lift"] is None
        assert body["external_execution_authorized"] is False
        assert body["scope_conditions"]["niches"] == ["education"]
        if domain == "distribution":
            assert body["sources"][0]["lane"] == "official_guidance_not_local_effect"
        if domain == "profile":
            assert (
                body["sources"][0]["lane"] == "qualitative_profile_rubric_not_measured_conversion"
            )
        with app.database.transaction() as connection:
            doc = documents.build(connection, "evidence", result["evidence"]["revision_id"])
            assert doc and doc["claim_level"] == "testable_strategy_not_guaranteed"
            lexical.project(connection, doc)
            assert graph.neighborhood(connection, result["ref"]["revision_id"], depth=1)["nodes"]
        ref = EntityRef.model_validate(result["ref"])
    with open_application(settings) as app:
        assert service.show(app, ref)["content"] == body
        if source_id:
            with app.database.transaction() as connection:
                withdraw(connection, source_id=source_id, reason="Controlled permission withdrawal")
            with pytest.raises(ConfigurationError, match="Ineligible|Withdrawn"):
                service.show(app, ref)
            plan = audience_service.redact(app, source_id=source_id)
            audience_service.redact(
                app,
                source_id=source_id,
                confirmation=plan["confirmation"],
                reason="Controlled erasure",
            )
            with pytest.raises(ConfigurationError, match="erased|Ineligible"):
                service.show(app, ref)


def test_cited_context_cannot_bypass_scope_checks_by_omitting_context_list(
    settings: Settings, account_export: Path
) -> None:
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        evidence, _, _ = inputs(app, "publishing", "demo")
        spec = proposed("publishing", evidence, [])
        wrong = spec.model_copy(
            update={"scope": spec.scope.model_copy(update={"platform": "youtube"})}
        )
        with pytest.raises(ConfigurationError, match="platform/niche"):
            service.create(app, wrong)
        assert service.create(app, spec)["content"]["context_evidence"]


def test_originality_guarantees_and_missing_domain_context_are_refused(
    settings: Settings, account_export: Path
) -> None:
    raw = json.loads(account_export.read_text())
    caption = "Use this exact long creator script about our specific classroom demonstration today"
    next(r for r in raw["records"] if r["record_type"] == "post")["caption"] = caption
    account_export.write_text(json.dumps(raw))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        evidence, context, _ = inputs(app, "production", "demo")
        spec = proposed("production", evidence, context)
        for change, match in (
            (caption, "Copied"),
            ("This will guarantee viral reach", "guarantee"),
        ):
            bad = spec.model_copy(
                update={"actions": (spec.actions[0].model_copy(update={"change": change}),)}
            )
            with pytest.raises(ConfigurationError, match=match):
                service.create(app, bad)
        missing = proposed("profile", evidence, [])
        with pytest.raises(ConfigurationError, match="C1"):
            service.create(app, missing)
