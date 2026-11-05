"""Actual canonical import → context/outcome alignment → reload → withdrawal/erasure."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from test_versioned_analytics import ACCOUNT, corrected, explicit_windows
from typer.testing import CliRunner

from socialdna.application import audience_service
from socialdna.application import context_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.performance_service import compare
from socialdna.cli.app import app as cli
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.context import ContextExport, PublicationReportSpec
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.memory import QuerySpec
from socialdna.memory import documents, hybrid, lexical
from socialdna.storage import context_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import artifact_checks, database_checks


def document(app: Any) -> dict[str, Any]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        account = repo.latest("account", ACCOUNT)
        posts = [repo.latest("post", stable_id("post", "demo", f"p{i}")) for i in range(6)]
        assert account and all(posts)
        records = []
        for i, post in enumerate(posts):
            assert post is not None
            published = json.loads(repo.entity(post)["payload_json"])["published_at"]
            # Preserve an explicitly supplied local representation, not a guessed zone.
            from zoneinfo import ZoneInfo

            local = datetime.fromisoformat(published).astimezone(ZoneInfo("Europe/Berlin"))
            records.append(
                {
                    "record_type": "publication_context",
                    "key": "packaging",
                    "account": account.model_dump(),
                    "post": post.model_dump(),
                    "clock": {"captured_at": "2026-02-01T00:00:00Z"},
                    "published_original": local.isoformat(),
                    "timezone": "Europe/Berlin",
                    "native_format": "video",
                    "language": "en",
                    "language_basis": "source",
                    "title": {"state": "present", "value": f"Crème 🍋 fixture {i}"},
                    "description": {"state": "not_collected"},
                    "caption": {"state": "empty", "value": ""},
                    "niche": "cooking",
                    "audience": "fixture audience",
                }
            )
        records.append(
            {
                "record_type": "publishing_window",
                "key": "complete-week",
                "account": account.model_dump(),
                "captured_at": "2026-02-01T00:00:00Z",
                "window_start": "2026-01-01T00:00:00Z",
                "window_end": "2026-01-07T00:00:00Z",
                "formats": ["video"],
                "posts": [p.model_dump() for p in posts if p],
                "complete": True,
                "includes_deleted_and_omitted": True,
                "completeness_basis": "Source-attested complete controlled export, "
                "not inferred from selected successes",
            }
        )
    return {
        "schema_version": "1.0",
        "dataset_id": "publication-fixture",
        "source_uri": "urn:fixture:publishing",
        "permission_basis": "owned controlled export",
        "records": records,
    }


def test_publication_performance_citations_history_restart_and_erasure(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    explicit_windows(account_export)
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        raw = document(app)
        image = tmp_path / "owned-thumbnail.png"
        Image.new("RGB", (16, 16), "red").save(image)
        raw["records"][0]["thumbnails"] = [
            {
                "variant": "original",
                "placement": "feed-cover",
                "path": str(image),
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            }
        ]
        spec = ContextExport.model_validate(raw)
        imported = service.import_into_application(app, spec)
        assert service.import_into_application(app, spec) == imported
        refs = [EntityRef.model_validate(r["ref"]) for r in imported["records"]]
        posts = [stable_id("post", "demo", f"p{i}") for i in range(6)]
        performance = compare(app, "posts", posts[::2], posts[1::2], corrected(model="none"))
        assert len(performance["results"]["comparison"]["pairs"]) == 3
        request = PublicationReportSpec(
            publications=tuple(refs[:6]),
            window=refs[6],
            objective="recommendation",
            surface="fixture_feed",
            outcome_mapping_basis="Source-labelled fixture views; no search or conversion claim",
            analysis_run_id=performance["run_id"],
            as_of=utc_now(),
        )
        report = service.publication_report(app, request)
        from socialdna.application.investigation_service import _scope_evidence

        with app.database.transaction() as connection:
            assert (
                _scope_evidence(
                    connection,
                    EvidenceRef.model_validate(imported["records"][0]["evidence"]),
                    performance["posts"],
                )["kind"]
                == "context_record"
            )
            with pytest.raises(ConfigurationError, match="outside"):
                _scope_evidence(
                    connection, EvidenceRef.model_validate(report["evidence"]), performance["posts"]
                )
        assert report["result"]["cadence"]["value"] == 1
        assert all(
            row["local_hour"] == 1 and row["utc_offset_seconds"] == 3600
            for row in report["result"]["rows"]
        )
        assert sorted(row["outcome"] for row in report["result"]["rows"]) == [
            100,
            200,
            300,
            400,
            500,
            600,
        ]
        assert not report["result"]["comparison"]["new_context_effect_estimated"]
        with app.database.transaction() as connection:
            citation = repository.cite(connection, refs[0], field="title/value", start=0, end=7)
            assert EvidenceResolver(connection).resolve(citation).locator.quote == "Crème 🍋"
            payload = repository.read(connection, refs[0])
            asset = payload["spec"]["thumbnails"][0]["artifact_id"]
            assert (
                EvidenceResolver(connection)
                .resolve(repository.cite(connection, refs[0], artifact_id=asset))
                .eligible
            )
            with pytest.raises(ConfigurationError, match="Artifact"):
                repository.cite(connection, refs[1], artifact_id=asset)
            artifact = EvidenceRepository(connection).get("artifact_objects", report["artifact_id"])
            frozen_path = app.artifacts.path_for(artifact["relative_path"])
            frozen = frozen_path.read_bytes()
        changed = json.loads(canonical_json(raw))
        changed["records"][0]["title"]["value"] = "Edited packaging"
        revised = service.import_into_application(app, ContextExport.model_validate(changed))
        assert revised["records"][0]["ref"]["id"] == refs[0].id
        assert revised["records"][0]["ref"]["revision_id"] != refs[0].revision_id
        assert service.publication_report(app, request)["ref"] == report["ref"]
        assert frozen_path.read_bytes() == frozen
        with pytest.raises(ConfigurationError, match="not known"):
            service.publication_report(
                app, request.model_copy(update={"policy": "historical_prediction"})
            )
        bad = json.loads(canonical_json(raw))
        bad["records"][-1]["posts"].pop()
        with pytest.raises(ConfigurationError, match="omits known"):
            service.import_into_application(app, ContextExport.model_validate(bad))
        sparse = json.loads(canonical_json(raw))
        sparse["records"][-1]["complete"] = False
        incomplete = service.import_into_application(app, ContextExport.model_validate(sparse))
        incomplete_ref = EntityRef.model_validate(incomplete["records"][-1]["ref"])
        assert (
            service.publication_report(
                app, request.model_copy(update={"window": incomplete_ref, "as_of": utc_now()})
            )["result"]["cadence"]["value"]
            is None
        )
        checks = database_checks(app) + artifact_checks(app)
        assert all(c.status != "error" for c in checks), checks
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "context",
            "show",
            report["ref"]["id"],
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["data"]["content"]["result"] == report["result"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            citation = repository.cite(connection, refs[1], field="title/value", start=0, end=7)
            doc = documents.build(connection, "evidence", citation.revision_id)
            assert doc
            lexical.project(connection, doc)
        assert hybrid.search(app, QuerySpec(text="Crème"))["hits"]
        with app.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Permission revoked")
            assert (
                not EvidenceResolver(connection)
                .resolve(EvidenceRef.model_validate(report["evidence"]))
                .eligible
            )
        assert not hybrid.search(app, QuerySpec(text="Crème"))["hits"]
        assert frozen_path.read_bytes() == frozen
        plan = audience_service.redact(app, source_id=imported["source_id"])
        assert plan["counts"]["entity_revision"] >= 8
        audience_service.redact(
            app,
            source_id=imported["source_id"],
            confirmation=plan["confirmation"],
            reason="Erase owned imported metadata",
        )
        assert not frozen_path.exists()
        with pytest.raises(ConfigurationError, match="erased"):
            service.import_into_application(app, spec)


def test_invalid_context_cli_has_no_initialization(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"bad"}')
    data = tmp_path / "no-library"
    result = CliRunner().invoke(
        cli,
        ["--data-dir", str(data), "--format", "json", "context", "import", str(path), "--dry-run"],
    )
    assert result.exit_code != 0 and json.loads(result.stdout)["status"] == "error"
    assert not data.exists()


def test_dated_trends_unknown_zones_and_scope_gates(
    settings: Settings, account_export: Path
) -> None:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        raw = document(app)
        raw["records"][0]["timezone"] = None
        imported = service.import_into_application(app, ContextExport.model_validate(raw))
        refs = tuple(EntityRef.model_validate(r["ref"]) for r in imported["records"][:6])
        trend = {
            "record_type": "trend_context",
            "key": "dated-query",
            "account": raw["records"][0]["account"],
            "clock": {"captured_at": "2026-02-01T00:00:00Z"},
            "platform": "demo",
            "objective": "search",
            "surface": "demo_search",
            "language": "en",
            "locale": "en-US",
            "niche": "cooking",
            "audience": "fixture audience",
            "query": "cooking",
            "observation_start": "2025-12-01T00:00:00Z",
            "observation_end": "2025-12-31T00:00:00Z",
            "observation": "Source-labelled software fixture; no forecast or universal search rank",
            "basis": "explicit_observation",
        }
        raw["records"] = [trend]
        imported_trend = service.import_into_application(app, ContextExport.model_validate(raw))
        ref = EntityRef.model_validate(imported_trend["records"][0]["ref"])
        request = PublicationReportSpec(
            publications=refs,
            trends=(ref,),
            objective="search",
            surface="demo_search",
            outcome_mapping_basis="Declared research objective only",
            as_of=utc_now(),
        )
        report = service.publication_report(app, request)
        assert report["result"]["rows"][0]["local_hour"] is None
        assert report["result"]["trends"][0]["query"] == "cooking"
        assert report["result"]["channel_status"] == "declared_objective_not_verified_traffic"
        for change in ({"objective": "recommendation"}, {"surface": "other_surface"}):
            with pytest.raises(ConfigurationError, match="mismatch"):
                service.publication_report(app, request.model_copy(update=change))
        trend["observation_end"] = "2026-01-02T00:00:00Z"
        future = service.import_into_application(app, ContextExport.model_validate(raw))
        future_ref = EntityRef.model_validate(future["records"][0]["ref"])
        with pytest.raises(ConfigurationError, match="Future trend"):
            service.publication_report(
                app, request.model_copy(update={"trends": (future_ref,), "as_of": utc_now()})
            )
        trend["platform"] = "youtube"
        with pytest.raises(ConfigurationError, match="platform differs"):
            service.import_into_application(app, ContextExport.model_validate(raw))
