"""Bounded versioned behavioral imports, source-grid analysis and frozen reports."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from socialdna import __version__
from socialdna.analytics.retention import compare_series
from socialdna.application.bootstrap import Application, open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.behavioral import (
    AudienceCohort,
    BehavioralExport,
    BehavioralMetricDefinition,
    MetricMeasurement,
    MetricSeries,
)
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.ingestion.tabular import parse_behavioral, timestamp
from socialdna.storage import behavioral_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def cutoff(value: str | None) -> str:
    try:
        result = timestamp(value) if value else utc_now()
    except ValueError as exc:
        raise ConfigurationError("Invalid behavioral knowledge cutoff") from exc
    if result > utc_now():
        raise ConfigurationError("Behavioral knowledge cutoff cannot be in the future")
    return result


def import_document(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = parse_behavioral(path)
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "dry_run": True,
            "limitations": [
                "Schema-only dry run; actual references and semantic compatibility "
                "are checked on import."
            ],
        }
    with open_application(settings) as app:
        return import_into_application(app, spec)


def import_into_application(app: Application, spec: BehavioralExport) -> dict[str, Any]:
    digest = hash_config(spec.model_dump(mode="json"))
    source = stable_id("behavioral-source", digest)
    provenance = stable_id("behavioral-provenance", digest)
    with app.database.transaction() as connection:
        from socialdna.application.evidence_service import assert_active_inputs

        assert_active_inputs(connection, source_ids=(source,))
        repository.put(
            connection,
            "source_records",
            id=source,
            source_kind="behavioral_export",
            source_uri=spec.source.source_uri,
            permission_basis=spec.source.permission_basis,
            terms_json=canonical_json(spec.source.model_dump(mode="json")),
            retrieved_at=utc_now(),
            content_hash=digest,
        )
        repository.put(
            connection,
            "provenance_records",
            id=provenance,
            source_record_id=source,
            method="behavioral-import-1",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json({"schema_version": "2.0"}),
            created_at=utc_now(),
        )
        records = []
        # Resolve explicit existing references; do not invent intra-file revision IDs.
        for record in spec.records:
            if isinstance(record, BehavioralMetricDefinition):
                item = repository.persist_definition(connection, record, provenance)
            elif isinstance(record, AudienceCohort):
                item = repository.persist_cohort(connection, record, provenance)
            elif isinstance(record, (MetricMeasurement, MetricSeries)):
                item = repository.persist_observation(connection, record, provenance)
            else:
                raise ConfigurationError("Unsupported behavioral record")
            records.append(item)
        # No source blobs are retained until all records pass actual validation.
        artifact = app.artifacts.put_bytes(
            connection,
            canonical_json(spec.model_dump(mode="json")).encode(),
            kind="behavioral-source",
            mime_type="application/json",
        )
        app.artifacts.add_reference(
            connection, artifact, owner_type="behavioral_source", owner_id=source, role="raw"
        )
        connection.execute(
            metadata.tables["source_records"]
            .update()
            .where(metadata.tables["source_records"].c.id == source)
            .values(raw_artifact_id=artifact)
        )
        return {
            "valid": True,
            "written": True,
            "source_id": source,
            "artifact_id": artifact,
            "records": records,
            "limitations": list(spec.source.limitations),
        }


def select_ref(
    connection: Any, identity: str, knowledge: str, revision: str | None = None
) -> EntityRef:
    table = metadata.tables["entity_revisions"]
    query = select(table).where(table.c.entity_id == identity, table.c.available_at <= knowledge)
    if revision:
        query = query.where(table.c.id == revision)
    row = connection.execute(query.order_by(table.c.revision_no.desc()).limit(1)).mappings().first()
    if not row or row["kind"] not in repository.KINDS:
        raise ConfigurationError("Unknown behavioral identity/revision at the requested cutoff")
    return EvidenceRepository.ref(dict(row))


def series_data(connection: Any, ref: EntityRef, knowledge: str) -> dict[str, Any]:
    if ref.kind != "metric_series":
        raise ConfigurationError("Retention analysis requires an actual metric series")
    data = repository.read(connection, ref, knowledge)
    table = metadata.tables["metric_bins"]
    bins = []
    repo = EvidenceRepository(connection)
    # The whole-series resolver has already checked each bin's current eligibility.
    for revision in connection.scalars(
        select(table.c.revision_id)
        .where(table.c.series_revision_id == ref.revision_id)
        .order_by(table.c.ordinal)
    ):
        child = repo.ref(repo.get("entity_revisions", revision))
        bins.append(
            {
                "ref": child.model_dump(),
                "evidence": repository.evidence_ref(connection, child).model_dump(),
                **json.loads(repo.entity(child)["payload_json"]),
            }
        )
    states = [b["result"]["availability"] for b in bins]
    return {
        **data,
        "evidence": repository.evidence_ref(connection, ref).model_dump(),
        "bins": bins,
        "coverage": {
            "supplied_bins": len(bins),
            "expected_bins": data["spec"]["expected_bins"],
            "available_bins": states.count("available"),
            "missing_or_suppressed_bins": len(bins) - states.count("available"),
            "absent_grid_rows": data["spec"]["expected_bins"] - len(bins)
            if data["spec"]["expected_bins"] is not None
            else None,
        },
    }


def creative_context(connection: Any, media_id: str, knowledge: str) -> dict[str, Any]:
    from socialdna.application.creative_service import assert_bundle_active
    from socialdna.storage.creative_repository import load_annotations

    bundle = load_annotations(connection, media_id, cutoff=knowledge)
    try:
        assert_bundle_active(connection, bundle, cutoff=knowledge)
    except ConfigurationError as exc:
        return {
            "eligible": False,
            "ref": bundle.get("ref"),
            "events": [],
            "limitations": [str(exc)],
        }
    return {
        "eligible": True,
        "ref": bundle.get("ref"),
        "events": bundle["events"],
        "reason": bundle.get("reason"),
        "limitations": ["Temporal proximity is not evidence that an event caused an exit."],
    }


def show(
    app: Application, identity: str, *, revision: str | None = None, as_of: str | None = None
) -> dict[str, Any]:
    knowledge = cutoff(as_of)
    with app.database.transaction() as connection:
        ref = select_ref(connection, identity, knowledge, revision)
        try:
            data = (
                series_data(connection, ref, knowledge)
                if ref.kind == "metric_series"
                else repository.read(connection, ref, knowledge)
            )
            return {**data, "eligible": True}
        except ConfigurationError as exc:
            return {"ref": ref.model_dump(), "eligible": False, "limitations": [str(exc)]}


def subject(
    app: Application, kind: str, identity: str, *, as_of: str | None = None
) -> dict[str, Any]:
    """Discover a real captured reference for import authoring, without database access."""
    if kind not in ("account", "post", "media"):
        raise ConfigurationError("Behavioral subjects are captured accounts, posts or media")
    knowledge = cutoff(as_of)
    with app.database.transaction() as connection:
        table = metadata.tables["entity_revisions"]
        row = (
            connection.execute(
                select(table)
                .where(
                    table.c.kind == kind,
                    table.c.entity_id == identity,
                    table.c.available_at <= knowledge,
                )
                .order_by(table.c.revision_no.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ConfigurationError("No captured subject revision is known by this cutoff")
        ref = EvidenceRepository.ref(dict(row))
        data = repository.active(connection, ref, knowledge)
        return {"ref": ref.model_dump(), "available_at": row["available_at"], "record": data}


def persist_analysis(
    connection: Any,
    target: EntityRef,
    report: dict[str, Any],
    entities: list[EntityRef],
    evidence: list[EvidenceRef],
    selection: dict[str, Any],
) -> dict[str, Any]:
    # Freeze both observed inputs and the actual selection/cutoff policy, including
    # unavailable branches. A changed data universe creates a new fingerprint.
    inputs = {
        "method": "behavioral-1",
        "selection": selection,
        "entities": [r.model_dump() for r in entities],
        "evidence": [r.model_dump() for r in evidence],
    }
    fingerprint = hash_config(inputs)
    table = metadata.tables["behavioral_analyses"]
    existing = connection.scalar(
        select(table.c.revision_id).where(table.c.fingerprint == fingerprint)
    )
    if existing:
        ref = EvidenceRepository(connection).ref(
            EvidenceRepository(connection).get("entity_revisions", existing)
        )
        loaded = repository.read(connection, ref)
        return {
            **loaded["report"],
            "ref": ref.model_dump(),
            "evidence": repository.evidence_ref(connection, ref).model_dump(),
            "cached": True,
        }
    source = EvidenceRepository(connection).entity(target)["source_id"]
    provenance = stable_id("behavioral-analysis-provenance", fingerprint)
    repository.put(
        connection,
        "provenance_records",
        id=provenance,
        source_record_id=source,
        method="behavioral-analysis-1",
        tool_name="socialdna",
        tool_version=__version__,
        config_json=canonical_json(inputs),
        created_at=utc_now(),
    )
    run = new_id()
    connection.execute(
        metadata.tables["analysis_runs"]
        .insert()
        .values(
            id=run,
            target_type="behavioral",
            target_id=target.id,
            depth="quick",
            profile_version="behavioral-1",
            config_hash=fingerprint,
            config_json=canonical_json(inputs),
            created_at=utc_now(),
            status="succeeded",
            started_at=utc_now(),
            finished_at=utc_now(),
        )
    )
    frozen = {
        "schema_version": "1.0",
        "report_type": "behavioral",
        "run_id": run,
        "target": target.model_dump(),
        "selection_manifest": inputs,
        "engine_version": __version__,
        **report,
    }
    ref = repository.save(
        connection,
        "behavioral_analysis",
        fingerprint,
        {"report": frozen, "fingerprint": fingerprint},
        provenance,
        entities=entities,
        evidence=evidence,
        run_id=run,
        fingerprint=fingerprint,
    )
    citation = repository.cite(connection, ref, run_id=run)
    return {**frozen, "ref": ref.model_dump(), "evidence": citation.model_dump(), "cached": False}


def load_analysis(app: Application, run: str) -> dict[str, Any]:
    with app.database.transaction() as connection:
        table = metadata.tables["behavioral_analyses"]
        revision = connection.scalar(select(table.c.revision_id).where(table.c.run_id == run))
        if not revision:
            raise ConfigurationError("Unknown behavioral analysis run")
        ref = EvidenceRepository(connection).ref(
            EvidenceRepository(connection).get("entity_revisions", revision)
        )
        data = repository.read(connection, ref)
        return {
            **data["report"],
            "ref": ref.model_dump(),
            "evidence": repository.evidence_ref(connection, ref).model_dump(),
        }


def analyze_retention(
    app: Application,
    *,
    series_id: str | None = None,
    post_id: str | None = None,
    compare_id: str | None = None,
    as_of: str | None = None,
    revision: str | None = None,
) -> dict[str, Any]:
    if bool(series_id) == bool(post_id):
        raise ConfigurationError("Select exactly one series ID or post ID")
    if revision and not series_id:
        raise ConfigurationError("An exact revision requires an explicit series ID")
    knowledge = cutoff(as_of)
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        if post_id:
            captured = metadata.tables["entity_revisions"]
            post_revision = connection.scalar(
                select(captured.c.id)
                .where(
                    captured.c.kind == "post",
                    captured.c.entity_id == post_id,
                    captured.c.available_at <= knowledge,
                )
                .order_by(captured.c.revision_no.desc())
                .limit(1)
            )
            if post_revision is None:
                raise ConfigurationError("No actual post revision is known at this cutoff")
            post = repo.ref(repo.get("entity_revisions", post_revision))
            repository.active(connection, post, knowledge)
            candidates = [
                r
                for r in repository.latest(connection, "metric_series", knowledge)
                if json.loads(repo.entity(r)["payload_json"])["spec"]["subject"]["id"] == post_id
            ]
            if len(candidates) > 1:
                raise ConfigurationError(
                    "Multiple series exist for the post; select an explicit series"
                )
            if not candidates:
                return persist_analysis(
                    connection,
                    post,
                    {
                        "analysis_kind": "retention",
                        "status": "partial",
                        "availability": "not_supplied",
                        "series": None,
                        "comparison": None,
                        "limitations": [
                            "No authorized retention series was supplied. Public scalar views "
                            "are not an early-retention proxy."
                        ],
                    },
                    [post],
                    [],
                    {"post": post_id, "requested_as_of": as_of},
                )
            ref = candidates[0]
        else:
            assert series_id
            ref = select_ref(connection, series_id, knowledge, revision)
        data = series_data(connection, ref, knowledge)
        definition = repository.read(
            connection, EntityRef.model_validate(data["spec"]["definition"]), knowledge
        )
        if definition["spec"]["meaning"] not in ("retention", "completion", "watch_time"):
            raise ConfigurationError(
                "This source series does not define retention, completion or watch time"
            )
        entities, evidence = [ref], [EvidenceRef.model_validate(data["evidence"])]
        context = None
        if data["spec"]["media"]:
            context = creative_context(connection, data["spec"]["media"]["id"], knowledge)
            if context["eligible"]:
                if context["ref"]:
                    entities.append(EntityRef.model_validate(context["ref"]))
                for event in context["events"]:
                    entities.append(EntityRef.model_validate(event["ref"]))
                    evidence.append(EvidenceRef.model_validate(event["evidence"]))
        comparison, other = None, None
        if compare_id:
            second = select_ref(connection, compare_id, knowledge)
            if second.id == ref.id:
                raise ConfigurationError("A series is not independent confirmation of itself")
            other = series_data(connection, second, knowledge)
            comparison = compare_series(data, other)
            entities.append(second)
            evidence.append(EvidenceRef.model_validate(other["evidence"]))
        return persist_analysis(
            connection,
            ref,
            {
                "analysis_kind": "retention",
                "status": "success"
                if data["coverage"]["missing_or_suppressed_bins"] == 0
                and data["spec"]["completeness"] == "complete_for_declared_grid"
                and (comparison is None or comparison["status"] == "available")
                else "partial",
                "availability": "available"
                if data["coverage"]["available_bins"]
                else "unavailable",
                "knowledge_cutoff": knowledge,
                "definition": definition,
                "series": data,
                "comparison_series": other,
                "comparison": comparison,
                "creative_context": context,
                "limitations": [
                    "Source-grid aggregate observations are not independent viewers. "
                    "No confidence interval, survival model, interpolation or causal event "
                    "effect was fitted.",
                    "Unknown denominators permit descriptive source values, "
                    "not binomial precision.",
                ],
            },
            entities,
            evidence,
            {
                "series": ref.model_dump(),
                "compare": other["ref"] if other else None,
                "as_of": as_of,
            },
        )


def media_overlay(app: Application, media_id: str) -> dict[str, Any]:
    knowledge = cutoff(None)
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        curves, withheld = [], []
        for ref in repository.latest(connection, "metric_series", knowledge, limit=200):
            raw = json.loads(repo.entity(ref)["payload_json"])
            media = raw["spec"]["media"]
            if not media or media["id"] != media_id:
                continue
            try:
                curves.append(series_data(connection, ref, knowledge))
            except ConfigurationError:
                withheld.append(ref.model_dump())
        context = creative_context(connection, media_id, knowledge)
        return {
            "series": curves,
            "creative_context": context,
            "withheld_series": withheld,
            "limitations": [
                "Shared-media context only. Coarse bin boundaries retain their source "
                "resolution; proximity to an event does not establish an exit or causal effect."
            ],
        }
