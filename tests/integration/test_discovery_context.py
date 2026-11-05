"""Delivered C1 producers feed the same bounded discovery pipeline and safety gates."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from test_discovery import dataset, request
from test_platform_research import distribution_library, platform_export
from test_profile_conversion import owner_metrics, profile_export
from test_versioned_analytics import explicit_windows

from socialdna.application import (
    audience_service,
    context_service,
    platform_service,
    profile_service,
)
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.discovery_inputs import build
from socialdna.application.discovery_service import discover, reproduce
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.context import ContextExport
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.memory import documents, graph, lexical
from socialdna.research.candidates import DiscoverySpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def change(base: DiscoverySpec, **changes: Any) -> DiscoverySpec:
    return DiscoverySpec.model_validate({**base.model_dump(mode="json"), **changes})


def test_publication_models_complete_inventory_memory_and_erasure(
    settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "owned.json"
    dataset(path)
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        records = []
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            for c in range(16):
                account = repo.latest("account", stable_id("account", "demo", f"c{c}"))
                assert account
                posts = []
                for i in range(6):
                    post = repo.latest("post", stable_id("post", "demo", f"p{c}-{i}"))
                    assert post
                    posts.append(post.model_dump())
                    records.append(
                        {
                            "record_type": "publication_context",
                            "key": "historical",
                            "account": account.model_dump(),
                            "post": post.model_dump(),
                            "clock": {
                                "captured_at": "2026-02-01T00:00:00Z",
                                "validity_basis": "source_attested",
                                "valid_from": "2026-01-01T00:00:00Z",
                                "valid_until": "2026-02-01T00:00:00Z",
                            },
                            "published_original": f"2026-01-{i + 1:02}T01:00:00+01:00",
                            "timezone": "Europe/Berlin",
                            "native_format": "video",
                            "language": "en",
                            "language_basis": "source",
                            "title": {"state": "present", "value": "t" * (i + 1)},
                            "description": {"state": "not_collected"},
                            "caption": {"state": "not_collected"},
                            "niche": "education",
                            "audience": "controlled",
                        }
                    )
                records.append(
                    {
                        "record_type": "publishing_window",
                        "key": "inventory",
                        "account": account.model_dump(),
                        "captured_at": "2026-02-01T00:00:00Z",
                        "window_start": "2026-01-01T00:00:00Z",
                        "window_end": "2026-01-07T00:00:00Z",
                        "formats": ["video"],
                        "posts": posts,
                        "complete": True,
                        "includes_deleted_and_omitted": True,
                        "completeness_basis": "Controlled complete inventory",
                    }
                )
        exported = ContextExport.model_validate(
            {
                "dataset_id": "discovery-publishing",
                "source_uri": "urn:owned:publishing",
                "permission_basis": "Owned controlled sources",
                "records": records,
            }
        )
        imported = context_service.import_into_application(app, exported)
        pubs = [r["ref"] for r in imported["records"] if r["ref"]["kind"] == "publication_context"]
        windows = [r["ref"] for r in imported["records"] if r["ref"]["kind"] == "publishing_window"]
        options = request()
        source = {**options.input.model_dump(mode="json"), "publications": pubs, "windows": windows}
        candidates = [
            {
                "key": kind,
                "kind": kind,
                "features": ["publication.title_length"],
                "proposal_source": "prespecified historical packaging",
                "prediction": "Controlled title-length curve",
            }
            for kind in ("main", "quadratic")
        ]
        options = change(options, input=source, candidates=candidates)
        snapshot = build(app, options)
        assert len(snapshot["rows"]) == 96
        assert all(r["features"]["publication.cadence"] == 1 for r in snapshot["rows"])
        assert all(
            r["features"]["publication.hour_cos"] == pytest.approx(0.9659258263)
            for r in snapshot["rows"]
        )
        report = discover(app, options)
        assert report["result"]["selected"] == "quadratic"
        assert report["result"]["outer"]["evaluations"]["in_scope"]["mae"] < 2
        assert reproduce(app, EntityRef.model_validate(report["ref"]))["reproduced"]
        citation = EvidenceRef.model_validate(report["patterns"][0]["evidence"])
        with app.database.transaction() as connection:
            doc = documents.build(connection, "evidence", citation.revision_id)
            assert doc and doc["claim_level"] == "exploratory_observational"
            lexical.project(connection, doc)
            view = graph.neighborhood(
                connection, report["patterns"][0]["ref"]["revision_id"], depth=1
            )
            assert view["edges"]
            assert all(
                "not causation" in edge["qualification"]["interpretation"] for edge in view["edges"]
            )
        # A later metadata edit does not rewrite the frozen fit. It does make
        # that derived pattern historical in the default current memory view.
        edited = {
            **records[0],
            "title": {"state": "present", "value": "Later edited title"},
            "clock": {
                "captured_at": "2026-03-01T00:00:00Z",
                "validity_basis": "observed",
                "valid_from": "2026-03-01T00:00:00Z",
            },
        }
        context_service.import_into_application(
            app,
            exported.model_copy(
                update={
                    "records": ContextExport.model_validate(
                        {**exported.model_dump(mode="json"), "records": [edited]}
                    ).records
                }
            ),
        )
        with app.database.transaction() as connection:
            assert not documents.current_revision(
                connection, EntityRef.model_validate(report["patterns"][0]["ref"])
            )
            assert (
                graph.neighborhood(
                    connection, report["patterns"][0]["ref"]["revision_id"], depth=1
                )["nodes"]
                == []
            )
        assert reproduce(app, EntityRef.model_validate(report["ref"]))["reproduced"]
        plan = audience_service.redact(app, source_id=imported["source_id"])
        assert plan["counts"]["entity_revision"] > len(records)
        audience_service.redact(
            app,
            source_id=imported["source_id"],
            confirmation=plan["confirmation"],
            reason="Controlled source erasure",
        )
        with app.database.transaction() as connection:
            results = list(
                connection.scalars(select(metadata.tables["discovery_attempts"].c.result_json))
            )
            assert results and all(json.loads(r).get("redacted") for r in results)
        with pytest.raises(ConfigurationError, match="erased|Ineligible"):
            reproduce(app, EntityRef.model_validate(report["ref"]))


@pytest.mark.parametrize(
    ("platform", "surface"), [("instagram", "reels"), ("tiktok", "for_you"), ("youtube", "shorts")]
)
def test_distribution_actual_source_features_and_feedback_scope_gates(
    settings: Settings, account_export: Path, platform: str, surface: str
) -> None:
    raw = json.loads(account_export.read_text())
    for row in raw["records"]:
        row["platform"] = platform
        if "metric_key" in row:
            row["metric_key"] = row["metric_key"].replace("demo.", platform + ".")
        if "key" in row:
            row["key"] = row["key"].replace("demo.", platform + ".")
    account_export.write_text(json.dumps(raw))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        library = distribution_library(app, platform)
        scope = {
            "platform": platform,
            "surface": surface,
            "native_format": "video",
            "language": "en",
            "market": "US",
            "niche": "education",
            "audience": "controlled source cohort",
        }
        capability = platform_service.import_into_application(
            app,
            platform_export(
                [
                    {
                        "record_type": "platform_capabilities",
                        "key": "actual-source",
                        "account": library["account"],
                        "scope": scope,
                        "clock": {"captured_at": "2026-02-01T00:00:00Z"},
                        "analytics_permitted": True,
                        "access_scope": "authorized",
                        "collection_method": "authorized_export",
                        "source_report": "controlled",
                        "reviewer": "source reviewer",
                        "mapping_basis": "Source-native code",
                        "source_lag_seconds": 0,
                        "metrics": [
                            {
                                "definition": d,
                                "role": role,
                                "availability": "available",
                                "reason": "Supplied",
                            }
                            for d, role in zip(
                                library["definitions"], ("shares", "impressions"), strict=True
                            )
                        ],
                        "mappings": [
                            {"raw_code": "SOURCE_NATIVE", "surface": surface, "traffic": "organic"}
                        ],
                    }
                ]
            ),
        )["records"][0]["ref"]
        observed = platform_service.import_into_application(
            app,
            platform_export(
                [
                    {
                        "record_type": "distribution_observation",
                        "key": f"observed-{i}",
                        "account": library["account"],
                        "post": post,
                        "capabilities": capability,
                        "early": library["measurements"][2 * i],
                        "later": library["measurements"][2 * i + 1],
                        "raw_surface_code": "SOURCE_NATIVE",
                        "clock": {"captured_at": "2026-02-01T00:00:00Z"},
                    }
                    for i, post in enumerate(library["posts"])
                ]
            ),
        )
        options = change(
            request(),
            input={
                "kind": "distribution",
                "observations": [r["ref"] for r in observed["records"]],
                "timing": "retrospective_association",
            },
            scope={
                **request().scope.model_dump(mode="json"),
                **{k: v for k, v in scope.items() if k != "niche"},
                "objective": "recommendation",
                "traffic": "organic",
            },
            candidates=[
                {
                    "key": "response",
                    "kind": "main",
                    "features": ["distribution.early"],
                    "proposal_source": "source response",
                    "prediction": "Lagged association, not ranking weights",
                }
            ],
        )
        data = build(app, options)
        assert [r["features"]["distribution.early"] for r in data["rows"]] == [10, 20]
        assert [r["outcome"] for r in data["rows"]] == [100, 30]
        assert data["provenance"]["official_guidance"] == []
        with pytest.raises(ConfigurationError, match="not known"):
            build(
                app,
                change(
                    options,
                    input={
                        **options.input.model_dump(mode="json"),
                        "timing": "available_before_later_window",
                    },
                ),
            )
        incompatible = options.scope.model_copy(update={"language": "fr"})
        with pytest.raises(ConfigurationError, match="Incompatible"):
            build(app, change(options, scope=incompatible.model_dump(mode="json")))


def test_profile_literal_features_use_actual_source_attested_funnel_not_rubric_score(
    settings: Settings, account_export: Path
) -> None:
    explicit_windows(account_export)
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            account = EvidenceRepository(connection).latest(
                "account", stable_id("account", "demo", "0001")
            )
        assert account
        profile = {
            "record_type": "profile_snapshot",
            "key": "exposed",
            "account": account.model_dump(),
            "clock": {
                "captured_at": "2026-02-02T00:00:00Z",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_until": "2026-02-01T00:00:00Z",
                "validity_basis": "source_attested",
            },
            **{
                name: {"state": "not_collected"}
                for name in ("username", "display_name", "category", "positioning")
            },
            "bio": {"state": "present", "value": "Owned cooking lessons"},
            "declaration_basis": "owner_declared",
            "content_pillars": ["cooking"],
            "photo_state": "not_collected",
            "links_state": "empty",
            "pins_state": "empty",
        }
        snapshot = profile_service.import_into_application(app, profile_export([profile]))[
            "records"
        ][0]
        measured = owner_metrics(app, account.model_dump())
        definition = {
            "record_type": "funnel_definition",
            "key": "source-counter",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-02-02T00:00:00Z"},
            "reviewer": "source reviewer",
            "source_report": "controlled",
            "join_basis": "source_reported_nested_counts",
            "deduplication": "source_unique_per_window",
            "linkage_limitations": "Aggregate subset only",
            "bindings": [
                {
                    "definition": ref,
                    "signal": signal,
                    "uniqueness": "unique_accounts",
                    "source_event_code": signal,
                    "source_definition_excerpt": measured["definition_specs"][i][
                        "numerator_definition"
                    ],
                }
                for i, (ref, signal) in enumerate(
                    zip(measured["definitions"], measured["signals"], strict=True)
                )
            ],
        }
        manifest = profile_service.import_into_application(app, profile_export([definition]))[
            "records"
        ][0]
        funnel = {
            "record_type": "funnel_context",
            "key": "actual-funnel",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-02-03T00:00:00Z"},
            "definition": manifest["ref"],
            "profile": snapshot["ref"],
            "profile_exposure": "source_attested",
            "exposure_evidence": [snapshot["evidence"]],
            "stages": [
                {"key": signal, "measurement": ref}
                for signal, ref in zip(measured["signals"], measured["measurements"], strict=True)
            ],
            "rates": [
                {
                    "numerator": "follows",
                    "denominator": "profile_visits",
                    "source_reports_subset": True,
                    "linkage_evidence": [manifest["evidence"]],
                }
            ],
        }
        observed = profile_service.import_into_application(app, profile_export([funnel]))[
            "records"
        ][0]
        options = change(
            request(),
            input={
                "kind": "funnels",
                "observations": [observed["ref"]],
                "numerator": "follows",
                "denominator": "profile_visits",
            },
            scope={**request().scope.model_dump(mode="json"), "objective": "conversion"},
            candidates=[
                {
                    "key": "bio",
                    "kind": "main",
                    "features": ["profile.bio_length"],
                    "proposal_source": "literal source fields",
                    "prediction": "Aggregate association, not quality score",
                }
            ],
        )
        built = build(app, options)
        assert built["rows"][0]["features"]["profile.bio_length"] == len("Owned cooking lessons")
        assert built["rows"][0]["outcome"] == 0.1
        assert built["rows"][0]["measurement_members"]
        unknown = {
            **funnel,
            "key": "unknown-exposure",
            "profile_exposure": "unknown",
            "exposure_evidence": [],
        }
        other = profile_service.import_into_application(app, profile_export([unknown]))["records"][
            0
        ]
        with pytest.raises(ConfigurationError, match="exact-version exposure"):
            build(
                app,
                change(
                    options,
                    as_of=utc_now(),
                    input={**options.input.model_dump(mode="json"), "observations": [other["ref"]]},
                ),
            )
