"""Offline vertical slice using actual media/import/comparison/citation services.

Generated clip labels test software contracts, not cooking recognition or psychology.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from socialdna.application import (
    audience_service,
    behavioral_service,
    literature_service,
    query_service,
)
from socialdna.application import investigation_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.creative_service import import_into_application
from socialdna.application.evidence_service import ClaimValidator, EvidenceResolver, withdraw
from socialdna.application.performance_service import analyze_account, compare
from socialdna.application.research_service import register_research, show_research
from socialdna.audience.annotations import AnnotationSet
from socialdna.audience.collections import CollectionSpec
from socialdna.cli.app import app as cli
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.behavioral import BehavioralExport
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus, ResearchProtocol
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.memory import QuerySpec
from socialdna.domain.research import CorrectedPerformanceSpec, PerformanceSpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import database_checks, evidence_checks
from socialdna.storage.schema import metadata

CORPUS = Path(__file__).parents[2] / "examples/research/literature.json"
ACCOUNT = stable_id("account", "demo", "0001")


def design(**changes: Any) -> CorrectedPerformanceSpec:
    return CorrectedPerformanceSpec.model_validate(
        {
            "metric_key": "demo.views.v1",
            "estimand": "within_creator_association",
            "design": "within_creator",
            "feature_policy": "retrospective_content",
            "knowledge_cutoff": utc_now(),
            "publication_cutoff": "2026-11-01T00:00:00Z",
            "sampling_frame": "All permitted fixture posts, including failures and unknown labels",
            "features": ["caption_length"],
            "covariates": ["caption_length"],
            "family_id": "cooking-research-family",
            "family_terms": ["caption_length"],
            "bootstrap_resamples": 200,
            "model": "ols",
            **changes,
        }
    )


def registration(settings: Settings, tmp_path: Path) -> dict[str, Any]:
    path = tmp_path / "question.json"
    path.write_text(
        json.dumps(
            {
                "key": "cooking-opening",
                "question": "Why might result-first cooking openings work?",
                "population": "Permitted fixture cooking posts, not a representative real corpus",
                "hypotheses": [
                    {"key": k, "statement": s, "population": "Fixture cooking posts"}
                    for k, s in (
                        ("curiosity", "A knowledge gap may encourage watching."),
                        ("sensory", "Sensory appeal may explain the same outcome."),
                        ("context", "Publishing or production context may confound it."),
                    )
                ],
            }
        )
    )
    return register_research(settings, path)


def protocol(
    registered: dict[str, Any],
    imported: dict[str, Any],
    feature: str = "caption_length",
    **changes: Any,
) -> ResearchProtocol:
    plans = []
    for i, ref in enumerate(registered["hypotheses"]):
        plans.append(
            {
                "hypothesis": ref,
                "explanation": "contextual" if i == 2 else "psychological",
                "prediction": {
                    "feature": feature,
                    "metric_key": "demo.views.v1",
                    "direction": "positive",
                    "contrast": "Opening-associated contrast",
                    "falsifier": "A null/reversed contrast in a suitable independent sample",
                    "discriminating_measurement": "Curiosity versus sensory ratings under "
                    "a separately authorized matched manipulation",
                },
                "confounders": ["Topic, audience, paid exposure and packaging"],
                "scope_conditions": ["The frozen authorized fixture and outcome window only"],
                **(
                    {
                        "construct_ref": imported["constructs"]["epistemic-curiosity"],
                        "operationalization": imported["operationalizations"]["curiosity-plan"],
                        "literature": [
                            {
                                "finding": imported["citations"]["kang2009.curiosity"],
                                "applicability": "indirect",
                                "reviewer": "fixture reviewer",
                                "rationale": "Trivia tasks do not directly test cooking openings",
                            }
                        ],
                    }
                    if i == 0
                    else {}
                ),
            }
        )
    return ResearchProtocol.model_validate(
        {
            "key": "cooking-rivals",
            "question": registered["question"],
            "hypotheses": plans,
            "population": "All selected SQL-manifest posts, not nearest-neighbor results",
            "production_context": "Unknown beyond actual measured/reviewed content",
            "distribution_context": "Private traffic/eligibility unavailable",
            "publishing_context": "UTC metadata only; local cadence unknown",
            "profile_context": "Historical profile conversion unavailable",
            "experiment_design": "Separately manipulate information gap while matching appearance; "
            "measure curiosity and sensory response before interpreting any mediator.",
            "treatment_variants": ["Finished-meal opening", "Preparation-first opening"],
            **changes,
        }
    )


@pytest.fixture
def library(settings: Settings, account_export: Path, tmp_path: Path) -> dict[str, Any]:
    data = json.loads(account_export.read_text())
    data["source"]["comments_permitted"] = True
    published = {
        r["external_id"]: r["published_at"] for r in data["records"] if r["record_type"] == "post"
    }
    for row in data["records"]:
        if row["record_type"] == "metric_snapshot" and row.get("subject_type", "post") == "post":
            row["window_start"] = published[row["subject_external_id"]]
            row["window_end"] = row["observed_at"]
    data["records"].append(
        {
            "record_type": "comment",
            "platform": "demo",
            "post_external_id": "p0",
            "external_id": "cooking-comment",
            "body": "I will cook this!",
            "published_at": "2026-01-02T00:00:00Z",
        }
    )
    account_export.write_text(json.dumps(data))
    imported_data = import_dataset(settings, account_export, "json")
    registered = registration(settings, tmp_path)
    with open_application(settings) as app:
        corpus = literature_service.import_corpus(
            app, literature_service.read_spec(CORPUS, LiteratureCorpus)
        )
        prepared = service.prepare(app, protocol(registered, corpus))
        analysis = analyze_account(app, ACCOUNT, design())
    return {
        "corpus": corpus,
        "protocol": prepared["protocol"],
        "analysis": analysis,
        "registered": registered,
        "source_id": imported_data["source_id"],
    }


def evaluation(library: dict[str, Any], **changes: Any) -> EvaluationSpec:
    return EvaluationSpec.model_validate(
        {
            "protocol": library["protocol"],
            "analysis_run_ids": [library["analysis"]["run_id"]],
            **changes,
        }
    )


def test_immutable_inconclusive_assessment_reports_restart_and_memory(
    settings: Settings,
    library: dict[str, Any],
) -> None:
    with open_application(settings) as app:
        first = service.evaluate(app, evaluation(library))
        second = service.evaluate(app, evaluation(library))
        assert first == second and first["claim_level"] == "hypothesis"
        ref = EntityRef.model_validate(first["assessment"])
        record = service.show_record(app, ref)["content"]
        assert [j["mechanism_status"] for j in record["judgments"]] == [
            "non_discriminating",
            "unsupported_literature",
            "not_applicable",
        ]
        assert all(j["local_association"]["status"] == "inconclusive" for j in record["judgments"])
        assert record["population_manifests"][0]["post_ids"] == [
            p["post_id"] for p in library["analysis"]["posts"]
        ]
        assert not record["population_manifests"][0]["independent_confirmation"]
        report = service.assessment_report(app, ref)
        assert report["content"]["bibliography"]
        assert report["content"]["bibliography"][0]["reviewed_finding"]["limitations"]
        assert (
            report["content"]["judgments"][0]["local_association"]["observations"][0]["limitations"]
            == library["analysis"]["limitations"]
        )
        assert report["content"]["experiment_proposal"]["status"] == "proposed_not_executed"
        frozen = Path(report["artifact"]["path"]).read_bytes()
        markdown = service.assessment_report(app, ref, "markdown")
        assert "No psychological mediator" in markdown["content"]
        assert all(c.status != "error" for c in database_checks(app) + evidence_checks(app))
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["test_attempts"])
                )
                == 1
            )
    with open_application(settings) as app:
        assert show_research(app, ref.id)["content"] == record
        assert service.assessment_report(app, ref)["artifact"] == report["artifact"]
        assert Path(report["artifact"]["path"]).read_bytes() == frozen
        hits = query_service.query(app, QuerySpec(text="trivia", family="research_knowledge"))
        assert hits["hits"]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--offline",
            "--format",
            "json",
            "research",
            "show",
            ref.id,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["data"]["content"] == record
    directory = settings.data_dir.parent
    protocol_path, evaluation_path = directory / "protocol.json", directory / "evaluation.json"
    protocol_path.write_text(protocol(library["registered"], library["corpus"]).model_dump_json())
    evaluation_path.write_text(evaluation(library).model_dump_json())
    for command, path in (("prepare", protocol_path), ("evaluate", evaluation_path)):
        invoked = CliRunner().invoke(
            cli,
            [
                "--data-dir",
                str(settings.data_dir),
                "--offline",
                "--format",
                "json",
                "research",
                command,
                "--spec",
                str(path),
            ],
        )
        assert invoked.exit_code == 0, invoked.stdout
        data = json.loads(invoked.stdout)["data"]
        assert data["protocol" if command == "prepare" else "assessment"] == (
            library["protocol"] if command == "prepare" else first["assessment"]
        )


def test_withdrawal_revokes_assessment_and_all_derived_findings(
    settings: Settings,
    library: dict[str, Any],
) -> None:
    with open_application(settings) as app:
        result = service.evaluate(app, evaluation(library))
        assessment = EntityRef.model_validate(result["assessment"])
        service.assessment_report(app, assessment)
        with app.database.transaction() as connection:
            finding = EntityRef.model_validate(library["corpus"]["findings"]["kang2009.curiosity"])
            source = EvidenceRepository(connection).entity(finding)["source_id"]
            citation = EvidenceRef.model_validate(result["findings"][0]["evidence"])
            withdraw(connection, source_id=source, reason="Review permission withdrawn")
            assert not EvidenceResolver(connection).resolve(citation).eligible
        assert service.show_record(app, assessment)["content"] is None
        with pytest.raises(ConfigurationError, match="withheld"):
            service.assessment_report(app, assessment)
        with pytest.raises(ConfigurationError, match="Ineligible"):
            service.evaluate(app, evaluation(library))
        hits = query_service.query(app, QuerySpec(text="trivia", family="research_knowledge"))
        assert not any(h["owner"]["id"] == finding.id for h in hits["hits"])


@pytest.mark.parametrize(
    "review_status,publication_status",
    [
        ("unverified", "current"),
        ("reviewed", "retracted"),
    ],
)
def test_unverified_or_retracted_sources_are_not_eligible(
    settings: Settings,
    review_status: str,
    publication_status: str,
) -> None:
    document = json.loads(CORPUS.read_text())
    document["studies"][0].update(
        review_status=review_status, publication_status=publication_status
    )
    with open_application(settings) as app:
        corpus = literature_service.import_corpus(app, LiteratureCorpus.model_validate(document))
        with app.database.transaction() as connection:
            citation = EvidenceRef.model_validate(corpus["citations"]["kang2009.curiosity"])
            assert not EvidenceResolver(connection).resolve(citation).eligible
            with pytest.raises(ConfigurationError, match="Ineligible"):
                EvidenceResolver(connection).resolve(citation, purpose="new_claim")


def test_claim_gates_and_legacy_rejection(settings: Settings, library: dict[str, Any]) -> None:
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError, match="requested association"):
            service.evaluate(app, evaluation(library, expected_claim_level="association"))
        legacy = analyze_account(app, ACCOUNT, PerformanceSpec(metric_key="demo.views.v1"))
        with pytest.raises(ConfigurationError, match="version-2"):
            service.evaluate(app, evaluation(library, analysis_run_ids=[legacy["run_id"]]))
        with app.database.transaction() as connection:
            ref = EvidenceRef.model_validate(library["corpus"]["citations"]["kang2009.curiosity"])
            with pytest.raises(ConfigurationError, match="causal"):
                ClaimValidator(connection).validate_research("causal", (ref,))
            with pytest.raises(ConfigurationError, match="statistical term"):
                ClaimValidator(connection).validate_research("association", (ref,))


@pytest.mark.parametrize("change", ["retracted", "corrected", "unverified"])
def test_later_source_status_revokes_old_assessment_without_rewriting_it(
    settings: Settings,
    library: dict[str, Any],
    change: str,
) -> None:
    with open_application(settings) as app:
        result = service.evaluate(app, evaluation(library))
        ref = EntityRef.model_validate(result["assessment"])
        saved = service.assessment_report(app, ref)
        original = Path(saved["artifact"]["path"]).read_bytes()
        document = json.loads(CORPUS.read_text())
        if change == "unverified":
            document["studies"][0]["review_status"] = change
        else:
            document["studies"][0]["publication_status"] = change
        literature_service.import_corpus(app, LiteratureCorpus.model_validate(document))
        assert service.show_record(app, ref)["status"] == "withheld"
        assert Path(saved["artifact"]["path"]).read_bytes() == original


def test_wrong_question_irrelevant_literature_and_nonstudy_citations(
    settings: Settings,
    library: dict[str, Any],
) -> None:
    with open_application(settings) as app:
        document = protocol(library["registered"], library["corpus"]).model_dump(mode="json")
        document["hypotheses"] = document["hypotheses"][:2]
        with pytest.raises(ConfigurationError, match="all registered rival"):
            service.prepare(app, ResearchProtocol.model_validate(document))
        document = protocol(library["registered"], library["corpus"]).model_dump(mode="json")
        document["hypotheses"][0]["literature"][0]["applicability"] = "not_applicable"
        prepared = service.prepare(app, ResearchProtocol.model_validate(document))
        result = service.evaluate(app, evaluation(library, protocol=prepared["protocol"]))
        content = service.show_record(app, EntityRef.model_validate(result["assessment"]))[
            "content"
        ]
        assert content["judgments"][0]["literature"]["status"] == "unsupported"
        document["hypotheses"][0]["literature"][0]["finding"] = library["analysis"][
            "statistical_evidence"
        ][0]["ref"]
        with pytest.raises(ConfigurationError, match="study excerpt"):
            service.prepare(app, ResearchProtocol.model_validate(document))
        document = protocol(library["registered"], library["corpus"]).model_dump(mode="json")
        document["question"]["revision_id"] = library["registered"]["hypotheses"][0]["revision_id"]
        with pytest.raises(ConfigurationError, match="kind/identity"):
            service.prepare(app, ResearchProtocol.model_validate(document))


def test_reviewed_media_and_sampled_reactions_join_real_cooking_workflow(
    settings: Settings,
    library: dict[str, Any],
    video: Path,
    tmp_path: Path,
) -> None:
    # Add an authorized media reference, then let the real batch pipeline bind it.
    path = tmp_path / "media.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "cooking-media",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:fixture:video",
                },
                "records": [
                    {
                        "record_type": "media",
                        "platform": "demo",
                        "post_external_id": "p0",
                        "uri": str(video),
                    }
                ],
            }
        )
    )
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        batch = analyze_account(
            app,
            ACCOUNT,
            design(model="none"),
            analyze_media=True,
            media_options=AnalysisOptions(no_ai=True, depth="quick"),
        )
        assert any(r["status"] == "success" for r in batch["batch"])
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            media = connection.execute(select(metadata.tables["media_assets"])).mappings().first()
            assert media is not None
            post = repo.latest("post", stable_id("post", "demo", "p0"))
            comment_id = connection.scalar(select(metadata.tables["comments"].c.id))
            comment = repo.latest("comment", comment_id)
            assert post and comment
        annotation = CreativeAnnotationSet.model_validate(
            {
                "key": "cooking-review",
                "media_sha256": media["sha256"],
                "permission_basis": "Controlled fixture annotation, not detector validation",
                "protocol": {
                    "origin": "human",
                    "author": "reviewer",
                    "procedure": "opening review",
                    "outcome_access": "blinded",
                    "label_frozen_before_outcomes": True,
                },
                "coverage": [
                    {
                        "modality": "visual",
                        "techniques": [
                            "finished_dish",
                            "preparation_instruction",
                            "ingredient_display",
                        ],
                        "mode": "exhaustive_review",
                        "intervals": [{"start_ms": 0, "end_ms": 3000}],
                        "limitation": "Generated-clip assertion only",
                    }
                ],
                "events": [
                    {
                        "key": "dish",
                        "technique": "finished_dish",
                        "description": "Fixture dish",
                        "modalities": ["visual"],
                        "state": "reviewed",
                        "reviewer": "reviewer",
                        "anchors": [
                            {
                                "start_min_ms": 0,
                                "start_max_ms": 0,
                                "end_min_ms": 800,
                                "end_max_ms": 800,
                            }
                        ],
                    }
                ],
            }
        )
        creative = import_into_application(app, annotation)
        collection = audience_service.import_into_application(
            app,
            CollectionSpec.model_validate(
                {
                    "key": "cooking-comments",
                    "permission_basis": "Authorized fixture comment review",
                    "source_uri": "urn:fixture:comments",
                    "posts": [post.model_dump()],
                    "members": [{"comment": comment.model_dump()}],
                    "collected_at": utc_now(),
                    "ordering": "ranked",
                    "sampling_method": "ranked",
                    "completeness": "partial",
                    "declared_frame": "One ranked supplied comment; not audience prevalence",
                    "pagination_complete": False,
                    "truncated": True,
                    "supplied_count": 1,
                    "deleted_moderated_coverage": "Unknown",
                    "retention": "authorized_retention",
                }
            ),
        )
        reactions = audience_service.import_into_application(
            app,
            AnnotationSet.model_validate(
                {
                    "key": "cooking-reactions",
                    "collection": collection["ref"],
                    "permission_basis": "Authorized fixture review",
                    "protocol": {
                        "origin": "human",
                        "author": "reviewer",
                        "procedure": "literal-intention rubric",
                        "outcome_access": "blinded",
                    },
                    "annotations": [
                        {
                            "key": "intention",
                            "comment": comment.model_dump(),
                            "start_char": 0,
                            "end_char": 17,
                            "quote": "I will cook this!",
                            "labels": ["expressed_intention"],
                            "state": "reviewed",
                            "reviewer": "reviewer",
                            "rationale": "Explicit intention, not behavior",
                        }
                    ],
                }
            ),
        )
        prepared = service.prepare(
            app, protocol(library["registered"], library["corpus"], feature="creative.result_first")
        )
        spec = design(
            features=["creative.result_first", "caption_length"],
            family_terms=["creative.result_first", "caption_length"],
            family_id="cooking-creative-family",
            creative_annotation_key="cooking-review",
            creative_recipes={"creative.result_first": "creative.result_first.v1"},
        )
        posts = [stable_id("post", "demo", f"p{i}") for i in range(6)]
        within = compare(app, "posts", posts[:3], posts[3:], spec)
        cross = compare(
            app,
            "posts",
            posts[:3],
            posts[3:],
            design(
                **{
                    **spec.model_dump(),
                    "family_id": "cooking-cross-family",
                    "design": "cross_creator",
                    "estimand": "cross_creator_comparison",
                    "model": "none",
                }
            ),
        )
        owner_document = json.loads(
            (CORPUS.parent.parent / "behavioral/definitions.json").read_text()
        )
        with app.database.transaction() as connection:
            account = EvidenceRepository(connection).latest("account", ACCOUNT)
            assert account is not None
        owner_document["records"][-1]["account"] = account.model_dump()
        owner_document["source"]["source_uri"] = "urn:fixture:owned-retention"
        owner_document["records"] = [
            r for r in owner_document["records"] if r["key"] != "demo.followers.behavior.v1"
        ]
        owner_document["records"][0].update(
            numerator_definition="Synthetic repeat-inclusive watch events",
            denominator_definition="Synthetic eligible play starts",
            source_definition_uri="urn:fixture:repeat-inclusive-watch-definition",
            description="Controlled software fixture, not measured platform retention",
        )
        owner_document["records"][-1].update(
            known=True,
            eligibility="All source-defined fixture plays",
            aggregation_limitations="Synthetic aggregate grid, not independent viewers",
        )
        imported_owner = behavioral_service.import_into_application(
            app, BehavioralExport.model_validate(owner_document)
        )
        owner_refs = {r["key"]: r["ref"] for r in imported_owner["records"]}
        retention_document = {
            "schema_version": "2.0",
            "source": owner_document["source"],
            "records": [
                {
                    "record_type": "metric_series",
                    "key": "fixture-retention",
                    "subject": post.model_dump(),
                    "definition": owner_refs["demo.retention.v1"],
                    "cohort": owner_refs["owned-account-all.v1"],
                    "clock": {
                        "window_start": "2026-01-01T00:00:00Z",
                        "window_end": "2026-01-08T00:00:00Z",
                        "collected_at": utc_now(),
                    },
                    "coordinate_kind": "normalized_progress",
                    "resolution": "Two halves",
                    "convention": "half_open_intervals",
                    "expected_bins": 2,
                    "completeness": "complete_for_declared_grid",
                    "bins": [
                        {"ordinal": 0, "start": 0, "end": 0.5, "measurement": {"value": 1.1}},
                        {"ordinal": 1, "start": 0.5, "end": 1, "measurement": {"value": 0.4}},
                    ],
                }
            ],
        }
        retention = behavioral_service.import_into_application(
            app, BehavioralExport.model_validate(retention_document)
        )
        evidence = [
            creative["events"][0]["evidence"],
            reactions["reactions"][0]["evidence"],
            retention["records"][0]["evidence"],
        ]
        result = service.evaluate(
            app,
            EvaluationSpec.model_validate(
                {
                    "protocol": prepared["protocol"],
                    "analysis_run_ids": [within["run_id"], cross["run_id"]],
                    "evidence": evidence,
                }
            ),
        )
        saved = service.show_record(app, EntityRef.model_validate(result["assessment"]))["content"]
        assert len(saved["supplementary_evidence"]) == 3
        assert saved["judgments"][0]["counterexamples"][0]["unsuccessful_uses"] == [posts[0]]
        assert saved["judgments"][0]["local_association"]["status"] == "inconclusive"
        assert result["claim_level"] == "hypothesis"  # tiny fixture, not a proved mechanism
        ref = EntityRef.model_validate(result["assessment"])
        rendered = service.assessment_report(app, ref)
        plan = audience_service.redact(app, comment_id=comment.id)
        audience_service.redact(
            app,
            comment_id=comment.id,
            confirmation=plan["confirmation"],
            reason="Remove fixture audience content",
        )
        assert service.show_record(app, ref)["status"] == "withheld"
        assert not Path(rendered["artifact"]["path"]).exists()


@pytest.mark.parametrize("signal", [40, 0, -40])
def test_actual_pipeline_association_and_opposite_prediction(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
    signal: int,
) -> None:
    records: list[dict[str, Any]] = []
    for creator in range(22):
        account = f"creator-{creator}"
        records.append(
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": account,
                "creator_key": account,
                "niche": "cooking",
            }
        )
        for index in range(8):
            post = f"{account}-{index}"
            published = datetime.fromisoformat("2026-01-01T00:00:00+00:00") + timedelta(days=index)
            value = 500 + signal * index + ((creator * 7 + index * 13) % 17)
            records.extend(
                [
                    {
                        "record_type": "post",
                        "platform": "demo",
                        "external_id": post,
                        "account_external_id": account,
                        "published_at": published.isoformat(),
                        "caption": "x" * (index + 1),
                    },
                    {
                        "record_type": "metric_snapshot",
                        "platform": "demo",
                        "subject_external_id": post,
                        "metric_key": "demo.views.v1",
                        "value": value,
                        "observed_at": (published + timedelta(days=7)).isoformat(),
                        "window_start": published.isoformat(),
                        "window_end": (published + timedelta(days=7)).isoformat(),
                    },
                ]
            )
    path = tmp_path / "many-creators.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "synthetic-independent-creators",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:fixture:many-creators",
                },
                "records": records,
            }
        )
    )
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        ids = [stable_id("account", "demo", f"creator-{c}") for c in range(22)]
        report = compare(app, "accounts", ids[:11], ids[11:], design(family_id="positive-family"))
        changed = protocol(library["registered"], library["corpus"]).model_dump(mode="json")
        changed["key"] = "opposed-predictions"
        changed["hypotheses"][1]["prediction"]["direction"] = "negative"
        prepared = service.prepare(app, ResearchProtocol.model_validate(changed))
        result = service.evaluate(
            app,
            EvaluationSpec.model_validate(
                {
                    "protocol": prepared["protocol"],
                    "analysis_run_ids": [report["run_id"]],
                    "expected_claim_level": "association" if signal else "hypothesis",
                }
            ),
        )
        content = service.show_record(app, EntityRef.model_validate(result["assessment"]))[
            "content"
        ]
        expected = (
            ("consistent", "contrary")
            if signal > 0
            else (("contrary", "consistent") if signal < 0 else ("inconclusive", "inconclusive"))
        )
        assert content["judgments"][0]["local_association"]["status"] == expected[0]
        assert content["judgments"][1]["local_association"]["status"] == expected[1]
        assert content["judgments"][0]["counterexamples"][0]["status"] == (
            "not_a_binary_creative_feature"
        )
        assert all(j["causal_identification"] == "not_identified" for j in content["judgments"])
        with app.database.transaction() as connection:
            links = metadata.tables["evidence_links"]
            roles = set(
                connection.scalars(
                    select(links.c.role).where(
                        links.c.owner_revision_id.in_(
                            [f["ref"]["revision_id"] for f in result["findings"]]
                        ),
                        links.c.scope_revision_id
                        == library["registered"]["question"]["revision_id"],
                    )
                )
            )
        if signal:
            assert {"supporting", "contradicting"} <= roles
        else:
            assert "non_discriminating" in roles
            assert not roles & {"supporting", "contradicting"}
