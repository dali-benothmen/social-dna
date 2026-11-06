"""Real URL selection -> canonical imports -> R2 pipeline -> frozen report/reproduction."""

import json
import subprocess
import sys

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from socialdna.application import workflow_service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.workflow_report_service import generate
from socialdna.cli.app import app as cli
from socialdna.core.time import utc_now
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.domain.workflows import WorkflowRequest
from socialdna.storage.schema import metadata

LEFT = "https://www.instagram.com/left/"
RIGHT = "https://www.instagram.com/right/"


def imported(settings, tmp_path, *, count=6, revision=1, mature=True):
    records = [
        {
            "record_type": "metric_definition",
            "platform": "instagram",
            "key": "instagram.views.v1",
            "definition": "Consented export view count",
        }
    ]
    for owner, handle in (("001", "left"), ("002", "right")):
        records.append(
            {
                "record_type": "account",
                "platform": "instagram",
                "external_id": owner,
                "handle": handle,
                "creator_key": owner,
                "niche": "cooking",
            }
        )
        for i in range(count):
            post = f"{handle}{i}"
            records.extend(
                [
                    {
                        "record_type": "post",
                        "platform": "instagram",
                        "external_id": post,
                        "account_external_id": owner,
                        "content_type": "video",
                        "published_at": "2026-01-01T00:00:00Z",
                        "caption": "x" * (i + 1),
                        "title": f"Ordinary {revision} {post}",
                        "url": f"https://www.instagram.com/p/{post}/",
                    },
                    {
                        "record_type": "metric_snapshot",
                        "platform": "instagram",
                        "subject_external_id": post,
                        "metric_key": "instagram.views.v1",
                        "observed_at": "2026-01-08T00:00:00Z" if mature else "2026-01-02T00:00:00Z",
                        "window_start": "2026-01-01T00:00:00Z",
                        "window_end": "2026-01-08T00:00:00Z" if mature else "2026-01-02T00:00:00Z",
                        "value": (100 + i * 20) if owner == "001" else 160 - i * 5,
                    },
                ]
            )
    path = tmp_path / "comparisons.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "comparison-fixture",
                    "permission_basis": "creator_owned_export",
                    "source_uri": "urn:fixture:comparison",
                    "terms": {"revision": revision},
                },
                "records": records,
            }
        )
    )
    result = import_dataset(settings, path, "json")
    assert result["valid"], result
    return result


def design(**changes):
    return CorrectedPerformanceSpec.model_validate(
        {
            "metric_key": "instagram.views.v1",
            "design": "cross_creator",
            "estimand": "cross_creator_comparison",
            "knowledge_cutoff": utc_now(),
            "publication_cutoff": "2026-11-01T00:00:00Z",
            "features": ["caption_length"],
            "covariates": ["caption_length"],
            "context": ["platform", "content_type"],
            "model": "none",
            "feature_policy": "retrospective_content",
            "family_id": "url-comparison",
            "family_terms": ["caption_length"],
            "bootstrap_resamples": 200,
            "sampling_frame": "Bounded independently permitted library sample",
            **changes,
        }
    )


def planned(settings, **changes):
    return workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="compare",
            url=LEFT,
            against=(RIGHT,),
            question_scope="comparison_descriptive",
            goal="Compare the observed exported performance, including ordinary posts",
            **changes,
        ),
    )["workflow_id"]


def test_actual_pipeline_exact_sample_counterexamples_reload_and_reproduce(settings, tmp_path):
    imported(settings, tmp_path)
    identity = planned(settings, comparison={"design": design()})
    result = workflow_service.run(settings, identity)
    document = result["content"]
    assert result["status"] == "partial", result  # Two creators do not license inference.
    assert document["quantitative"]["method_version"] == "performance-2"
    assert document["quantitative"]["comparison"]["status"] == "supported_descriptive"
    assert document["numeric_inference"] == "withheld"
    assert any(a["code"] == "creator_generalization_withheld" for a in result["required_actions"])
    assert document["counterexamples"] and document["statistical_evidence"]
    assert all(i["selected_posts"] == 6 for i in document["inventory"])
    assert workflow_service.run(settings, identity)["content"] == document
    with open_application(settings) as app:
        assert generate(app, identity)["content"] == document
        markdown = generate(app, identity, "markdown")["content"]
        assert "Counterexamples" in markdown and "urn:fixture" not in markdown
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["statistical_analyses"])
                )
                == 1
            )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "compare",
            "reproduce",
            document["comparison_run_id"],
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stderr + process.stdout
    reproduced = json.loads(process.stdout)["data"]
    assert reproduced["analysis_configuration"]["reproduced_from"] == document["comparison_run_id"]
    assert reproduced["results"] == document["quantitative"]


def test_post_urls_can_complete_a_finite_descriptive_question(settings, tmp_path):
    imported(settings, tmp_path)
    request = WorkflowRequest(
        mode="compare",
        url="https://www.instagram.com/p/left0/",
        against=("https://www.instagram.com/p/left1/",),
        question_scope="comparison_descriptive",
        goal="Describe these two exported observations, without creator-wide inference",
        comparison={"design": design(design="descriptive", estimand="descriptive")},
    )
    identity = workflow_service.plan(settings, request)["workflow_id"]
    result = workflow_service.run(settings, identity)
    assert result["status"] == "success", result
    assert result["content"]["quantitative"]["available_n"] == 2
    assert result["content"]["numeric_inference"] == "descriptive_only"


@pytest.mark.parametrize(
    "case",
    [
        "no_design",
        "incompatible_platform",
        "missing_source",
        "immature",
        "sparse",
        "missing_denominator",
        "incompatible_window",
    ],
)
def test_unsupported_comparisons_are_honestly_partial(settings, tmp_path, case):
    imported(settings, tmp_path, count=1 if case == "sparse" else 6, mature=case != "immature")
    changes = {"comparison": {"design": design()}}
    if case == "no_design":
        changes = {}
    if case == "missing_denominator":
        changes = {"comparison": {"design": design(denominator_key="instagram.missing.v1")}}
    if case == "incompatible_window":
        changes = {"comparison": {"design": design(window_seconds=3600)}}
    if case == "incompatible_platform":
        changes["against"] = ("https://www.tiktok.com/@right",)
    if case == "missing_source":
        changes["against"] = ("https://www.instagram.com/unknown/",)
    request = WorkflowRequest(
        mode="compare",
        url=LEFT,
        against=changes.pop("against", (RIGHT,)),
        question_scope="comparison_descriptive",
        **changes,
    )
    identity = workflow_service.plan(settings, request)["workflow_id"]
    result = workflow_service.run(settings, identity)
    assert result["status"] == "partial" and result["required_actions"]
    assert result["content"]["numeric_inference"] == "withheld"
    assert not result["content"]["request_fulfilled"]


def test_cli_dry_run_bounds_and_exact_frozen_plan(settings, tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "workflow",
            "plan",
            "--mode",
            "compare",
            "--url",
            LEFT,
            "--against",
            RIGHT,
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not settings.data_dir.exists()
    imported(settings, tmp_path)
    identity = planned(settings, max_posts=2)
    imported(settings, tmp_path, revision=2)
    result = workflow_service.run(settings, identity)
    assert all(i["omitted_by_limit"] == 4 for i in result["content"]["inventory"])
    assert all(
        "Ordinary 1" in p["title"] for i in result["content"]["inventory"] for p in i["posts"]
    )
    with open_application(settings) as app:
        assert generate(app, identity)["freshness"]["superseded_inputs"]


def test_committed_statistical_checkpoint_resumes_without_another_test_attempt(
    settings, tmp_path, monkeypatch
):
    from socialdna.application import performance_service

    imported(settings, tmp_path)
    identity = planned(settings, comparison={"design": design()})
    original = performance_service.compare

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Injected interruption after the atomic statistical checkpoint")

    monkeypatch.setattr(performance_service, "compare", interrupted)
    with pytest.raises(RuntimeError):
        workflow_service.run(settings, identity)

    def refuse_refit(*args, **kwargs):
        pytest.fail("Resume must reuse the actual committed run")

    monkeypatch.setattr(performance_service, "compare", refuse_refit)
    result = workflow_service.run(settings, identity)
    assert result["content"]["comparison_run_id"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["statistical_analyses"])
                )
                == 1
            )


def test_qualified_literature_and_original_proposal_then_invalid_review_refusal(settings, tmp_path):
    from pathlib import Path

    from test_recommendations import proposed

    from socialdna.application import literature_service
    from socialdna.domain.investigation import LiteratureCorpus

    imported(settings, tmp_path)
    corpus_path = Path(__file__).parents[2] / "examples/research/literature.json"
    corpus = LiteratureCorpus.model_validate_json(corpus_path.read_text())
    with open_application(settings) as app:
        sources = literature_service.import_corpus(app, corpus)
    refs = list(sources["findings"].values())
    citation = next(iter(sources["citations"].values()))
    proposal = proposed("production", citation, [], platform="instagram")
    identity = planned(
        settings,
        comparison={
            "support_revisions": (refs[0]["revision_id"],),
            "contrary_revisions": (refs[-1]["revision_id"],),
            "recommendation": proposal,
        },
    )
    result = workflow_service.run(settings, identity)
    lanes = result["content"]["sources"]
    assert {s["role"] for s in lanes} == {"support", "counterevidence", "proposal"}
    assert lanes[0]["lane"] == "reviewed_external_literature_not_local_replication"
    assert lanes[-1]["lane"] == "proposed_test_not_guaranteed"
    assert result["content"]["inventory"] and result["status"] == "partial"
    raw = corpus.model_dump(mode="json")
    for study in raw["studies"]:
        study["review_status"] = "unverified"
    with open_application(settings) as app:
        literature_service.import_corpus(app, LiteratureCorpus.model_validate(raw))
    refused = planned(
        settings,
        comparison={"support_revisions": (refs[0]["revision_id"],), "recommendation": proposal},
    )
    output = workflow_service.run(settings, refused)
    assert output["content"]["inventory"] and not output["content"]["sources"]
    assert {a["code"] for a in output["required_actions"]} >= {
        "prepared_source_withheld",
        "recommendation_withheld",
    }


def test_native_only_capture_cannot_be_laundered_into_comparison(settings, monkeypatch):
    from test_source_workflows import URL, capture

    from socialdna.application import workflow_maintenance

    monkeypatch.setenv("SOCIALDNA_YOUTUBE_API_KEY", "local-test-secret")
    monkeypatch.setattr(workflow_maintenance, "verified", lambda _: True)
    native = workflow_service.plan(settings, WorkflowRequest(url=URL))["workflow_id"]
    capture(settings, native)
    request = WorkflowRequest(
        mode="compare", url=URL, against=("https://www.youtube.com/shorts/AbCdefGhI12",)
    )
    identity = workflow_service.plan(settings, request)["workflow_id"]
    result = workflow_service.run(settings, identity)
    assert result["status"] == "partial" and not result["content"]["inventory"]
    assert "A &lt;script&gt; story" not in json.dumps(result)
    assert result["content"]["numeric_inference"] == "withheld"
