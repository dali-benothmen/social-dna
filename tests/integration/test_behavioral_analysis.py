import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from socialdna.application import behavioral_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.performance_service import analyze_account_outcomes
from socialdna.application.query_service import graph_query, query
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.behavioral import AccountOutcomeSpec, BehavioralExport
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.memory import QuerySpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import artifact_checks, database_checks, evidence_checks
from socialdna.storage.schema import metadata


def export(records: list[dict[str, Any]], **source_changes: Any) -> BehavioralExport:
    return BehavioralExport.model_validate(
        {
            "schema_version": "2.0",
            "source": {
                "dataset_id": "owned-behavior",
                "source_uri": "urn:owned:analytics",
                "permission_basis": "creator_owned_export",
                "analytics_permitted": True,
                **source_changes,
            },
            "records": records,
        }
    )


@pytest.fixture
def library(settings: Settings, account_export: Path) -> dict[str, Any]:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            account = repo.latest("account", stable_id("account", "demo", "0001"))
            posts = [repo.latest("post", stable_id("post", "demo", f"p{i}")) for i in range(6)]
        base = {
            "record_type": "behavioral_definition",
            "platform": "demo",
            "subject_type": "account",
            "meaning": "followers",
            "semantics": "count",
            "unit": "accounts",
            "domain": "nonnegative",
            "measurement": "cumulative",
            "numerator_definition": "account followers",
            "population_basis": "accounts",
            "replay_policy": "not_applicable",
            "source_definition_uri": "urn:owned:definitions",
            "description": "Source-defined authorized fixture; not a platform benchmark",
        }
        records = [
            {**base, "key": "demo.followers.behavior.v1"},
            {
                **base,
                "key": "demo.netgrowth.v1",
                "meaning": "net_growth",
                "semantics": "net_change",
                "domain": "signed",
                "measurement": "period",
                "numerator_definition": "signed net follower change",
            },
            {
                **base,
                "key": "demo.conversions.v1",
                "meaning": "conversion",
                "measurement": "period",
                "numerator_definition": "source attributed conversions",
                "aggregation": "sum_disjoint",
            },
            {
                **base,
                "key": "demo.retention.v1",
                "subject_type": "post",
                "meaning": "retention",
                "semantics": "ratio",
                "unit": "watch ratio",
                "measurement": "series",
                "numerator_definition": "watch events",
                "denominator_definition": "eligible plays",
                "population_basis": "plays",
                "replay_policy": "includes_replays",
            },
            {
                "record_type": "audience_cohort",
                "key": "owned-all",
                "account": account.model_dump(),
                "known": True,
                "eligibility": "All source-defined eligible plays/accounts",
                "aggregation_limitations": "Aggregate source assertions, "
                "no individual viewer records",
            },
        ]
        imported = service.import_into_application(app, export(records))
        refs = {r["key"]: r["ref"] for r in imported["records"]}
        return {
            "account": account.model_dump(),
            "posts": [p.model_dump() for p in posts],
            "definitions": refs,
            "cohort": refs["owned-all"],
        }


def clock(start: str, end: str) -> dict[str, Any]:
    return {
        "window_start": start,
        "window_end": end,
        "data_cutoff": end,
        "collected_at": utc_now(),
        "source_generated_at": end,
    }


def series(library: dict[str, Any], index: int = 0, **changes: Any) -> dict[str, Any]:
    start = datetime.fromisoformat("2026-01-01T00:00:00+00:00") + timedelta(days=index)
    return {
        "record_type": "metric_series",
        "key": f"post-{index}-retention",
        "subject": library["posts"][index],
        "definition": library["definitions"]["demo.retention.v1"],
        "cohort": library["cohort"],
        "clock": clock(start.isoformat(), (start + timedelta(days=7)).isoformat()),
        "coordinate_kind": "normalized_progress",
        "resolution": "Four source quarter-video bins",
        "convention": "half_open_intervals",
        "completeness": "complete_for_declared_grid",
        "expected_bins": 4,
        "bins": [
            {"ordinal": i, "start": i / 4, "end": (i + 1) / 4, "measurement": {"value": v}}
            for i, v in enumerate([1.2, 0.8, 0.9, 0.6])
        ],
        **changes,
    }


def followers(library: dict[str, Any], key: str, when: str, value: float) -> dict[str, Any]:
    return {
        "record_type": "metric_measurement",
        "key": key,
        "subject": library["account"],
        "definition": library["definitions"]["demo.followers.behavior.v1"],
        "cohort": library["cohort"],
        "clock": clock(when, when),
        "measurement": {"value": value},
    }


def outcome_spec(library: dict[str, Any], **changes: Any) -> AccountOutcomeSpec:
    return AccountOutcomeSpec.model_validate(
        {
            "definition": library["definitions"]["demo.followers.behavior.v1"],
            "cohort": library["cohort"],
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-08T00:00:00Z",
            **changes,
        }
    )


def test_retention_real_persistence_comparison_citations_report_restart(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        imported = service.import_into_application(
            app, export([series(library), series(library, 1)])
        )
        refs = [r["ref"] for r in imported["records"]]
        result = service.analyze_retention(app, series_id=refs[0]["id"], compare_id=refs[1]["id"])
        assert result["series"]["bins"][0]["result"]["value"] == 1.2
        assert result["series"]["bins"][0]["media_mapping"] is None
        assert result["comparison"]["status"] == "available"
        assert len(result["comparison"]["differences"]) == 4
        assert result["comparison"]["independent_viewers"] is None
        assert (
            service.analyze_retention(app, series_id=refs[0]["id"], compare_id=refs[1]["id"])[
                "run_id"
            ]
            == result["run_id"]
        )
        assert (
            service.import_into_application(
                app, export([series(library)], dataset_id="new-source")
            )["records"][0]["ref"]["id"]
            == refs[0]["id"]
        )
        with app.database.transaction() as connection:
            citation = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(result["series"]["bins"][0]["evidence"]),
                purpose="new_claim",
                post_id=library["posts"][0]["id"],
            )
            assert citation.locator_kind == "behavioral_record" and citation.eligible
        markdown = generate_report(app, result["run_id"], "markdown")
        assert "not independent viewers" in markdown["content"] and "1.2" in markdown["content"]
        assert all(
            c.status != "error"
            for c in database_checks(app) + evidence_checks(app) + artifact_checks(app)
        )
    with open_application(settings) as app:
        assert service.load_analysis(app, result["run_id"])["comparison"] == result["comparison"]
        remembered = query(app, QuerySpec(text="post-0-retention", owner_kind="metric_series"))
        assert remembered["hits"][0]["citations"][0]["locator_kind"] == "behavioral_record"
        bin_hit = query(app, QuerySpec(text="value", owner_kind="metric_bin"))["hits"][0]
        assert bin_hit["citations"][0]["eligible"]
        view = graph_query(app, bin_hit["owner"]["revision_id"])
        assert any(node["ref"]["kind"] == "metric_series" for node in view["nodes"])


def test_signed_account_endpoints_delays_and_exact_correction_history(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        service.import_into_application(
            app,
            export(
                [
                    followers(library, "start", "2026-01-01T00:00:00Z", 100),
                    followers(library, "end", "2026-01-08T00:00:00Z", 90),
                ]
            ),
        )
        result = analyze_account_outcomes(app, library["account"]["id"], outcome_spec(library))
        assert result["net_change"]["value"] == -10
        assert all(row["growth_attributed_to_post"] is None for row in result["post_context"])
        assert all(
            row["account_size_known_at_publication"]["value"] is None
            for row in result["post_context"]
        )
        assert result["attribution"]["source_reported_total"] is None
        before = utc_now()
        service.import_into_application(
            app, export([followers(library, "end", "2026-01-08T00:00:00Z", 80)])
        )
        corrected = analyze_account_outcomes(app, library["account"]["id"], outcome_spec(library))
        assert corrected["net_change"]["value"] == -20 and corrected["run_id"] != result["run_id"]
        historical = analyze_account_outcomes(
            app, library["account"]["id"], outcome_spec(library, knowledge_cutoff=before)
        )
        assert historical["net_change"]["value"] == -10
        assert service.load_analysis(app, result["run_id"])["net_change"]["value"] == -10
        with app.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(metadata.tables["signed_metric_changes"].c.value).where(
                        metadata.tables["signed_metric_changes"].c.revision_id
                        == result["net_change"]["ref"]["revision_id"]
                    )
                )
                == -10
            )
        assert "nearest post" in generate_report(app, corrected["run_id"], "markdown")["content"]


def test_public_only_missing_retention_is_not_a_scalar_proxy(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        result = service.analyze_retention(app, post_id=library["posts"][0]["id"])
        assert result["availability"] == "not_supplied" and result["series"] is None
        assert "not supplied" in generate_report(app, result["run_id"], "markdown")["content"]


def test_withdrawn_bin_withholds_series_and_frozen_reports_without_altering_archives(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        imported = service.import_into_application(app, export([series(library)]))["records"][0]
        result = service.analyze_retention(app, series_id=imported["ref"]["id"])
        report = generate_report(app, result["run_id"])
        original = Path(report["path"]).read_bytes()
        with app.database.transaction() as connection:
            withdraw(
                connection,
                evidence_id=imported["bins"][0]["evidence"]["id"],
                reason="Revoked bin use",
            )
            assert not EvidenceResolver(connection).resolve(imported["evidence"]["id"]).eligible
        assert not service.show(app, imported["ref"]["id"])["eligible"]
        with pytest.raises(ConfigurationError, match="[Ii]neligible|[Ww]ithdrawn"):
            generate_report(app, result["run_id"])
        assert Path(report["path"]).read_bytes() == original


def test_versioned_behavioral_cli_dry_run_and_restart(
    settings: Settings, library: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "owned-behavioral.json"
    path.write_text(export([series(library)]).model_dump_json())

    def cli(*args: str, data: Path = settings.data_dir) -> dict[str, Any]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "socialdna",
                "--offline",
                "--format",
                "json",
                "--data-dir",
                str(data),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)["data"]

    dry = tmp_path / "schema-only"
    assert not cli("import", "behavioral", str(path), "--dry-run", data=dry)["written"]
    assert not dry.exists()
    imported = cli("import", "behavioral", str(path))["records"][0]
    result = cli("analyze", "retention", "--series", imported["ref"]["id"])
    assert cli("behavioral", "show", imported["ref"]["id"])["eligible"]
    assert cli("evidence", "resolve", result["evidence"]["id"])["eligible"]
    assert (
        cli("report", "generate", "--run", result["run_id"])["content"]["report_type"]
        == "behavioral"
    )


def attribution(library: dict[str, Any], key: str, **changes: Any) -> dict[str, Any]:
    return {
        "record_type": "attribution_observation",
        "key": key,
        "subject": library["account"],
        "definition": library["definitions"]["demo.conversions.v1"],
        "cohort": library["cohort"],
        "clock": clock("2026-01-01T00:00:00Z", "2026-01-08T00:00:00Z"),
        "measurement": {"value": 10},
        "attribution_type": "platform_reported",
        "model": "Declared seven-day last-touch fixture; not causal identification",
        "lookback_start": "2025-12-31T00:00:00Z",
        "lookback_end": "2026-01-08T00:00:00Z",
        "allocation_policy": "fractional",
        "deduplication_key": key,
        "credits": [
            {"post": library["posts"][0], "weight": 0.5},
            {"post": library["posts"][1], "weight": 0.5},
        ],
        **changes,
    }


def test_attribution_is_source_reported_and_overlapping_or_duplicate_credits_are_not_added(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        service.import_into_application(
            app,
            export(
                [
                    followers(library, "s", "2026-01-01T00:00:00Z", 100),
                    followers(library, "e", "2026-01-08T00:00:00Z", 90),
                    attribution(library, "conversions"),
                ]
            ),
        )
        spec = outcome_spec(
            library, attribution_definition=library["definitions"]["demo.conversions.v1"]
        )
        result = analyze_account_outcomes(app, library["account"]["id"], spec)
        assert result["attribution"]["source_reported_total"] == 10
        assert result["attribution"]["causal_effect"] is None
        assert len(result["attribution"]["observations"][0]["spec"]["credits"]) == 2
        service.import_into_application(app, export([attribution(library, "another-window")]))
        overlap = analyze_account_outcomes(app, library["account"]["id"], spec)["attribution"]
        assert overlap["source_reported_total"] is None
        assert any("overlapping_conversion" in reason for reason in overlap["limitations"])
        # Independent source IDs cannot turn a duplicated aggregate event set into new conversions.
        service.import_into_application(
            app, export([attribution(library, "duplicate", deduplication_key="conversions")])
        )
        duplicate = analyze_account_outcomes(app, library["account"]["id"], spec)["attribution"]
        assert len(duplicate["duplicate_refs_excluded"]) == 1
        assert duplicate["source_reported_total"] is None


def test_signed_supplied_change_missing_endpoints_and_source_withdrawal(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        spec = outcome_spec(library)
        missing = analyze_account_outcomes(app, library["account"]["id"], spec)
        assert missing["net_change"] is None and missing["status"] == "partial"
        supplied = {
            "record_type": "metric_measurement",
            "key": "net-supplied",
            "subject": library["account"],
            "definition": library["definitions"]["demo.netgrowth.v1"],
            "cohort": library["cohort"],
            "clock": clock(spec.start, spec.end),
            "measurement": {"value": -12},
        }
        imported = service.import_into_application(app, export([supplied]))
        direct = analyze_account_outcomes(
            app,
            library["account"]["id"],
            outcome_spec(
                library,
                mode="supplied_change",
                definition=library["definitions"]["demo.netgrowth.v1"],
            ),
        )
        assert direct["net_change"]["value"] == -12
        with app.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Analytics source revoked")
        with pytest.raises(ConfigurationError, match="[Ii]neligible|[Ww]ithdrawn"):
            service.load_analysis(app, direct["run_id"])


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"coordinate_kind": "provider_index"}, "different_coordinate_kind"),
        ({"resolution": "Different provider spacing"}, "different_resolution"),
        ({"completeness": "partial"}, "incomplete_or_overlapping_grid"),
    ],
)
def test_incompatible_series_are_reported_not_implicitly_aligned(
    settings: Settings, library: dict[str, Any], change: dict[str, Any], reason: str
) -> None:
    with open_application(settings) as app:
        imported = service.import_into_application(
            app, export([series(library), series(library, 1, **change)])
        )
        a, b = [r["ref"]["id"] for r in imported["records"]]
        result = service.analyze_retention(app, series_id=a, compare_id=b)
        assert result["comparison"]["status"] == "incompatible"
        assert (
            reason in result["comparison"]["reasons"] and result["comparison"]["differences"] == []
        )


def test_missing_suppressed_bins_and_source_freshness_remain_explicit(
    settings: Settings, library: dict[str, Any]
) -> None:
    raw = series(library)
    raw["bins"][1]["measurement"] = {
        "value": None,
        "availability": "source_suppressed",
        "reason": "Source privacy threshold",
    }
    with open_application(settings) as app:
        imported = service.import_into_application(app, export([raw, series(library, 1)]))
        a, b = [r["ref"]["id"] for r in imported["records"]]
        result = service.analyze_retention(app, series_id=a, compare_id=b)
        assert result["status"] == "partial"
        assert result["series"]["coverage"]["missing_or_suppressed_bins"] == 1
        assert result["comparison"]["differences"][1]["difference"] is None
        assert result["series"]["bins"][1]["result"]["availability"] == "source_suppressed"
        raw = series(library, key="unknown-freshness")
        raw["clock"]["data_cutoff"] = None
        unknown = service.import_into_application(app, export([raw]))["records"][0]["ref"]["id"]
        result = service.analyze_retention(app, series_id=unknown, compare_id=b)
        assert "unknown_or_incomplete_source_freshness" in result["comparison"]["reasons"]


def test_definition_changes_and_invalid_batch_leave_no_canonical_or_raw_writes(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            original = json.loads(
                EvidenceRepository(connection).entity(
                    EntityRef.model_validate(library["definitions"]["demo.retention.v1"])
                )["payload_json"]
            )["spec"]
        changed = {**original, "description": "Changed same-version semantics"}
        with pytest.raises(ConfigurationError, match="new versioned key"):
            service.import_into_application(app, export([changed]))
        raw = series(library)
        raw["subject"] = library["account"]
        # Structurally wrong series subjects are rejected by the versioned schema.
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            export([raw])
        raw = series(library)
        raw["definition"] = library["definitions"]["demo.followers.behavior.v1"]
        before = sorted(p for p in app.paths.artifacts.rglob("*") if p.is_file())
        with pytest.raises(ConfigurationError, match="subject"):
            service.import_into_application(
                app, export([series(library, key="must-rollback"), raw])
            )
        assert before == sorted(p for p in app.paths.artifacts.rglob("*") if p.is_file())
        with app.database.transaction() as connection:
            assert not connection.scalar(select(metadata.tables["metric_series"].c.revision_id))


def test_actual_media_event_overlay_keeps_coarse_boundaries_and_frozen_context(
    settings: Settings, library: dict[str, Any], video: Path, account_export: Path
) -> None:
    from socialdna.application.creative_service import import_into_application as creative_import
    from socialdna.application.import_service import import_local
    from socialdna.application.performance_service import analyze_account
    from socialdna.domain.creative import CreativeAnnotationSet
    from socialdna.domain.media import AnalysisOptions
    from socialdna.domain.research import PerformanceSpec
    from socialdna.media.timeline import timeline

    document = json.loads(account_export.read_text())
    document["records"].append(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p0",
            "uri": video.as_uri(),
        }
    )
    account_export.write_text(json.dumps(document))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        media = import_local(app, video)
        analyze_account(
            app,
            library["account"]["id"],
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            max_posts=1,
            media_options=AnalysisOptions(no_ai=True),
        )
        with app.database.transaction() as connection:
            media_ref = EvidenceRepository(connection).latest("media", media["media_id"])
            sha = EvidenceRepository(connection).get("media_assets", media["media_id"])["sha256"]
        creative = CreativeAnnotationSet.model_validate(
            {
                "key": "controlled-opening",
                "media_sha256": sha,
                "permission_basis": "Owned software fixture; not a recognition benchmark",
                "protocol": {
                    "origin": "human",
                    "author": "fixture",
                    "procedure": "controlled assertion",
                    "outcome_access": "blinded",
                },
                "events": [
                    {
                        "key": "opening",
                        "technique": "finished_dish",
                        "description": "Controlled opening fixture",
                        "modalities": ["visual"],
                        "anchors": [
                            {
                                "start_min_ms": 0,
                                "start_max_ms": 0,
                                "end_min_ms": 700,
                                "end_max_ms": 700,
                            }
                        ],
                        "state": "reviewed",
                        "reviewer": "fixture",
                    }
                ],
            }
        )
        event = creative_import(app, creative)["events"][0]
        imported = service.import_into_application(
            app, export([series(library, media=media_ref.model_dump())])
        )["records"][0]
        result = service.analyze_retention(app, series_id=imported["ref"]["id"])
        assert result["series"]["bins"][0]["media_mapping"]["end_ms"] == 750
        assert len(result["series"]["bins"]) == 4
        assert result["creative_context"]["events"][0]["ref"] == event["ref"]
        assert "behavioral" not in timeline(app, media["media_id"])
        overlay = timeline(app, media["media_id"], include_behavioral=True)["behavioral"]
        assert overlay["creative_context"]["events"][0]["ref"] == event["ref"]
        assert (
            "Controlled opening fixture"
            in generate_report(app, result["run_id"], "markdown")["content"]
        )
        # Removing an event from the current annotation set removes the current
        # overlay, without rewriting the previously frozen behavioral report.
        changed = creative.model_dump(mode="json")
        changed["events"] = []
        creative_import(app, CreativeAnnotationSet.model_validate(changed))
        new = service.analyze_retention(app, series_id=imported["ref"]["id"])
        assert not new["creative_context"]["events"]
        assert service.load_analysis(app, result["run_id"])["creative_context"]["events"]


def test_unknown_cohorts_prevent_series_comparisons_and_account_change(
    settings: Settings, library: dict[str, Any]
) -> None:
    with open_application(settings) as app:
        cohort = {
            "record_type": "audience_cohort",
            "key": "unknown-cohort",
            "account": library["account"],
            "known": False,
            "eligibility": "Source did not disclose cohort filters",
            "aggregation_limitations": "Not established as comparable",
        }
        unknown = service.import_into_application(app, export([cohort]))["records"][0]["ref"]
        imported = service.import_into_application(
            app, export([series(library, cohort=unknown), series(library, 1, cohort=unknown)])
        )
        result = service.analyze_retention(
            app,
            series_id=imported["records"][0]["ref"]["id"],
            compare_id=imported["records"][1]["ref"]["id"],
        )
        assert "unknown_cohort" in result["comparison"]["reasons"]
        start = followers(library, "unknown-start", "2026-01-01T00:00:00Z", 100)
        end = followers(library, "unknown-end", "2026-01-08T00:00:00Z", 90)
        start["cohort"], end["cohort"] = unknown, unknown
        service.import_into_application(app, export([start, end]))
        change = analyze_account_outcomes(
            app, library["account"]["id"], outcome_spec(library, cohort=unknown)
        )
        assert change["net_change"] is None


def test_behavioral_research_citations_are_qualified_and_withdrawal_is_transitive(
    settings: Settings, library: dict[str, Any], tmp_path: Path
) -> None:
    from socialdna.application.research_service import generate_research_report, register_research

    with open_application(settings) as app:
        imported = service.import_into_application(app, export([series(library)]))
        evidence = imported["records"][0]["bins"][0]["evidence"]
    path = tmp_path / "behavioral-research.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "behavioral-context",
                "question": "Which source-defined retention observations are actually available?",
                "population": "Owned controlled software fixtures",
                "evidence": [evidence],
            }
        )
    )
    registered = register_research(settings, path)
    with open_application(settings) as app:
        report = generate_research_report(
            app, registered["question"]["id"], report_format="markdown"
        )
        assert (
            "behavioral evidence" in report["content"]
            and "not independent viewers" in report["content"]
        )
        with app.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Analytics revoked")
        current = generate_research_report(app, registered["question"]["id"])
        assert not current["content"]["citations"][0]["eligible"]
        assert current["content"].get("behavioral_evidence", []) == []


def test_historical_missing_retention_uses_the_post_revision_actually_known_then(
    settings: Settings, library: dict[str, Any], account_export: Path
) -> None:
    before = utc_now()
    document = json.loads(account_export.read_text())
    next(
        r
        for r in document["records"]
        if r.get("record_type") == "post" and r.get("external_id") == "p0"
    )["caption"] = "Corrected later caption"
    account_export.write_text(json.dumps(document))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        result = service.analyze_retention(app, post_id=library["posts"][0]["id"], as_of=before)
        assert result["availability"] == "not_supplied" and result["target"] == library["posts"][0]
        with pytest.raises(ConfigurationError, match="explicit series ID"):
            service.analyze_retention(
                app, post_id=library["posts"][0]["id"], revision="not-a-series-revision"
            )
