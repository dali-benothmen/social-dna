"""Real SQLite/FTS/Qdrant processes; synthetic embeddings test plumbing, not relevance."""

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from socialdna.application import audience_service, query_service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.creative_service import import_into_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.import_service import import_local
from socialdna.application.research_service import register_research
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.time import utc_now
from socialdna.domain.creative import CreativeAnnotationSet
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.memory import EmbeddingSpace, QuerySpec
from socialdna.memory import graph, hybrid, lexical, vector_sync
from socialdna.storage.backup import create_backup, restore_library
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

SECRET = "🍳 Velvet saffron opening — I will cook this!"


class TestEmbedder:
    """No production registration route; a normalized deterministic test double."""

    __test__ = False

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        vectors = []
        for text in texts:
            values = [1.0, float(text.casefold().count("saffron")), float(len(text) % 7)]
            norm = math.sqrt(sum(value * value for value in values))
            vectors.append([value / norm for value in values])
        return vectors


def test_space(**changes: Any) -> EmbeddingSpace:
    return EmbeddingSpace.model_validate(
        {
            "model_name": "test-double-not-a-production-model",
            "model_revision": "fixture-1",
            "manifest_hash": "a" * 64,
            "license": "fixture only",
            "dimensions": 3,
            "max_tokens": 512,
            "languages": ["en"],
            "runtime_version": "test-only",
            **changes,
        }
    )


test_space.__test__ = False  # type: ignore[attr-defined]


@pytest.fixture
def library(settings: Settings, account_export: Path) -> tuple[EvidenceRef, EvidenceRef]:
    payload = json.loads(account_export.read_text())
    payload["source"]["comments_permitted"] = True
    payload["records"].append(
        {
            "record_type": "comment",
            "platform": "demo",
            "post_external_id": "p0",
            "external_id": "memory-comment",
            "body": SECRET,
            "published_at": "2026-01-07T00:00:00Z",
        }
    )
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app, app.database.transaction() as connection:
        repository = EvidenceRepository(connection)
        comment = connection.scalar(select(metadata.tables["comments"].c.id))
        metric = connection.scalar(select(metadata.tables["metric_observations"].c.id))
        assert comment and metric
        refs = (
            repository.comment_evidence(comment, 0, len(SECRET)),
            repository.metric_evidence(metric),
        )
    return refs


def subprocess_command(settings: Settings, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--offline",
            "--format",
            "json",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["data"]


def prepare(app: Application) -> str:
    with app.database.transaction() as connection:
        lexical.reconcile(connection)
        return vector_sync.register_space(connection, test_space())


def test_sql_fts_cross_process_exact_citations_and_literal_query(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    result = subprocess_command(settings, "query", "saffron")
    assert result["hits"][0]["text"] == SECRET
    assert result["hits"][0]["citations"][0]["ref"] == library[0].model_dump()
    resolved = subprocess_command(
        settings, "evidence", "resolve", library[0].id, "--revision", library[0].revision_id
    )
    assert resolved["eligible"] and resolved["locator"]["quote"] == SECRET
    sql = subprocess_command(settings, "query", "saffron", "--mode", "sql")
    assert sql["hits"][0]["document_revision_id"] == result["hits"][0]["document_revision_id"]
    assert subprocess_command(settings, "query", '" OR NOT * -: ()')["hits"] == []
    assert not (settings.data_dir / "vectors" / "meta.json").exists()


def test_cooking_opening_graph_restart_and_removed_event(settings: Settings, video: Path) -> None:
    with open_application(settings) as app:
        media = import_local(app, video)
        with app.database.transaction() as connection:
            sha = EvidenceRepository(connection).get("media_assets", media["media_id"])["sha256"]
        spec = CreativeAnnotationSet.model_validate(
            {
                "key": "cooking-review",
                "media_sha256": sha,
                "permission_basis": "owned generated fixture",
                "protocol": {
                    "origin": "human",
                    "author": "fixture",
                    "procedure": "reviewed fixture assertion",
                    "outcome_access": "blinded",
                    "label_frozen_before_outcomes": True,
                },
                "events": [
                    {
                        "key": "opening",
                        "technique": "finished_dish",
                        "description": "Result-first saffron cooking opening (fixture assertion)",
                        "modalities": ["visual"],
                        "anchors": [
                            {
                                "start_min_ms": 0,
                                "start_max_ms": 0,
                                "end_min_ms": 700,
                                "end_max_ms": 800,
                            }
                        ],
                        "state": "reviewed",
                        "reviewer": "fixture",
                    }
                ],
            }
        )
        import_into_application(app, spec)
    hit = subprocess_command(settings, "query", "saffron", "--owner-kind", "creative_event")[
        "hits"
    ][0]
    assert hit["citations"][0]["locator"]["media"]["id"] == media["media_id"]
    root = hit["owner"]["revision_id"]
    view = subprocess_command(settings, "graph", "neighbors", root)
    assert any(edge["relation"] == "media_context" for edge in view["edges"])
    assert all("scope_revision_id" in edge["qualification"] for edge in view["edges"])
    with open_application(settings) as app:
        import_into_application(app, spec.model_copy(update={"events": ()}))
        assert (
            query_service.query(app, QuerySpec(text="saffron", owner_kind="creative_event"))["hits"]
            == []
        )
        historical = query_service.query(app, QuerySpec(text="saffron", revision_id=root))
        assert historical["hits"]  # exact historical citation remains allowed absent erasure.


def test_draft_graph_is_qualified_not_an_effect(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef], tmp_path: Path
) -> None:
    spec = tmp_path / "question.json"
    spec.write_text(
        json.dumps(
            {
                "key": "saffron-question",
                "question": "Does a saffron opening help?",
                "population": "fixture cooking posts, not an evaluated population",
                "evidence": [library[0].model_dump()],
                "hypotheses": [
                    {
                        "key": "anticipation",
                        "statement": "Saffron may cue anticipation.",
                        "population": "fixture only",
                        "evidence": [library[1].model_dump()],
                    }
                ],
            }
        )
    )
    register_research(settings, spec)
    with open_application(settings) as app:
        result = query_service.query(
            app, QuerySpec(text="anticipation", owner_kind="hypothesis", graph_depth=2)
        )
        assert result["hits"]
        hit = result["hits"][0]
        assert hit["representation"]["claim_level"] == "hypothesis"
        assert all(
            edge["relation"] not in {"causes", "associated_with", "supports"}
            for edge in hit["graph"]["edges"]
        )


def test_correction_and_known_asof_do_not_serve_old_as_current(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef], account_export: Path
) -> None:
    with open_application(settings) as app:
        before = query_service.query(app, QuerySpec(text="saffron"))["hits"][0]
    cutoff = utc_now()
    payload = json.loads(account_export.read_text())
    payload["records"][-1]["body"] = "A corrected basil opening."
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"] == []
        assert query_service.query(app, QuerySpec(text="saffron", as_of=cutoff))["hits"]
        assert query_service.query(
            app, QuerySpec(text="saffron", revision_id=before["owner"]["revision_id"])
        )["hits"]


def test_change_journal_rolls_back_with_canonical_write(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            repository = EvidenceRepository(connection)
            comment = repository.get("evidence_revisions", library[0].revision_id)[
                "subject_revision_id"
            ]
            entity = repository.get("entity_revisions", comment)
            previous = connection.scalar(
                select(func.count()).select_from(metadata.tables["memory_changes"])
            )
        with (
            pytest.raises(RuntimeError, match="rollback"),
            app.database.transaction() as connection,
        ):
            repository = EvidenceRepository(connection)
            repository.save_entity(
                "hypothesis",
                "not-committed",
                {"statement": "saffron uncommitted"},
                entity["provenance_id"],
            )
            raise RuntimeError("rollback")
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["memory_changes"])
                )
                == previous
            )


def test_qdrant_upsert_crash_replay_and_space_isolation(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef], monkeypatch: pytest.MonkeyPatch
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        client = app.vectors.client
        original = client.upsert

        def crash(*args: Any, **kwargs: Any) -> Any:
            original(*args, **kwargs)
            raise RuntimeError("crash after upsert before acknowledgement")

        monkeypatch.setattr(client, "upsert", crash)
        result = vector_sync.drain(app, space, provider=TestEmbedder(), limit=1)
        assert result["failed"] == 1 and result["pending"]
    with open_application(settings) as app:
        assert vector_sync.drain(app, space, provider=TestEmbedder())["pending"] == 0
        with app.database.transaction() as connection:
            other = vector_sync.register_space(connection, test_space(query_prefix="different: "))
            assert other != space
        assert vector_sync.drain(app, other, provider=TestEmbedder())["pending"] == 0
        hit = hybrid.search(
            app, QuerySpec(text="saffron", mode="semantic", space_id=space), provider=TestEmbedder()
        )["hits"][0]
        assert hit["citations"]
        names = [item.name for item in app.vectors.client.get_collections().collections]
        assert any(space.replace("-", "") in name for name in names)
        assert any(other.replace("-", "") in name for name in names)
        with app.database.transaction() as connection:
            entries = list(
                connection.execute(select(metadata.tables["vector_index_entries"])).mappings()
            )
        assert all(entry["indexed_generation"] == entry["generation"] for entry in entries)
        assert sum(app.vectors.client.count(name, exact=True).count for name in names) == len(
            entries
        )
    restarted = subprocess_command(settings, "storage", "status")
    assert set(restarted["vectors"]["collections"]) == set(names)


def test_stale_generation_and_missing_collection_repair(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        with app.database.transaction() as connection:
            table = metadata.tables["vector_documents"]
            identity = connection.scalar(select(table.c.id).where(table.c.owner_kind == "comment"))
            assert identity
            vector_sync.desire(connection, identity, None)
        result = vector_sync.drain(app, space, provider=TestEmbedder())
        assert result["superseded"] == 1
        assert not hybrid.search(
            app,
            QuerySpec(text="saffron", mode="semantic", owner_kind="comment", space_id=space),
            provider=TestEmbedder(),
        )["hits"]
        for item in app.vectors.client.get_collections().collections:
            app.vectors.client.delete_collection(item.name)
        assert vector_sync.repair(app, space)["requeued"] > 0
        assert vector_sync.drain(app, space, provider=TestEmbedder())["pending"] == 0


def test_withdrawal_immediately_gates_stale_fts_graph_vectors_and_jobs(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        vector_sync.drain(app, space, provider=TestEmbedder())
        with app.database.transaction() as connection:
            root = EvidenceRepository(connection).get("evidence_revisions", library[0].revision_id)[
                "subject_revision_id"
            ]
            withdraw(connection, evidence_id=library[0].id, reason="fixture revocation")
        assert hybrid.search(app, QuerySpec(text="saffron"))["hits"] == []
        assert (
            hybrid.search(
                app,
                QuerySpec(text="saffron", mode="semantic", space_id=space, owner_kind="comment"),
                provider=TestEmbedder(),
            )["hits"]
            == []
        )
        with app.database.transaction() as connection:
            assert graph.neighborhood(connection, root)["nodes"] == []
            lexical.reconcile(connection)
        assert vector_sync.drain(app, space, provider=TestEmbedder())["pending"] == 0


def test_erasure_scrubs_all_indexes_and_rebuild_cannot_resurrect(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        vector_sync.drain(app, space, provider=TestEmbedder())
        with app.database.transaction() as connection:
            row = EvidenceRepository(connection).get("evidence_revisions", library[0].revision_id)
            owner = EvidenceRepository(connection).get(
                "entity_revisions", row["subject_revision_id"]
            )
            entries, documents = (
                metadata.tables[name] for name in ("vector_index_entries", "vector_documents")
            )
            indexed = dict(
                connection.execute(
                    select(entries)
                    .join(documents, documents.c.id == entries.c.document_id)
                    .where(documents.c.owner_kind == "comment")
                )
                .mappings()
                .one()
            )
            native_name = vector_sync.collection("audience_reactions", space)
            vector_sync.desire(
                connection, indexed["document_id"], indexed["desired_revision_id"], force=True
            )
        plan = audience_service.redact(app, comment_id=owner["entity_id"])
        result = audience_service.redact(
            app,
            comment_id=owner["entity_id"],
            confirmation=plan["confirmation"],
            reason="authorized fixture erasure",
        )
        assert result["written"]
        assert app.vectors.client.retrieve(native_name, [indexed["point_id"]]) == []
        query_service.reconcile(app, rebuild=True)
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"] == []
        assert not hybrid.search(
            app,
            QuerySpec(text="saffron", mode="semantic", space_id=space, owner_kind="comment"),
            provider=TestEmbedder(),
        )["hits"]
        with app.database.transaction() as connection:
            assert not EvidenceResolver(connection).resolve(library[0]).eligible
            assert not connection.exec_driver_sql(
                "SELECT 1 FROM memory_fts WHERE memory_fts MATCH 'saffron'"
            ).first()
            assert not any(
                SECRET in row[0]
                for row in connection.exec_driver_sql("SELECT text FROM vector_document_revisions")
            )
        vector_sync.drain(app, space, provider=TestEmbedder())
        assert app.vectors.client.retrieve(native_name, [indexed["point_id"]]) == []
    assert SECRET.encode() not in (settings.data_dir / "socialdna.db").read_bytes()
    assert b"saffron" not in (settings.data_dir / "socialdna.db").read_bytes()


def test_fts_rebuild_missing_model_and_bounded_resume(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        first = query_service.reconcile(app, limit=1, rebuild=True)
        assert first["status"] == "partial"
        while query_service.status(app)["pending_changes"]:
            query_service.reconcile(app, limit=10)
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"]
        result = query_service.query(app, QuerySpec(text="saffron", mode="hybrid"))
        assert (
            result["status"] == "partial" and result["hits"] and result["semantic"] == "unavailable"
        )
        semantic = query_service.query(app, QuerySpec(text="saffron", mode="semantic"))
        assert semantic["status"] == "partial" and semantic["hits"] == []


def test_graph_path_budget_and_scope_filters(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef]
) -> None:
    with open_application(settings) as app:
        hit = query_service.query(app, QuerySpec(text="saffron"))["hits"][0]
        with app.database.transaction() as connection:
            root = hit["owner"]["revision_id"]
            view = graph.neighborhood(connection, root)
            target = next(
                node["revision_id"] for node in view["nodes"] if node["revision_id"] != root
            )
            assert graph.path(connection, root, target)["path"]
            assert graph.neighborhood(connection, root, max_nodes=1)["truncated"]
            with pytest.raises(ConfigurationError):
                graph.neighborhood(connection, root, depth=6)
        assert (
            query_service.query(app, QuerySpec(text="saffron", owner_kind="metric_snapshot"))[
                "hits"
            ]
            == []
        )
        assert (
            query_service.query(app, QuerySpec(text="saffron", source_id="not-a-source"))["hits"]
            == []
        )


def test_restore_reconciles_erasure_and_missing_vectors(
    settings: Settings, library: tuple[EvidenceRef, EvidenceRef], tmp_path: Path
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        vector_sync.drain(app, space, provider=TestEmbedder())
        backup = tmp_path / "before-erasure"
        create_backup(app.paths, backup)
        with app.database.transaction() as connection:
            row = EvidenceRepository(connection).get("evidence_revisions", library[0].revision_id)
            owner = EvidenceRepository(connection).get(
                "entity_revisions", row["subject_revision_id"]
            )
        plan = audience_service.redact(app, comment_id=owner["entity_id"])
        audience_service.redact(
            app,
            comment_id=owner["entity_id"],
            confirmation=plan["confirmation"],
            reason="owned erasure",
        )
    destination = tmp_path / "restored"
    restore_library(backup, destination, withdrawals_from=settings.data_dir)
    with open_application(Settings(data_dir=destination)) as app:
        query_service.reconcile(app, rebuild=True)
        assert not query_service.query(app, QuerySpec(text="saffron"))["hits"]
        assert vector_sync.repair(app, space)["requeued"]
    assert SECRET.encode() not in (destination / "socialdna.db").read_bytes()


def test_projection_crash_keeps_canonical_work_and_outbox_atomic(
    settings: Settings,
    library: tuple[EvidenceRef, EvidenceRef],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            vector_sync.register_space(connection, test_space())
        original = lexical.project

        def crash(connection: Any, document: Any) -> int:
            original(connection, document)
            raise RuntimeError("projection crash")

        with monkeypatch.context() as scoped:
            scoped.setattr(lexical, "project", crash)
            with pytest.raises(RuntimeError, match="projection crash"):
                query_service.reconcile(app)
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["memory_changes"])
                )
                > 0
            )
            assert not connection.scalar(
                select(func.count()).select_from(metadata.tables["vector_outbox"])
            )
            assert not connection.scalar(
                select(func.count()).select_from(metadata.tables["vector_document_revisions"])
            )
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"]


def test_withdrawal_during_inference_cannot_write_stale_content(
    settings: Settings,
    library: tuple[EvidenceRef, EvidenceRef],
) -> None:
    with open_application(settings) as app:
        space = prepare(app)

        class RevokingEmbedder(TestEmbedder):
            def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
                with app.database.transaction() as connection:
                    withdraw(
                        connection, evidence_id=library[0].id, reason="withdrawn during inference"
                    )
                return super().encode(texts, query=query)

        vector_sync.drain(app, space, provider=RevokingEmbedder())
        vector_sync.drain(app, space, provider=TestEmbedder())
        assert not hybrid.search(
            app,
            QuerySpec(text="saffron", owner_kind="comment", mode="semantic", space_id=space),
            provider=TestEmbedder(),
        )["hits"]


def test_fts_recreation_and_corrupt_vector_independence(
    settings: Settings,
    library: tuple[EvidenceRef, EvidenceRef],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from socialdna.core.exceptions import StorageIntegrityError

    def unavailable(*args: Any) -> Any:
        raise StorageIntegrityError("Injected unavailable Qdrant")

    monkeypatch.setattr("socialdna.storage.vectors.LocalVectorStore._open", unavailable)
    with open_application(settings) as app:
        hit = query_service.query(app, QuerySpec(text="saffron", mode="sql"))["hits"][0]
        with app.database.transaction() as connection:
            connection.exec_driver_sql("DROP TABLE memory_fts")
        query_service.reconcile(app, rebuild=True)
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"]
        assert query_service.graph_query(app, hit["owner"]["revision_id"])["nodes"]
        with app.database.transaction() as connection:
            table = metadata.tables["vector_document_revisions"]
            connection.execute(
                table.update()
                .where(table.c.id == hit["document_revision_id"])
                .values(text="corrupted projection")
            )
        from socialdna.memory.health import checks

        assert checks(app)[0].status == "warning"
        query_service.reconcile(app, rebuild=True)
        assert query_service.query(app, QuerySpec(text="saffron"))["hits"][0]["text"] == SECRET
        assert checks(app)[0].status == "ok"


def test_repair_budget_advances_across_the_whole_space(
    settings: Settings,
    library: tuple[EvidenceRef, EvidenceRef],
) -> None:
    with open_application(settings) as app:
        space = prepare(app)
        vector_sync.drain(app, space, provider=TestEmbedder())
        for item in app.vectors.client.get_collections().collections:
            app.vectors.client.delete_collection(item.name)
        total = 0
        for _ in range(100):
            result = vector_sync.repair(app, space, limit=2)
            total += result["requeued"]
            if not result["scan_limit_reached"]:
                break
        with app.database.transaction() as connection:
            count = connection.scalar(
                select(func.count()).select_from(metadata.tables["vector_index_entries"])
            )
        assert total == count and total > 2
