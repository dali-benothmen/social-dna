"""Incremental learning through actual imports, feature materialization and statistics."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_psychological_research import ACCOUNT, CORPUS, design, evaluation, protocol
from test_psychological_research import library as library
from typer.testing import CliRunner

from socialdna.application import (
    audience_service,
    investigation_service,
    literature_service,
    query_service,
)
from socialdna.application import reevaluation_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import withdraw
from socialdna.application.performance_service import analyze_account, compare, reproduce
from socialdna.application.research_service import show_research
from socialdna.cli.app import app as cli
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef
from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus
from socialdna.domain.memory import QuerySpec
from socialdna.research.reevaluation import ReevaluationSpec
from socialdna.storage import reevaluation_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def append_posts(
    settings: Settings,
    tmp_path: Path,
    *,
    account: str = "0001",
    count: int = 2,
    offset: int = 0,
    signal: int = -40,
    creators: int = 1,
) -> None:
    records: list[dict[str, Any]] = []
    for creator in range(creators):
        owner = account if creators == 1 else f"creator-{creator}"
        records.append(
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": owner,
                "creator_key": "owned-creator" if owner == "0001" else owner,
                "niche": "cooking",
            }
        )
        for index in range(count):
            post = f"{owner}-batch-{offset}-{index}"
            records.extend(
                [
                    {
                        "record_type": "post",
                        "platform": "demo",
                        "external_id": post,
                        "account_external_id": owner,
                        "published_at": "2026-02-01T00:00:00Z",
                        "caption": "x" * (index + 1),
                    },
                    {
                        "record_type": "metric_snapshot",
                        "platform": "demo",
                        "subject_external_id": post,
                        "metric_key": "demo.views.v1",
                        "value": 1000 + signal * index + ((creator * 7 + index * 13) % 17),
                        "observed_at": "2026-02-08T00:00:00Z",
                        "window_start": "2026-02-01T00:00:00Z",
                        "window_end": "2026-02-08T00:00:00Z",
                    },
                ]
            )
    path = tmp_path / f"append-{account}-{offset}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": f"synthetic-incremental-{account}-{offset}",
                    "permission_basis": "creator_owned_export",
                    "source_uri": f"urn:fixture:incremental:{account}:{offset}",
                },
                "records": records,
            }
        )
    )
    assert import_dataset(settings, path, "json")["valid"]


def assess(settings: Settings, library: dict[str, Any]) -> EntityRef:
    with open_application(settings) as app:
        return EntityRef.model_validate(
            investigation_service.evaluate(app, evaluation(library))["assessment"]
        )


def test_noop_and_unrelated_import_do_not_reprocess(
    settings: Settings, library: dict[str, Any], tmp_path: Path
) -> None:
    ref = assess(settings, library)
    with open_application(settings) as app:
        before = service.history(app, ref.id)
        assert before["assessments"][0]["freshness"] == "current"
        result = service.reevaluate(app, ref.id)
        assert result["status"] == "unchanged" and result["analyses_run"] == 0
    append_posts(settings, tmp_path, account="unrelated")
    with open_application(settings) as app:
        assert investigation_service.show_record(app, ref)["freshness"] == "current"
        assert service.reevaluate(app, ref.id)["status"] == "unchanged"
        assert service.history(app, ref.id)["requests"] == []


def test_incremental_membership_history_reports_and_cli(
    settings: Settings, library: dict[str, Any], tmp_path: Path
) -> None:
    ref = assess(settings, library)
    with open_application(settings) as app:
        report = investigation_service.assessment_report(app, ref)
        historical_bytes = Path(report["artifact"]["path"]).read_bytes()
        previous_payload = canonical_json(investigation_service.show_record(app, ref)["content"])
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        assert investigation_service.show_record(app, ref)["freshness"] == "stale"
        status = service.status(app)
        assert status["analyses_run"] == 0
        revised = service.reevaluate(app, ref.id)
        assert revised["analyses_run"] == 1
        successor = EntityRef.model_validate(revised["assessment"])
        content = investigation_service.show_record(app, successor)["content"]
        delta = content["reevaluation"]
        assert len(delta["membership"]["posts"]["new"]) == 2
        assert len(delta["membership"]["posts"]["reused"]) == 6
        assert delta["membership"]["creators"]["new"] == []
        assert content["population_manifests"][0]["test_ledger"]["prior_attempts"] == 1
        assert (
            content["population_manifests"][0]["test_ledger"]["family_id"]
            == "cooking-research-family"
        )
        assert not delta["independent_confirmation"]
        assert (
            canonical_json(investigation_service.show_record(app, ref)["content"])
            == previous_payload
        )
        assert investigation_service.show_record(app, ref)["freshness"] == "superseded"
        assert (
            Path(investigation_service.assessment_report(app, ref)["artifact"]["path"]).read_bytes()
            == historical_bytes
        )
        assert service.reevaluate(app, ref.id)["status"] == "unchanged"
        history = service.history(app, library["registered"]["hypotheses"][0]["id"])
        assert len(history["assessments"]) == 2 and len(history["transitions"]) == 1
        assert history["requests"][0]["status"] == "completed"
        with app.database.transaction() as connection:
            assert not repository.current(connection, ref)
        hits = query_service.query(app, QuerySpec(text="cooking", mode="fts", limit=30))["hits"]
        assert not any(h["owner"]["revision_id"] == ref.revision_id for h in hits)
    for command in (["history", ref.id], ["status"], ["reevaluate", ref.id]):
        result = CliRunner().invoke(
            cli, ["--data-dir", str(settings.data_dir), "--format", "json", "research", *command]
        )
        assert result.exit_code == 0, result.output
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "research",
            "show",
            ref.id,
            "--revision",
            ref.revision_id,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        json.loads(result.stdout)["data"]["content"]["input_hash"]
        == json.loads(previous_payload)["input_hash"]
    )


def test_interrupted_evaluation_reuses_checkpoint_without_refitting(
    settings: Settings, library: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = assess(settings, library)
    append_posts(settings, tmp_path)
    original = service.evaluate

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected interruption after committed analysis")

    with open_application(settings) as app:
        monkeypatch.setattr(service, "evaluate", fail)
        with pytest.raises(RuntimeError, match="injected interruption"):
            service.reevaluate(app, ref.id)
        with app.database.transaction() as connection:
            count = connection.scalar(
                select(func.count()).select_from(metadata.tables["test_attempts"])
            )
        assert count == 2
    monkeypatch.setattr(service, "evaluate", original)
    append_posts(settings, tmp_path, offset=1)
    with open_application(settings) as app:
        result = service.reevaluate(app, ref.id)
        assert result["analyses_run"] == 0
        resumed = EntityRef.model_validate(result["assessment"])
        assert investigation_service.show_record(app, resumed)["freshness"] == "stale"
        assert service.history(app, ref.id)["requests"][0]["status"] == "completed"
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["test_attempts"])
                )
                == count
            )


def test_explicit_scope_narrowing_and_family_reset_refusal(
    settings: Settings, library: dict[str, Any]
) -> None:
    ref = assess(settings, library)
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError, match="family_id"):
            service.reevaluate(app, ref.id, ReevaluationSpec(designs=(design(family_id="reset"),)))
        narrowed = design(population={"topics": ["not-present"]})
        result = service.reevaluate(
            app, ref.id, ReevaluationSpec(reason="Narrow to declared topic", designs=(narrowed,))
        )
        delta = investigation_service.show_record(
            app, EntityRef.model_validate(result["assessment"])
        )["content"]["reevaluation"]
        assert len(delta["membership"]["posts"]["removed"]) == 6
        assert all(t["comparison"] == "scope_narrowed" for t in delta["transitions"])


def test_literature_correction_requires_review_and_withdrawal_is_not_resurrected(
    settings: Settings, library: dict[str, Any]
) -> None:
    ref = assess(settings, library)
    corpus = literature_service.read_spec(CORPUS, LiteratureCorpus).model_dump(mode="json")
    corpus["studies"][0]["publication_status"] = "corrected"
    with open_application(settings) as app:
        imported = literature_service.import_corpus(app, LiteratureCorpus.model_validate(corpus))
        with app.database.transaction() as connection:
            assert any(
                r["kind"] == "literature_changed"
                for r in repository.refresh(connection, ref.revision_id)["reasons"]
            )
        assert investigation_service.show_record(app, ref)["status"] == "withheld"
        assert service.reevaluate(app, ref.id)["status"] == "review_required"
        assert service.history(app, ref.id)["assessments"][0]["judgments"] is None
        reviewed = investigation_service.prepare(app, protocol(library["registered"], imported))
        revised = service.reevaluate(
            app,
            ref.id,
            ReevaluationSpec(
                reason="Review corrected literature applicability",
                protocol=EntityRef.model_validate(reviewed["protocol"]),
            ),
        )
        assert revised["analyses_run"] == 0
        assert show_research(app, ref.id)["ref"] == revised["assessment"]
        assert show_research(app, ref.id, revision_id=ref.revision_id)["status"] == "withheld"


def test_watch_and_lineage_guards(
    settings: Settings, library: dict[str, Any], tmp_path: Path
) -> None:
    ref = assess(settings, library)
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        service.reevaluate(app, ref.id)
        for sql in (
            "UPDATE assessment_transitions SET created_at='changed'",
            "DELETE FROM assessment_transitions",
            "UPDATE assessment_watches SET manifest_json='[]'",
            "UPDATE reevaluation_requests SET status='running' WHERE status='completed'",
        ):
            with pytest.raises(IntegrityError), app.database.transaction() as connection:
                connection.exec_driver_sql(sql)


@pytest.mark.parametrize(
    ("new_signal", "disposition", "local_status"),
    [(-40, "weakened", "inconclusive"), (-120, "contradicted_in_scope", "contrary")],
)
def test_actual_positive_association_weakens_after_new_failures(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
    new_signal: int,
    disposition: str,
    local_status: str,
) -> None:
    # 176 initial posts across 22 clusters; 176 opposite-pattern posts are new
    # units in the SAME creators, not a claimed independent replication.
    append_posts(settings, tmp_path, creators=22, count=8, offset=1, signal=40)
    with open_application(settings) as app:
        ids = [stable_id("account", "demo", f"creator-{c}") for c in range(22)]
        analysis = compare(
            app, "accounts", ids[:11], ids[11:], design(family_id="incremental-cooking")
        )
        initial = investigation_service.evaluate(
            app,
            EvaluationSpec.model_validate(
                {
                    "protocol": library["protocol"],
                    "analysis_run_ids": [analysis["run_id"]],
                    "expected_claim_level": "association",
                }
            ),
        )
        ref = EntityRef.model_validate(initial["assessment"])
        assert (
            investigation_service.show_record(app, ref)["content"]["judgments"][0][
                "local_association"
            ]["status"]
            == "consistent"
        )
    append_posts(settings, tmp_path, creators=22, count=8, offset=2, signal=new_signal)
    with open_application(settings) as app:
        revised = service.reevaluate(app, ref.id)
        new = EntityRef.model_validate(revised["assessment"])
        delta = investigation_service.show_record(app, new)["content"]["reevaluation"]
        assert delta["transitions"][0]["disposition"] == disposition
        assert delta["transitions"][0]["current_status"] == local_status
        assert len(delta["membership"]["posts"]["new"]) == 176
        assert len(delta["membership"]["posts"]["reused"]) == 176
        assert delta["membership"]["creators"]["new"] == []
        assert not delta["independent_confirmation"]
        assert len(service.history(app, ref.id)["transitions"]) == 1


def test_journal_survives_index_drain_and_rebuild_is_not_new_evidence(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
) -> None:
    ref = assess(settings, library)
    with open_application(settings) as app:
        query_service.reconcile(app, limit=5000)
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        query_service.reconcile(app, limit=5000)
        assert investigation_service.show_record(app, ref)["freshness"] == "stale"
        revised = service.reevaluate(app, ref.id)
        successor = EntityRef.model_validate(revised["assessment"])
        query_service.reconcile(app, limit=5000, rebuild=True)
        assert investigation_service.show_record(app, successor)["freshness"] == "current"
        assert service.reevaluate(app, ref.id)["status"] == "unchanged"


def test_arrivals_between_frozen_analysis_and_assessment_are_not_missed(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
) -> None:
    append_posts(settings, tmp_path)
    ref = assess(settings, library)
    with open_application(settings) as app:
        assert investigation_service.show_record(app, ref)["freshness"] == "stale"
        assert service.reevaluate(app, ref.id)["analyses_run"] == 1


@pytest.mark.parametrize("target", ["source", "earlier_statistical_citation"])
def test_withdrawal_withholds_both_revisions_and_history_content(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
    target: str,
) -> None:
    ref = assess(settings, library)
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        service.reevaluate(app, ref.id)
        with app.database.transaction() as connection:
            withdraw(
                connection,
                source_id=library["source_id"] if target == "source" else None,
                evidence_id=library["analysis"]["statistical_evidence"][0]["ref"]["id"]
                if target == "earlier_statistical_citation"
                else None,
                reason="Permission revoked",
                actor="owner",
            )
        history = service.history(app, ref.id)
        assert all(
            a["status"] == "withheld" and a["comparison"] is None for a in history["assessments"]
        )
        if target == "source":
            with pytest.raises(ConfigurationError):
                service.reevaluate(app, ref.id)
        else:
            assert service.reevaluate(app, ref.id)["status"] == "review_required"


def test_metric_correction_records_revised_not_new_units(
    settings: Settings,
    library: dict[str, Any],
    account_export: Path,
) -> None:
    ref = assess(settings, library)
    data = json.loads(account_export.read_text())
    for record in data["records"]:
        if record["record_type"] == "metric_snapshot" and record["metric_key"] == "demo.views.v1":
            record["value"] += 50
    data["source"]["dataset_id"] = "corrected-owned-fixture"
    account_export.write_text(json.dumps(data))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        result = service.reevaluate(app, ref.id)
        delta = investigation_service.show_record(
            app, EntityRef.model_validate(result["assessment"])
        )["content"]["reevaluation"]
        assert delta["membership"]["posts"]["new"] == []
        assert len(delta["membership"]["posts"]["reused"]) == 6
        assert any(c["kind"] == "metric_changed" for c in delta["changes"])
        changed = next(c for c in delta["changes"] if c["kind"] == "analysis_inputs_changed")
        assert len(changed["changed_posts"]) == 6
        assert all(
            c["change"] == "revised"
            and c["previous"]["snapshot_ids"] != c["current"]["snapshot_ids"]
            for c in changed["changed_posts"]
        )


def test_audience_erasure_withholds_entire_revision_chain_and_artifacts(
    settings: Settings,
    library: dict[str, Any],
    tmp_path: Path,
) -> None:
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            comment = EvidenceRepository(connection).latest(
                "comment", stable_id("comment", stable_id("post", "demo", "p0"), "cooking-comment")
            )
            assert comment is not None
            citation = EvidenceRepository(connection).comment_evidence(comment.id, 0, 17)
        result = investigation_service.evaluate(
            app, evaluation(library, evidence=[citation.model_dump()])
        )
        ref = EntityRef.model_validate(result["assessment"])
        before = investigation_service.assessment_report(app, ref)
    append_posts(settings, tmp_path)
    with open_application(settings) as app:
        result = service.reevaluate(app, ref.id)
        successor = EntityRef.model_validate(result["assessment"])
        after = investigation_service.assessment_report(app, successor)
        plan = audience_service.redact(app, comment_id=comment.id)
        audience_service.redact(
            app,
            comment_id=comment.id,
            confirmation=plan["confirmation"],
            reason="Authorized fixture removal",
        )
        history = service.history(app, ref.id)
        assert len(history["transitions"]) == 1
        assert all(
            a["status"] == "withheld" and a["comparison"] is None for a in history["assessments"]
        )
        assert not Path(before["artifact"]["path"]).exists()
        assert not Path(after["artifact"]["path"]).exists()


def test_prior_release_analysis_reproduces_without_changing_frozen_inputs(
    settings: Settings,
    library: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from socialdna.application import statistical_service

    with open_application(settings) as app:
        with monkeypatch.context() as old_release:
            old_release.setattr(statistical_service, "__version__", "0.0.11")
            original = analyze_account(app, ACCOUNT, design())
        reproduced = reproduce(app, original["run_id"])
        assert reproduced["results"] == original["results"]
        assert reproduced["posts"] == original["posts"]
        assert reproduced["test_ledger"]["reproduced_from"] == original["run_id"]
        assert not reproduced["test_ledger"]["independent_confirmation"]
