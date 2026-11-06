import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sqlalchemy import func, select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.application.performance_service import (
    analyze_account,
    build_population,
    compare,
    reproduce,
)
from socialdna.application.report_service import generate_report
from socialdna.application.statistical_service import _begin_attempt
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EvidenceRef
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import CorrectedPerformanceSpec, PerformanceSpec
from socialdna.storage.schema import metadata

ACCOUNT = stable_id("account", "demo", "0001")


def corrected(**changes: Any) -> CorrectedPerformanceSpec:
    return CorrectedPerformanceSpec.model_validate(
        {
            "metric_key": "demo.views.v1",
            "estimand": "within_creator_association",
            "design": "within_creator",
            "feature_policy": "retrospective_content",
            "knowledge_cutoff": utc_now(),
            "publication_cutoff": "2026-11-01T00:00:00Z",
            "baseline_cutoff": "evaluation",
            "sampling_frame": "all authorized cooking fixture posts",
            "features": ["caption_length"],
            "covariates": ["caption_length"],
            "family_id": "fixture-family",
            "family_terms": ["caption_length"],
            "bootstrap_resamples": 200,
            **changes,
        }
    )


def explicit_windows(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    posts = {row["external_id"]: row for row in payload["records"] if row["record_type"] == "post"}
    for row in payload["records"]:
        if row["record_type"] == "metric_snapshot" and row.get("subject_type", "post") == "post":
            published = posts[row["subject_external_id"]]["published_at"]
            row["window_start"] = published
            row["window_end"] = (datetime.fromisoformat(published) + timedelta(days=7)).isoformat()
    path.write_text(json.dumps(payload))
    return payload


def test_actual_feature_timing_distinguishes_late_import_from_publication(
    settings: Settings,
    account_export: Path,
) -> None:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        spec = corrected(maturity_policy="collection_proxy", feature_policy="historical_prediction")
        rows, _ = build_population(app, spec, account_ids=[ACCOUNT])
        assert len(rows) == 6
        assert all(
            row["feature_values"]["caption_length"]["available_at"] > row["published_at"]
            for row in rows
        )
        assert all(not row["feature_values"]["caption_length"]["eligible"] for row in rows)
        assert all(row["outcome_available_at"] > row["snapshots"][0]["observed_at"] for row in rows)
        result = analyze_account(
            app, ACCOUNT, corrected(feature_policy="historical_prediction", model="ols")
        )
        assert result["results"]["regression"]["status"] == "insufficient_data"
        assert result["results"]["available_n"] == 0  # unknown source freshness, not known zero


def test_full_reference_history_and_new_analysis_at_same_cutoff_are_future_invariant(
    settings: Settings,
    account_export: Path,
) -> None:
    payload = explicit_windows(account_export)
    import_dataset(settings, account_export, "json")
    spec = corrected()
    target = stable_id("post", "demo", "p5")
    with open_application(settings) as app:
        report = compare(app, "posts", [target], [stable_id("post", "demo", "p4")], spec)
        baseline = next(r for r in report["results"]["creator_baselines"] if r["post_id"] == target)
        assert baseline["summary"]["n"] == 5  # not merely the selected p4 comparison post
        archived = generate_report(app, report["run_id"])
        original_bytes = Path(archived["path"]).read_bytes()
    payload["source"]["dataset_id"] = "future-import"
    payload["records"] = [
        {
            "record_type": "post",
            "platform": "demo",
            "external_id": "future",
            "account_external_id": "0001",
            "published_at": "2027-01-01T00:00:00Z",
            "caption": "Future",
        },
        {
            "record_type": "metric_snapshot",
            "platform": "demo",
            "subject_external_id": "future",
            "metric_key": "demo.views.v1",
            "observed_at": "2027-01-08T00:00:00Z",
            "value": 99999,
        },
        {
            "record_type": "post",
            "platform": "demo",
            "external_id": "p5",
            "account_external_id": "0001",
            "published_at": "2026-01-06T00:00:00Z",
            "caption": "A caption fetched after the cutoff",
        },
    ]
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        rebuilt = compare(app, "posts", [target], [stable_id("post", "demo", "p4")], spec)
        assert rebuilt["results"] == report["results"]
        assert rebuilt["posts"] == report["posts"]
        assert reproduce(app, report["run_id"])["results"] == report["results"]
        assert Path(archived["path"]).read_bytes() == original_bytes
        assert rebuilt["run_id"] != report["run_id"] and rebuilt["schema_version"] == "2.0"


def test_statistical_diagnostic_citations_survive_restart_and_propagate_withdrawal(
    settings: Settings,
    account_export: Path,
) -> None:
    explicit_windows(account_export)
    imported = import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        report = analyze_account(app, ACCOUNT, corrected(model="ols"))
        citation = EvidenceRef.model_validate(report["statistical_evidence"][0]["ref"])
        saved = generate_report(app, report["run_id"], "markdown")
        assert (
            "Baseline references" in saved["content"]
            and "Statistical citations" in saved["content"]
        )
        bytes_before = Path(saved["path"]).read_bytes()
        with app.database.transaction() as connection:
            assert connection.scalar(select(metadata.tables["reports"].c.schema_version)) == "2.0"
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            resolver = EvidenceResolver(connection)
            resolved = resolver.resolve(citation, purpose="new_claim", run_id=report["run_id"])
            assert resolved.locator_kind == "statistical_result"
            assert resolved.subject.kind == "statistical_analysis"
            with pytest.raises(ConfigurationError, match="requested run"):
                EvidenceResolver(connection).resolve(citation, run_id="wrong")
            withdraw(connection, source_id=imported["source_id"], reason="No longer authorized")
            # Reusing the resolver must not reuse pre-withdrawal eligibility.
            assert not resolver.resolve(citation).eligible
            with pytest.raises(ConfigurationError, match="Ineligible evidence"):
                EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        with pytest.raises(ConfigurationError, match="Withdrawn"):
            generate_report(app, report["run_id"])
        assert Path(saved["path"]).read_bytes() == bytes_before


def test_declared_family_records_null_attempts_and_rejects_consumed_holdouts(
    settings: Settings,
    account_export: Path,
) -> None:
    explicit_windows(account_export)
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        report = analyze_account(app, ACCOUNT, corrected(model="ols"))
        assert report["results"]["regression"]["status"] == "insufficient_data"
        spec = corrected(model="ols", split_policy="chronological", holdout_id="one-reservation")
        split = {
            "status": "ready",
            "train_post_ids": [stable_id("post", "demo", "p0")],
            "test_post_ids": [stable_id("post", "demo", "p5")],
        }
        _begin_attempt(app, [], spec, split, reproduced_from=None)
        with pytest.raises(ConfigurationError, match="Consumed holdout"):
            _begin_attempt(app, [], spec, split, reproduced_from=None)
        with pytest.raises(ConfigurationError, match="Consumed holdout"):
            _begin_attempt(
                app,
                [],
                spec.model_copy(update={"holdout_id": "renamed"}),
                split,
                reproduced_from=None,
            )
        _begin_attempt(app, [], spec, split, reproduced_from=report["run_id"])
        with pytest.raises(ConfigurationError, match="immutable"):
            analyze_account(app, ACCOUNT, corrected(age_days=8))
        with app.database.transaction() as connection:
            attempts = list(connection.execute(select(metadata.tables["test_attempts"])).mappings())
            assert any(
                r["status"] == "completed" and "insufficient_data" in r["result_json"]
                for r in attempts
            )
            assert sum(r["status"] == "refused" for r in attempts) == 2
            assert (
                connection.scalar(select(func.count()).select_from(metadata.tables["holdout_uses"]))
                == 1
            )


def test_partial_update_preserves_original_field_lineage(
    settings: Settings,
    account_export: Path,
) -> None:
    payload = explicit_windows(account_export)
    first = import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        before, _ = build_population(app, corrected(), account_ids=[ACCOUNT])
    payload["source"]["dataset_id"] = "partial-update"
    payload["records"] = [
        {
            "record_type": "post",
            "platform": "demo",
            "external_id": "p0",
            "account_external_id": "0001",
            "published_at": "2026-01-01T00:00:00Z",
            "title": "Changed title only",
        }
    ]
    account_export.write_text(json.dumps(payload))
    second = import_dataset(settings, account_export, "json")
    assert second["valid"], second
    with open_application(settings) as app:
        after, _ = build_population(app, corrected(), account_ids=[ACCOUNT])
        identity = stable_id("post", "demo", "p0")
        original = next(r for r in before if r["post_id"] == identity)["feature_values"][
            "caption_length"
        ]
        inherited = next(r for r in after if r["post_id"] == identity)["feature_values"][
            "caption_length"
        ]
        assert inherited["available_at"] == original["available_at"]
        assert inherited["lineage"]["source_ids"] == [first["source_id"]]
        assert second["source_id"] not in inherited["lineage"]["source_ids"]


def test_as_of_media_links_and_duplicate_hashes_use_production_batch(
    settings: Settings,
    account_export: Path,
    video: Path,
) -> None:
    payload = explicit_windows(account_export)
    payload["records"].extend(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": f"p{i}",
            "uri": video.as_uri(),
        }
        for i in range(6)
    )
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    cutoff_before = utc_now()
    with open_application(settings) as app:
        analyze_account(
            app,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        earlier, _ = build_population(
            app, corrected(knowledge_cutoff=cutoff_before), account_ids=[ACCOUNT]
        )
        now, _ = build_population(
            app,
            corrected(
                features=["duration_seconds", "caption_length"],
                family_terms=["duration_seconds", "caption_length"],
            ),
            account_ids=[ACCOUNT],
        )
        assert all(r["features"]["duration_seconds"] is None for r in earlier)
        assert all(r["features"]["duration_seconds"] == 3 for r in now)
        assert len({r["duplicate_group"] for r in now}) == 1
        assert all(r["duplicate_group"] for r in now)
        before_change = corrected(
            features=["duration_seconds", "caption_length"],
            family_terms=["duration_seconds", "caption_length"],
        )
    for record in payload["records"]:
        if record["record_type"] == "media" and record["post_external_id"] == "p0":
            record["uri"] = "changed-unavailable.mp4"
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        earlier, _ = build_population(app, before_change, account_ids=[ACCOUNT])
        latest, _ = build_population(app, corrected(), account_ids=[ACCOUNT])
        identity = stable_id("post", "demo", "p0")
        assert (
            next(r for r in earlier if r["post_id"] == identity)["features"]["duration_seconds"]
            == 3
        )
        assert (
            next(r for r in latest if r["post_id"] == identity)["features"]["duration_seconds"]
            is None
        )


@pytest.mark.parametrize("original_engine", ["0.0.4", "0.0.5", "0.0.19", "0.0.20", "0.0.25"])
def test_legacy_method_reproduction_does_not_reinterpret_archived_spec(
    settings: Settings,
    account_export: Path,
    original_engine: str,
) -> None:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        old = analyze_account(app, ACCOUNT, PerformanceSpec(metric_key="demo.views.v1"))
        with app.database.transaction() as connection:
            table = metadata.tables["statistical_analyses"]
            stored = json.loads(
                connection.scalar(
                    select(table.c.result_json).where(table.c.run_id == old["run_id"])
                )
            )
            stored["analysis_configuration"].pop("method_version")
            stored["analysis_configuration"]["engine_version"] = original_engine
            connection.execute(
                table.update()
                .where(table.c.run_id == old["run_id"])
                .values(result_json=json.dumps(stored))
            )
        assert reproduce(app, old["run_id"])["results"] == old["results"]
        new = analyze_account(app, ACCOUNT, corrected(maturity_policy="collection_proxy"))
        assert new["schema_version"] == "2.0" and old["schema_version"] == "1.0"
        assert new["results"] != old["results"]
        # Released corrected specs predate the optional creative fields. Their
        # frozen input/result hashes must still reproduce under the unchanged
        # numerical method, not be rebuilt with current creative defaults.
        with app.database.transaction() as connection:
            archived = json.loads(json.dumps(new))
            archived["analysis_configuration"]["engine_version"] = (
                original_engine if original_engine in {"0.0.19", "0.0.20", "0.0.25"} else "0.0.6"
            )
            for key in ("creative_recipes", "creative_annotation_key", "creative_label_policy"):
                archived["analysis_configuration"]["spec"].pop(key, None)
            table = metadata.tables["statistical_analyses"]
            connection.execute(
                table.update()
                .where(table.c.run_id == new["run_id"])
                .values(result_json=json.dumps(archived))
            )
        assert reproduce(app, new["run_id"])["results"] == new["results"]
        with app.database.transaction() as connection:
            table = metadata.tables["statistical_analyses"]
            corrupted = {**new, "reference_population": []}
            connection.execute(
                table.update()
                .where(table.c.run_id == new["run_id"])
                .values(result_json=json.dumps(corrupted))
            )
        with pytest.raises(StorageIntegrityError, match="reference inputs"):
            reproduce(app, new["run_id"])


def test_distinct_creator_account_comparison_has_real_matching_support(
    settings: Settings,
    account_export: Path,
) -> None:
    from copy import deepcopy

    payload = explicit_windows(account_export)
    originals = list(payload["records"])
    payload["records"].append(
        {
            "record_type": "account",
            "platform": "demo",
            "external_id": "other",
            "creator_key": "another-creator",
            "niche": "cooking",
        }
    )
    for record in originals:
        if (
            record["record_type"] not in ("post", "tag", "metric_snapshot")
            or record.get("subject_type") == "account"
        ):
            continue
        other = deepcopy(record)
        if other["record_type"] == "post":
            other["external_id"] = "q" + other["external_id"][1:]
            other["account_external_id"] = "other"
        elif other["record_type"] == "tag":
            other["post_external_id"] = "q" + other["post_external_id"][1:]
        else:
            other["subject_external_id"] = "q" + other["subject_external_id"][1:]
        payload["records"].append(other)
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        report = compare(
            app,
            "accounts",
            [ACCOUNT],
            [stable_id("account", "demo", "other")],
            corrected(design="cross_creator", estimand="cross_creator_comparison"),
        )
        comparison = report["results"]["comparison"]
        assert comparison["status"] == "supported_descriptive" and len(comparison["pairs"]) == 6
        assert comparison["effective_creator_count"] == 2
        assert comparison["matched_effect"]["estimate"] == 0
        assert comparison["matched_effect"]["ci_low"] is None


def test_production_model_pipeline_term_citation_and_single_use_validation(
    settings: Settings,
    account_export: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(account_export.read_text())
    payload["records"] = [
        r for r in payload["records"] if r["record_type"] in ("account", "metric_definition")
    ]
    rng = np.random.default_rng(3)
    for index in range(120):
        published = datetime.fromisoformat("2026-01-01T00:00:00+00:00") + timedelta(days=index)
        observed = published + timedelta(days=7)
        length = int(rng.integers(5, 40))
        payload["records"].extend(
            [
                {
                    "record_type": "post",
                    "platform": "demo",
                    "external_id": f"model{index}",
                    "account_external_id": "0001",
                    "published_at": published.isoformat(),
                    "caption": "x" * length,
                },
                {
                    "record_type": "metric_snapshot",
                    "platform": "demo",
                    "subject_external_id": f"model{index}",
                    "metric_key": "demo.views.v1",
                    "observed_at": observed.isoformat(),
                    "window_start": published.isoformat(),
                    "window_end": observed.isoformat(),
                    "value": int(100 + 3 * length + rng.integers(-2, 3)),
                },
            ]
        )
    account_export.write_text(json.dumps(payload))
    # Controlled clocks exercise the actual import→capture→materialize pipeline,
    # rather than injecting an optional feature_available_at into analytical rows.
    with monkeypatch.context() as clocks:
        clocks.setattr(
            "socialdna.application.account_import_service.utc_now",
            lambda: "2026-01-01T00:00:00.000000Z",
        )
        clocks.setattr(
            "socialdna.storage.evidence_repository.utc_now", lambda: "2026-01-01T00:00:00.000000Z"
        )
        assert import_dataset(settings, account_export, "json")["valid"]
    spec = corrected(model="ols", split_policy="chronological", holdout_id="actual-model-holdout")
    with open_application(settings) as app:
        report = analyze_account(app, ACCOUNT, spec)
        assert report["results"]["regression"]["status"] == "fitted_descriptive", report["results"]
        validation = report["results"]["validation"]
        assert validation["status"] == "evaluated", validation
        assert validation["evaluations"][0]["mae"] < 2
        term_citation = next(
            c for c in report["statistical_evidence"] if c["term"] == "caption_length"
        )
        with app.database.transaction() as connection:
            resolved = EvidenceResolver(connection).resolve(
                EvidenceRef.model_validate(term_citation["ref"]), purpose="new_claim"
            )
            assert resolved.locator.term == "caption_length"
        assert reproduce(app, report["run_id"])["results"] == report["results"]
        with pytest.raises(ConfigurationError, match="Consumed holdout"):
            analyze_account(app, ACCOUNT, spec)
        # A shifted split with a new name still overlaps the already inspected posts.
        with pytest.raises(ConfigurationError, match="Consumed holdout"):
            analyze_account(
                app,
                ACCOUNT,
                spec.model_copy(
                    update={"test_fraction": 0.25, "holdout_id": "renamed-and-shifted"}
                ),
            )


def test_superseded_metric_withdrawal_remains_a_frozen_analysis_dependency(
    settings: Settings,
    account_export: Path,
) -> None:
    payload = explicit_windows(account_export)
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        rows, _ = build_population(app, corrected(), account_ids=[ACCOUNT])
        previous = next(r for r in rows if r["post_id"] == stable_id("post", "demo", "p0"))[
            "snapshot_ids"
        ][0]
    snapshot = next(
        r
        for r in payload["records"]
        if r.get("metric_key") == "demo.views.v1" and r.get("subject_external_id") == "p0"
    )
    payload["source"]["dataset_id"] = "correction"
    payload["records"] = [{**snapshot, "value": 999}]
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as app:
        report = analyze_account(app, ACCOUNT, corrected())
        row = next(r for r in report["posts"] if r["post_id"] == stable_id("post", "demo", "p0"))
        assert previous not in row["snapshot_ids"] and previous in row["dependency_snapshot_ids"]
        with app.database.transaction() as connection:
            withdraw(
                connection,
                evidence_id=stable_id("metric-evidence", previous),
                reason="Old snapshot revoked",
            )
            citation = EvidenceRef.model_validate(report["statistical_evidence"][0]["ref"])
            assert not EvidenceResolver(connection).resolve(citation).eligible


def test_separately_imported_media_mapping_is_a_withdrawal_dependency(
    settings: Settings,
    account_export: Path,
    video: Path,
) -> None:
    payload = explicit_windows(account_export)
    assert import_dataset(settings, account_export, "json")["valid"]
    payload["source"]["dataset_id"] = "separate-media-mapping"
    payload["records"] = [
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": "p0",
            "uri": video.as_uri(),
        }
    ]
    account_export.write_text(json.dumps(payload))
    imported = import_dataset(settings, account_export, "json")
    assert imported["valid"]
    with open_application(settings) as app:
        analyze_account(
            app,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        report = analyze_account(app, ACCOUNT, corrected())
        row = next(r for r in report["posts"] if r["post_id"] == stable_id("post", "demo", "p0"))
        assert imported["source_id"] in row["source_ids"]
        with app.database.transaction() as connection:
            withdraw(connection, source_id=imported["source_id"], reason="Mapping revoked")
            citation = EvidenceRef.model_validate(report["statistical_evidence"][0]["ref"])
            assert not EvidenceResolver(connection).resolve(citation).eligible
