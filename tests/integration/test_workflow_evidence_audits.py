import json
import subprocess
import sys

import pytest
from sqlalchemy import select
from test_psychological_research import evaluation
from test_psychological_research import library as library
from test_research_reevaluation import append_posts
from test_url_comparisons import design, imported, planned

from socialdna.application import workflow_service
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import withdraw
from socialdna.application.workflow_report_service import generate
from socialdna.core.exceptions import SocialDNAError
from socialdna.core.ids import new_id
from socialdna.domain.evidence import ContentLocator, EntityRef
from socialdna.domain.workflows import WorkflowRequest
from socialdna.storage import content_repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def audit(settings, **kwargs):
    identity = workflow_service.plan(
        settings,
        WorkflowRequest(
            mode="evidence",
            goal="Explain the exact source records and preserved contradictions",
            **kwargs,
        ),
    )["workflow_id"]
    return identity, workflow_service.run(settings, identity)


def test_exact_sql_audit_works_without_indexes_with_bounded_graph_and_reload(settings, tmp_path):
    imported(settings, tmp_path)
    comparison = planned(settings, comparison={"design": design()})
    result = workflow_service.run(settings, comparison)
    identity, report = audit(
        settings, from_workflow=comparison, audit={"depth": 2, "include_graph": True}
    )
    document = report["content"]
    assert document["root"] == result["report"]
    assert document["nodes"] and document["citations"]
    assert any(c["locator_kind"] == "statistical_result" for c in document["citations"])
    assert document["graph"]["pending_changes"] > 0
    assert document["nodes"][0]["declared_conclusion"]["counterexamples"]
    assert not report["network_attempted"]
    with open_application(settings) as app:
        assert generate(app, identity)["content"] == document
        assert "Exact evidence audit" in generate(app, identity, "markdown")["content"]
        from socialdna.application import query_service

        query_service.reconcile(app, limit=1000)
    _, indexed = audit(
        settings, from_workflow=comparison, audit={"depth": 1, "include_graph": True}
    )
    assert indexed["content"]["graph"]["edges"]
    alias = workflow_service.plan(settings, WorkflowRequest(mode="report", from_workflow=identity))[
        "workflow_id"
    ]
    assert workflow_service.run(settings, alias)["content"] == document
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "workflow",
            "report",
            identity,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode in (0, 5), process.stderr + process.stdout
    assert json.loads(process.stdout)["data"]["content"] == document
    _, bounded = audit(
        settings, from_workflow=comparison, audit={"depth": 0, "max_nodes": 1, "max_edges": 2}
    )
    assert bounded["status"] == "partial" and bounded["content"]["truncated"]
    assert len(bounded["content"]["nodes"]) == 1 and len(bounded["content"]["edges"]) <= 2


def test_exact_evidence_duplicates_and_no_implicit_latest(settings, tmp_path):
    imported(settings, tmp_path)
    comparison = planned(settings)
    source = workflow_service.run(settings, comparison)
    root = EntityRef.model_validate(source["report"])
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            original = content_repository.cite(connection, root)
            second = repo.save_evidence(
                new_id(), ContentLocator(subject=root), repo.entity(root)["provenance_id"]
            )
            connection.execute(
                metadata.tables["content_evidence_bindings"]
                .insert()
                .values(
                    evidence_revision_id=second.revision_id, subject_revision_id=root.revision_id
                )
            )
    identity, result = audit(settings, evidence_reference=original)
    assert result["content"]["requested_evidence"] == original.model_dump()
    assert result["content"]["duplicates"], result
    assert any(second.model_dump() in row["references"] for row in result["content"]["duplicates"])
    _, limited = audit(settings, evidence_reference=original, audit={"depth": 0, "max_edges": 1})
    assert limited["status"] == "partial" and limited["content"]["truncated"]
    assert len(limited["content"]["citations"]) == 1
    imported(settings, tmp_path, revision=2)
    with open_application(settings) as app:
        assert generate(app, identity)["content"] == result["content"]
        assert generate(app, identity)["freshness"]["superseded_inputs"]


def test_withdrawal_and_confirmed_erasure_withhold_audit_and_comparison(settings, tmp_path):
    from socialdna.storage.audience_retention import begin, preview, resume

    imported_result = imported(settings, tmp_path)
    comparison = planned(settings, comparison={"design": design()})
    result = workflow_service.run(settings, comparison)
    identity, _ = audit(settings, from_workflow=comparison)
    source = imported_result["source_id"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            composed_source = EvidenceRepository(connection).entity(
                EntityRef.model_validate(result["report"])
            )["source_id"]
            withdraw(connection, source_id=source, reason="Creator withdrew this export")
        for workflow in (comparison, identity):
            with pytest.raises(SocialDNAError):
                generate(app, workflow)
    _, refused = audit(settings, entity_revision=result["report"]["revision_id"])
    assert refused["status"] == "partial" and "content" not in refused
    assert "Ordinary" not in json.dumps(refused)
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            deletion = preview(connection, source_id=composed_source)
            begin(
                connection,
                deletion,
                confirmation=deletion["confirmation"],
                reason="Owner deletion",
                actor="fixture",
            )
        resume(app.database, app.paths)
        with pytest.raises(SocialDNAError):
            generate(app, identity)
        with app.database.transaction() as connection:
            entities, compositions = (
                metadata.tables["entity_revisions"],
                metadata.tables["content_records"],
            )
            texts = list(
                connection.scalars(
                    select(entities.c.payload_json).join(
                        compositions, compositions.c.revision_id == entities.c.id
                    )
                )
            )
            assert not any("Ordinary 1" in text for text in texts)


def test_real_reevaluation_history_keeps_exact_old_root_and_no_audit_refit(
    settings, library, tmp_path
):
    from sqlalchemy import func

    from socialdna.application import investigation_service, reevaluation_service

    with open_application(settings) as app:
        old = investigation_service.evaluate(app, evaluation(library))["assessment"]
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        revised = reevaluation_service.reevaluate(app, old["id"])
        assert revised["analyses_run"] == 1
        with app.database.transaction() as connection:
            before = connection.scalar(
                select(func.count()).select_from(metadata.tables["statistical_analyses"])
            )
    identity, result = audit(
        settings, entity_revision=old["revision_id"], audit={"depth": 0, "max_nodes": 1}
    )
    history = result["content"]["research_history"]
    assert result["content"]["root"] == old
    assert len(history["assessments"]) == 2 and len(history["transitions"]) == 1
    assert history["assessments"][0]["comparison"] is None
    assert history["assessments"][1]["comparison"]
    with open_application(settings) as app:
        assert generate(app, identity)["content"] == result["content"]
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["statistical_analyses"])
                )
                == before
            )
