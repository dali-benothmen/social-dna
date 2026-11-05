"""Persistence and attempt/holdout lifecycle for explicit versioned designs.

The numerical engine remains in analytics. This service owns atomic canonical
snapshots and universal citations; legacy performance-1 execution is unchanged.
"""

import importlib.metadata
from typing import Any

from sqlalchemy import Connection, or_, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.analytics.statistics import analyze_designed_rows
from socialdna.analytics.validation import designed_split
from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver, assert_active_inputs
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import StatisticalLocator
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def assert_design_inputs(connection: Connection, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        assert_active_inputs(
            connection,
            source_ids=tuple(row["source_ids"]),
            evidence_ids=tuple(
                stable_id("metric-evidence", item) for item in row["dependency_snapshot_ids"]
            ),
        )
        for identity in row["feature_evidence_ids"]:
            EvidenceResolver(connection).resolve(identity, purpose="new_claim")


def _begin_attempt(
    application: Application,
    rows: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    split: dict[str, Any],
    *,
    reproduced_from: str | None,
) -> tuple[str, dict[str, Any]]:
    family = {
        "terms": spec.family_terms,
        "metric_key": spec.metric_key,
        "numerator_keys": spec.numerator_keys,
        "denominator_key": spec.denominator_key,
        "age_days": float(spec.age_days),
        "age_tolerance_days": float(spec.age_tolerance_days),
        "window_seconds": spec.window_seconds,
        "estimand": spec.estimand,
    }
    identity, refusal = new_id(), None
    with application.database.transaction() as connection:
        table = metadata.tables["test_families"]
        existing = connection.scalar(select(table.c.spec_json).where(table.c.id == spec.family_id))
        if existing and existing != canonical_json(family):
            raise ConfigurationError(
                "Declared family is immutable; use a distinct ID for a different family"
            )
        connection.execute(
            insert(table)
            .values(id=spec.family_id, spec_json=canonical_json(family), created_at=utc_now())
            .on_conflict_do_nothing()
        )
        uses = metadata.tables["holdout_uses"]
        # Fingerprint post IDs, not values: changing outcomes/predictors or renaming
        # a reservation does not turn the same inspected posts into a new holdout.
        fingerprint = hash_config({"test_post_ids": sorted(split["test_post_ids"])})
        members = metadata.tables["holdout_members"]
        by_id = {row["post_id"]: row for row in rows}
        member_values = [
            {"member_key": "post:" + identity, "post_id": identity, "media_sha256": None}
            for identity in split["test_post_ids"]
        ]
        for digest in sorted(
            {
                by_id[identity]["duplicate_group"]
                for identity in split["test_post_ids"]
                if identity in by_id and by_id[identity].get("duplicate_group")
            }
        ):
            member_values.append(
                {"member_key": "sha256:" + digest, "media_sha256": digest, "post_id": None}
            )
        reserved = bool(spec.holdout_id and split["test_post_ids"] and not reproduced_from)
        if reserved and (
            connection.scalar(
                select(uses.c.id).where(
                    or_(uses.c.id == spec.holdout_id, uses.c.fingerprint == fingerprint)
                )
            )
            or connection.scalar(
                select(members.c.member_key).where(
                    members.c.member_key.in_([member["member_key"] for member in member_values])
                )
            )
        ):
            refusal = (
                "Consumed holdout cannot support another independent validation; "
                "reproduction is allowed"
            )
        count = len(
            list(
                connection.scalars(
                    select(metadata.tables["test_attempts"].c.id).where(
                        metadata.tables["test_attempts"].c.family_id == spec.family_id
                    )
                )
            )
        )
        connection.execute(
            metadata.tables["test_attempts"]
            .insert()
            .values(
                id=identity,
                family_id=spec.family_id,
                status="refused" if refusal else "started",
                result_json=canonical_json(
                    {
                        "spec": spec.model_dump(mode="json"),
                        "input_hash": hash_config({"rows": rows}),
                        "refusal": refusal,
                        "reproduced_from": reproduced_from,
                    }
                ),
                created_at=utc_now(),
            )
        )
        if reserved and not refusal:
            connection.execute(
                uses.insert().values(
                    id=spec.holdout_id,
                    fingerprint=fingerprint,
                    attempt_id=identity,
                    split_json=canonical_json(split),
                    consumed_at=utc_now(),
                )
            )
            connection.execute(
                members.insert(),
                [{**member, "holdout_id": spec.holdout_id} for member in member_values],
            )
    if refusal:
        raise ConfigurationError(refusal)
    return identity, {
        "family_id": spec.family_id,
        "attempt_id": identity,
        "prior_attempts": count,
        "independent_confirmation": False,
        "holdout_reservation": spec.holdout_id,
        "reproduced_from": reproduced_from,
    }


def persist_designed_analysis(
    application: Application,
    rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    target_type: str,
    target_id: str,
    *,
    comparing: bool,
    batch: list[dict[str, Any]] | None,
    history: list[dict[str, Any]],
    reproduced_from: str | None,
    expected_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        assert_design_inputs(connection, rows + history)
    split = designed_split(rows, spec)
    attempt_id, ledger = _begin_attempt(
        application, rows, spec, split, reproduced_from=reproduced_from
    )
    try:
        results = analyze_designed_rows(rows, history, spec, comparing=comparing, split=split)
        return _save(
            application,
            rows,
            definitions,
            history,
            spec,
            target_type,
            target_id,
            batch or [],
            results,
            attempt_id,
            ledger,
            expected_results,
        )
    except Exception as exc:
        # Deliberately catch to record a failed attempt, then re-raise unchanged.
        with application.database.transaction() as connection:
            connection.execute(
                metadata.tables["test_attempts"]
                .update()
                .where(metadata.tables["test_attempts"].c.id == attempt_id)
                .values(
                    status="failed",
                    result_json=canonical_json(
                        {
                            "spec": spec.model_dump(mode="json"),
                            "input_hash": hash_config({"rows": rows}),
                            "error_type": type(exc).__name__,
                        }
                    ),
                )
            )
        raise


def _save(
    application: Application,
    rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    history: list[dict[str, Any]],
    spec: CorrectedPerformanceSpec,
    target_type: str,
    target_id: str,
    batch: list[dict[str, Any]],
    results: dict[str, Any],
    attempt_id: str,
    ledger: dict[str, Any],
    expected_results: dict[str, Any] | None,
) -> dict[str, Any]:
    run_id, now = new_id(), utc_now()
    analysis_id, cohort_id = stable_id("statistics", run_id), stable_id("cohort", run_id)
    configuration = {
        "method_version": "performance-2",
        "spec": spec.model_dump(mode="json"),
        "input_hash": hash_config({"rows": rows, "definitions": definitions}),
        "reference_hash": hash_config({"rows": history}),
        "engine_version": __version__,
        "libraries": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "pandas", "statsmodels", "scikit-learn")
        },
        "reproduced_from": ledger["reproduced_from"],
    }
    report = {
        "schema_version": "2.0",
        "report_type": "performance",
        "run_id": run_id,
        "target_type": target_type,
        "target_id": target_id,
        "status": "partial" if any(r["status"] != "success" for r in batch) else "success",
        "analysis_configuration": configuration,
        "metric_definitions": definitions,
        "results": results,
        "posts": rows,
        "reference_population": history,
        "test_ledger": ledger,
        "statistical_evidence": [],
        "batch": batch,
        "limitations": results["limitations"],
    }
    if any(r["creator_identity"] == "account_proxy" for r in rows):
        results["limitations"].append("Account proxies can overcount independent creator clusters.")
    if expected_results is not None and hash_config(results) != hash_config(expected_results):
        raise StorageIntegrityError("Recomputed versioned results differ from the frozen results")
    with application.database.transaction() as connection:
        assert_design_inputs(connection, rows + history)
        connection.execute(
            metadata.tables["analysis_runs"]
            .insert()
            .values(
                id=run_id,
                target_type=target_type,
                target_id=target_id,
                depth="standard",
                profile_version="performance-2",
                config_json=canonical_json(configuration),
                config_hash=hash_config(configuration),
                status="succeeded",
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        connection.execute(
            metadata.tables["cohorts"]
            .insert()
            .values(
                id=cohort_id,
                name=f"{target_type}:{target_id}",
                population_spec_json=canonical_json(configuration),
                created_by_run_id=run_id,
            )
        )
        pairs = results["comparison"]["pairs"] if results["comparison"] else []
        match_ids = {identity: str(i) for i, pair in enumerate(pairs) for identity in pair}
        for row in rows:
            connection.execute(
                metadata.tables["cohort_members"]
                .insert()
                .values(
                    cohort_id=cohort_id,
                    post_id=row["post_id"],
                    role=row["role"],
                    match_set_id=match_ids.get(row["post_id"]),
                    input_json=canonical_json(row),
                )
            )
            connection.execute(
                metadata.tables["derived_metrics"]
                .insert()
                .values(
                    id=stable_id("derived-metric", run_id, row["post_id"]),
                    post_id=row["post_id"],
                    metric_key=spec.metric_key,
                    value=row["outcome"],
                    formula_version="aligned-as-of-2",
                    input_ids_json=canonical_json(row["snapshot_ids"]),
                    run_id=run_id,
                )
            )
        # Insert the analysis before its FKs, but defer final report serialization
        # until citations have been created below. All of this is one transaction.
        analyses = metadata.tables["statistical_analyses"]
        connection.execute(
            analyses.insert().values(
                id=analysis_id,
                method=spec.model,
                spec_json=canonical_json(configuration),
                outcome_key=spec.metric_key,
                status=results["regression"]["status"],
                result_json=canonical_json(report),
                run_id=run_id,
            )
        )
        for row in history:
            connection.execute(
                metadata.tables["analysis_references"]
                .insert()
                .values(
                    analysis_id=analysis_id, post_id=row["post_id"], input_json=canonical_json(row)
                )
            )
        feature_ids = sorted(
            {v["id"] for row in rows + history for v in row["feature_values"].values()}
        )
        if feature_ids:
            connection.execute(
                metadata.tables["analysis_feature_values"].insert(),
                [
                    {"analysis_id": analysis_id, "feature_value_id": identity}
                    for identity in feature_ids
                ],
            )
        term_ids = []
        for term in results["regression"]["terms"]:
            identity = stable_id("statistical-result", run_id, term["term"])
            connection.execute(
                metadata.tables["statistical_results"]
                .insert()
                .values(
                    id=identity,
                    analysis_id=analysis_id,
                    term=term["term"],
                    **{
                        key: term.get(key)
                        for key in (
                            "estimate",
                            "standard_error",
                            "ci_low",
                            "ci_high",
                            "p_value",
                            "adjusted_p_value",
                        )
                    },
                    sample_count=term["sample_count"],
                    cluster_count=term["cluster_count"],
                    diagnostics_json=canonical_json(results["regression"].get("diagnostics", {})),
                )
            )
            term_ids.append((identity, term["term"]))
        report["statistical_evidence"] = _citations(connection, report, analysis_id, term_ids)
        connection.execute(
            analyses.update()
            .where(analyses.c.id == analysis_id)
            .values(result_json=canonical_json(report))
        )
        connection.execute(
            metadata.tables["test_attempts"]
            .update()
            .where(metadata.tables["test_attempts"].c.id == attempt_id)
            .values(
                analysis_id=analysis_id,
                status="completed",
                result_json=canonical_json(
                    {
                        "regression": results["regression"]["status"],
                        "spec": spec.model_dump(mode="json"),
                        "validation": results["validation"]["status"],
                        "input_hash": configuration["input_hash"],
                    }
                ),
            )
        )
        for entry in batch:
            connection.execute(
                metadata.tables["account_media_runs"]
                .insert()
                .values(account_run_id=run_id, **entry)
            )
    return report


def _citations(
    connection: Connection,
    report: dict[str, Any],
    analysis_id: str,
    terms: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    now = utc_now()
    source_id, provenance_id = (
        stable_id("analysis-source", analysis_id),
        stable_id("analysis-provenance", analysis_id),
    )
    connection.execute(
        metadata.tables["source_records"]
        .insert()
        .values(
            id=source_id,
            source_kind="derived_analysis",
            source_uri=f"socialdna:analysis/{analysis_id}",
            permission_basis=(
                "locally authored; reuse conditional on all captured input permissions"
            ),
            terms_json=canonical_json({"input_authority": "transitive", "not_causal": True}),
            retrieved_at=now,
        )
    )
    connection.execute(
        metadata.tables["provenance_records"]
        .insert()
        .values(
            id=provenance_id,
            source_record_id=source_id,
            method="performance-2",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json(report["analysis_configuration"]),
            created_at=now,
        )
    )
    repository = EvidenceRepository(connection)
    subject = repository.save_entity(
        "statistical_analysis",
        analysis_id,
        {
            "analysis_id": analysis_id,
            "run_id": report["run_id"],
            "input_hash": report["analysis_configuration"]["input_hash"],
            "reference_hash": report["analysis_configuration"]["reference_hash"],
            "results_hash": hash_config(report["results"]),
        },
        provenance_id,
        available_at=now,
    )
    connection.execute(
        metadata.tables["statistical_entity_bindings"]
        .insert()
        .values(revision_id=subject.revision_id, analysis_id=analysis_id)
    )
    result = []
    targets = (
        [(identity, term, None) for identity, term in terms]
        + [(None, None, name) for name in ("regression", "validation", "creator_baselines")]
        + ([(None, None, "comparison")] if report["results"]["comparison"] else [])
    )
    for result_id, term, diagnostic in targets:
        locator = StatisticalLocator.model_validate(
            {
                "subject": subject,
                "analysis_id": analysis_id,
                "result_id": result_id,
                "term": term,
                "diagnostic": diagnostic,
            }
        )
        ref = repository.save_evidence(
            stable_id("statistical-evidence", analysis_id, result_id or diagnostic or ""),
            locator,
            provenance_id,
            run_id=report["run_id"],
            available_at=now,
        )
        connection.execute(
            metadata.tables["statistical_evidence_bindings"]
            .insert()
            .values(
                evidence_revision_id=ref.revision_id,
                analysis_id=analysis_id,
                result_id=result_id,
                diagnostic=diagnostic,
            )
        )
        result.append({"ref": ref.model_dump(), "term": term, "diagnostic": diagnostic})
    return result
