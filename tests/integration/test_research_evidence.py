import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import ClaimValidator, EvidenceResolver, withdraw
from socialdna.application.performance_service import analyze_account
from socialdna.application.research_service import (
    generate_research_report,
    register_research,
    show_research,
)
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_file
from socialdna.core.ids import stable_id
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.research import PerformanceSpec, ResearchRegistration
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


@pytest.fixture
def research_export(account_export: Path) -> Path:
    payload = json.loads(account_export.read_text())
    payload["source"]["comments_permitted"] = True
    payload["records"].append(
        {
            "record_type": "comment",
            "platform": "demo",
            "post_external_id": "p0",
            "external_id": "c1",
            "body": "🍲 I will cook this! <script> [open](https://example.invalid)",
            "published_at": "2026-01-02T00:00:00Z",
        }
    )
    account_export.write_text(json.dumps(payload), encoding="utf-8")
    return account_export


def citations(settings: Settings, path: Path) -> tuple[EvidenceRef, EvidenceRef]:
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            repository = EvidenceRepository(connection)
            comment_id = connection.scalar(select(metadata.tables["comments"].c.id))
            snapshots = metadata.tables["metric_observations"]
            snapshot_id = connection.scalar(
                select(snapshots.c.id)
                .where(snapshots.c.metric_key == "demo.views.v1")
                .order_by(snapshots.c.value)
                .limit(1)
            )
            assert comment_id and snapshot_id
            return repository.comment_evidence(comment_id, 0, 19), repository.metric_evidence(
                snapshot_id
            )


def specification(tmp_path: Path, refs: tuple[EvidenceRef, ...] = ()) -> Path:
    path = tmp_path / "research.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "cooking-result-first",
                "question": "Why might a meal preview be associated with better outcomes?",
                "population": "Permitted cooking-video fixtures; no empirical claim",
                "data_needs": ["reviewed openings", "comparable outcomes"],
                "evidence": [ref.model_dump() for ref in refs],
                "hypotheses": [
                    {
                        "key": "anticipation",
                        "statement": "A preview might create anticipation.",
                        "population": "Fixture population",
                        "intended_claim_level": "association",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_real_comment_and_metric_citations_persist_and_keep_exact_versions(
    settings: Settings,
    research_export: Path,
) -> None:
    comment, metric = citations(settings, research_export)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            resolver = EvidenceResolver(connection)
            original = resolver.resolve(comment, purpose="new_claim")
            assert original.locator is not None
            assert original.locator.model_dump()["quote"] == "🍲 I will cook this!"
            assert original.producer_task_id is None
            observed = resolver.resolve(metric)
            assert observed.locator is not None
            payload = observed.locator.model_dump()
            assert payload["value"] == 100
            assert "start_ms" not in payload
            assert observed.producer_run_id is None
            metric_subject = observed.subject
            alias = resolver.resolve("socialdna:metric/" + metric_subject.id)
            assert alias.ref == metric
            original_source = original.source["id"]
    changed = json.loads(research_export.read_text())
    next(row for row in changed["records"] if row["record_type"] == "comment")["body"] = (
        "Changed text"
    )
    next(row for row in changed["records"] if row.get("external_id") == "p0")["caption"] = (
        "Edited after outcome"
    )
    research_export.write_text(json.dumps(changed))
    import_dataset(settings, research_export, "json")
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            resolver = EvidenceResolver(connection)
            old = resolver.resolve(comment)
            assert (
                old.locator is not None
                and old.locator.model_dump()["quote"] == "🍲 I will cook this!"
            )
            assert old.source["id"] == original_source
            assert resolver.resolve(metric).subject == metric_subject
            assert resolver.resolve("metric:" + metric_subject.id).ref == metric
            repository = EvidenceRepository(connection)
            current_comment = repository.get("entity_revisions", old.subject.revision_id)[
                "entity_id"
            ]
            new_ref = repository.comment_evidence(current_comment, 0, len("Changed text"))
            assert resolver.resolve(new_ref).locator.model_dump()["quote"] == "Changed text"
            assert new_ref.id != comment.id


@pytest.mark.parametrize(
    "start,end", [(-1, 3), (0, 0), (3, 2), (0, 10000), (True, 4), (0.5, 3), (0, "3")]
)
def test_invalid_comment_spans_are_rejected(
    settings: Settings,
    research_export: Path,
    start: int,
    end: int,
) -> None:
    citations(settings, research_export)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            comment_id = connection.scalar(select(metadata.tables["comments"].c.id))
            with pytest.raises(ConfigurationError, match="span"):
                EvidenceRepository(connection).comment_evidence(comment_id, start, end)


def test_wrong_identity_kind_revision_and_unavailable_metrics(
    settings: Settings,
    research_export: Path,
) -> None:
    comment, metric = citations(settings, research_export)
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            resolver, repository = EvidenceResolver(connection), EvidenceRepository(connection)
            with pytest.raises(ConfigurationError, match="identity"):
                resolver.resolve(EvidenceRef(id=metric.id, revision_id=comment.revision_id))
            subject = resolver.resolve(comment).subject
            with pytest.raises(ConfigurationError, match="kind/identity"):
                repository.entity(
                    EntityRef(kind="post", id=subject.id, revision_id=subject.revision_id)
                )
            with pytest.raises(ConfigurationError, match="post"):
                resolver.resolve(comment, post_id="wrong-post")
            with pytest.raises(ConfigurationError, match="run"):
                resolver.resolve(metric, run_id="wrong-run")
            assert not resolver.resolve(comment, as_of="2020-01-01T00:00:00Z").eligible
            with pytest.raises(ConfigurationError, match="Timestamp"):
                resolver.resolve(metric, as_of="2026-01-01")
            snapshots = metadata.tables["metric_observations"]
            missing_id = connection.scalar(
                select(snapshots.c.id).where(snapshots.c.availability == "not_permitted")
            )
            unavailable = repository.metric_evidence(missing_id)
            result = resolver.resolve(unavailable)
            assert not result.eligible and result.locator is None
            with pytest.raises(ConfigurationError, match="Ineligible"):
                resolver.resolve(unavailable, purpose="new_claim")
            with pytest.raises(ConfigurationError, match="associations"):
                ClaimValidator(connection).validate("association", (metric,))
            with pytest.raises(ConfigurationError, match="evidence"):
                ClaimValidator(connection).validate("observation", ())


def test_registration_is_idempotent_versioned_and_not_evaluation(
    settings: Settings,
    research_export: Path,
    tmp_path: Path,
) -> None:
    refs = citations(settings, research_export)
    path = specification(tmp_path, refs)
    first = register_research(settings, path)
    assert register_research(settings, path) == first
    assert not first["evaluation_ready"]
    with open_application(settings) as application:
        question = show_research(application, first["question"]["id"])
        assert len(question["hypotheses"]) == 1
        assert len(question["citations"]) == 2
    changed = json.loads(path.read_text())
    changed["hypotheses"][0]["statement"] = "An alternative draft explanation."
    path.write_text(json.dumps(changed))
    second = register_research(settings, path)
    assert second["question"]["id"] == first["question"]["id"]
    assert second["question"]["revision_id"] != first["question"]["revision_id"]
    with open_application(settings) as application:
        old = show_research(
            application, first["question"]["id"], revision_id=first["question"]["revision_id"]
        )
        assert old["hypotheses"][0]["specification"]["statement"].startswith("A preview")
        assert show_research(application, second["question"]["id"])["hypotheses"][0][
            "specification"
        ]["statement"].startswith("An alternative")


def test_withdrawal_degrades_current_report_without_rewriting_artifacts(
    settings: Settings,
    research_export: Path,
    tmp_path: Path,
) -> None:
    refs = citations(settings, research_export)
    path = specification(tmp_path, refs)
    question = register_research(settings, path)["question"]
    with open_application(settings) as application:
        report = generate_research_report(application, question["id"])
        old_path = Path(report["artifact"]["path"])
        checksum = hash_file(old_path)
        assert generate_research_report(application, question["id"])["ref"] == report["ref"]
        markdown = generate_research_report(application, question["id"], report_format="markdown")
        assert "🍲 I will cook this" in markdown["content"]
        with application.database.transaction() as connection:
            resolver = EvidenceResolver(connection)
            source_id = resolver.resolve(refs[0]).source["id"]
            first = withdraw(connection, source_id=source_id, reason="Research reuse revoked")
            assert not first["retained_bytes_erased"]
            assert (
                withdraw(connection, source_id=source_id, reason="Repeated request")["id"]
                == first["id"]
            )
        current = show_research(application, report["ref"]["id"])
        assert current["status"] == "partial"
        assert all(item["locator"] is None for item in current["content"]["citations"])
        assert "🍲" not in json.dumps(current, ensure_ascii=False)
        assert hash_file(old_path) == checksum
        revised = generate_research_report(application, question["id"])
        assert revised["status"] == "partial" and revised["ref"] != report["ref"]
        assert hash_file(old_path) == checksum
        with pytest.raises(ConfigurationError, match="Withdrawn"):
            analyze_account(
                application,
                stable_id("account", "demo", "0001"),
                PerformanceSpec(metric_key="demo.views.v1"),
            )
    with pytest.raises(ConfigurationError, match="Ineligible"):
        register_research(settings, path)


def test_dry_run_does_not_initialize_or_change_existing_database(
    settings: Settings,
    research_export: Path,
    tmp_path: Path,
) -> None:
    path = specification(tmp_path)
    assert register_research(settings, path, dry_run=True)["written"] is False
    assert not settings.data_dir.exists()
    refs = citations(settings, research_export)
    path = specification(tmp_path, refs)
    database_path = settings.data_dir / "socialdna.db"
    before = {item.name: hash_file(item) for item in settings.data_dir.iterdir() if item.is_file()}
    assert register_research(settings, path, dry_run=True)["valid"]
    after = {item.name: hash_file(item) for item in settings.data_dir.iterdir() if item.is_file()}
    assert before == after and database_path.is_file()


def test_sql_immutability_fk_and_typed_binding_checks(
    settings: Settings, research_export: Path
) -> None:
    comment, metric = citations(settings, research_export)
    with open_application(settings) as application:
        with pytest.raises(IntegrityError, match="immutable"):
            with application.database.transaction() as connection:
                connection.execute(
                    metadata.tables["evidence_revisions"]
                    .update()
                    .where(metadata.tables["evidence_revisions"].c.id == comment.revision_id)
                    .values(locator_json="{}")
                )
        with pytest.raises(IntegrityError):
            with application.database.transaction() as connection:
                connection.execute(
                    metadata.tables["evidence_links"]
                    .insert()
                    .values(
                        owner_revision_id="missing",
                        evidence_revision_id=metric.revision_id,
                        role="context",
                        scope_revision_id="missing",
                    )
                )
        with application.database.transaction() as connection:
            # A second, individually valid FK binding is still semantically invalid.
            metric_binding = (
                connection.execute(select(metadata.tables["metric_evidence_bindings"]))
                .mappings()
                .first()
            )
            connection.execute(
                metadata.tables["metric_evidence_bindings"]
                .insert()
                .values(**{**dict(metric_binding), "evidence_revision_id": comment.revision_id})
            )
            with pytest.raises(StorageIntegrityError, match="exactly one"):
                EvidenceResolver(connection).resolve(comment)


def test_research_contract_rejects_causal_and_duplicate_hypotheses() -> None:
    base = {
        "key": "x",
        "question": "Question?",
        "population": "Posts",
        "hypotheses": [{"key": "h", "statement": "Draft", "population": "Posts"}],
    }
    with pytest.raises(ValidationError):
        ResearchRegistration.model_validate({**base, "hypotheses": base["hypotheses"] * 2})
    base["hypotheses"][0]["intended_claim_level"] = "causal_finding"
    with pytest.raises(ValidationError):
        ResearchRegistration.model_validate(base)
