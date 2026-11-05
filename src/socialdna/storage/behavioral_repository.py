"""Canonical behavioral revisions and exercised typed projections."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.analytics.retention import metric_value
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.behavioral import (
    AttributionObservation,
    AudienceCohort,
    BehavioralMetricDefinition,
    MetricMeasurement,
    MetricSeries,
)
from socialdna.domain.evidence import BehavioralLocator, EntityRef, EvidenceRef
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

KINDS = {
    "behavioral_metric_definition": "behavioral_metric_definitions",
    "audience_cohort": "audience_cohorts",
    "metric_measurement": "metric_measurements",
    "metric_series": "metric_series",
    "metric_bin": "metric_bins",
    "attribution_observation": "attribution_observations",
    "signed_metric_change": "signed_metric_changes",
    "behavioral_analysis": "behavioral_analyses",
}


def put(connection: Connection, table: str, **values: Any) -> None:
    connection.execute(insert(metadata.tables[table]).values(**values).on_conflict_do_nothing())


def active(
    connection: Connection,
    ref: EntityRef,
    cutoff: str | None = None,
    *,
    _ancestors: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    from socialdna.application.evidence_service import assert_active_inputs

    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    if not row["source_id"]:
        raise ConfigurationError("Behavioral inputs require actual captured source authority")
    assert_active_inputs(connection, source_ids=(row["source_id"],))
    source = repo.get("source_records", row["source_id"])
    if not source["permission_basis"].strip():
        raise ConfigurationError("Behavioral source authority is absent")
    if source["source_kind"] == "behavioral_export" and not json.loads(source["terms_json"]).get(
        "analytics_permitted"
    ):
        raise ConfigurationError("Source does not permit analytics reuse")
    if cutoff and (row["available_at"] is None or row["available_at"] > cutoff):
        raise ConfigurationError(
            "Behavioral input availability is unknown or later than the cutoff"
        )
    payload = dict(json.loads(row["payload_json"]))
    if ref.kind in KINDS:
        if ref.revision_id in _ancestors or len(_ancestors) >= 32:
            raise StorageIntegrityError("Cyclic behavioral dependency chain")
        for child in payload["entity_inputs"]:
            active(
                connection,
                EntityRef.model_validate(child),
                cutoff,
                _ancestors=_ancestors | {ref.revision_id},
            )
    return payload


def save(
    connection: Connection,
    kind: str,
    identity_key: str,
    payload: dict[str, Any],
    provenance: str,
    *,
    entities: list[EntityRef],
    evidence: list[EvidenceRef] | None = None,
    **projection: Any,
) -> EntityRef:
    repo = EvidenceRepository(connection)
    identity = stable_id("behavioral", kind, identity_key)
    document = {
        **payload,
        "entity_inputs": [r.model_dump() for r in entities],
        "evidence_inputs": [r.model_dump() for r in (evidence or [])],
    }
    previous = repo.latest(kind, identity)
    prior = repo.entity(previous) if previous else None
    source = repo.get("provenance_records", provenance)["source_record_id"]
    ref = (
        previous
        if previous
        and prior
        and prior["content_hash"] == hash_config(document)
        and prior["source_id"] == source
        else repo.save_entity(kind, identity, document, provenance, available_at=utc_now())
    )
    put(connection, KINDS[kind], revision_id=ref.revision_id, **projection)
    for ordinal, (field, child) in enumerate(
        [
            *(("entity_revision_id", r.revision_id) for r in entities),
            *(("evidence_revision_id", r.revision_id) for r in (evidence or [])),
        ]
    ):
        put(
            connection,
            "behavioral_dependencies",
            parent_revision_id=ref.revision_id,
            ordinal=ordinal,
            **{field: child},
        )
    return ref


def cite(connection: Connection, ref: EntityRef, *, run_id: str | None = None) -> EvidenceRef:
    repo = EvidenceRepository(connection)
    row = repo.entity(ref)
    evidence = repo.save_evidence(
        stable_id("behavioral-evidence", ref.revision_id),
        BehavioralLocator(subject=ref),
        row["provenance_id"],
        available_at=row["available_at"],
        run_id=run_id,
    )
    put(
        connection,
        "behavioral_evidence_bindings",
        evidence_revision_id=evidence.revision_id,
        subject_revision_id=ref.revision_id,
    )
    return evidence


def evidence_ref(connection: Connection, ref: EntityRef) -> EvidenceRef:
    table = metadata.tables["evidence_revisions"]
    rows = list(
        connection.execute(
            select(table.c.evidence_id, table.c.id).where(
                table.c.subject_revision_id == ref.revision_id,
                table.c.locator_kind == "behavioral_record",
            )
        )
    )
    if len(rows) != 1:
        raise StorageIntegrityError("Behavioral observations require exactly one typed citation")
    return EvidenceRef(id=rows[0][0], revision_id=rows[0][1])


def read(connection: Connection, ref: EntityRef, cutoff: str | None = None) -> dict[str, Any]:
    from socialdna.application.evidence_service import EvidenceResolver

    data = active(connection, ref, cutoff)
    if ref.kind not in ("behavioral_metric_definition", "audience_cohort"):
        EvidenceResolver(connection).resolve(
            evidence_ref(connection, ref), purpose="new_claim", as_of=cutoff
        )
    row = EvidenceRepository(connection).entity(ref)
    source = EvidenceRepository(connection).get("source_records", row["source_id"])
    return {
        "ref": ref.model_dump(),
        "available_at": row["available_at"],
        "source": {k: source[k] for k in ("id", "source_uri", "permission_basis")},
        **data,
    }


def latest(connection: Connection, kind: str, cutoff: str, *, limit: int = 5000) -> list[EntityRef]:
    table = metadata.tables["entity_revisions"]
    selected: dict[str, EntityRef] = {}
    for row in connection.execute(
        select(table)
        .where(table.c.kind == kind, table.c.available_at <= cutoff)
        .order_by(table.c.revision_no)
    ).mappings():
        selected[row["entity_id"]] = EvidenceRepository.ref(dict(row))
        if len(selected) > limit:
            raise ConfigurationError("Behavioral selection exceeds 5000 record identities")
    return list(selected.values())


def persist_definition(
    connection: Connection, spec: BehavioralMetricDefinition, provenance: str
) -> dict[str, Any]:
    return _frozen(connection, "behavioral_metric_definition", spec, provenance, [])


def persist_cohort(connection: Connection, spec: AudienceCohort, provenance: str) -> dict[str, Any]:
    active(connection, spec.account)
    return _frozen(connection, "audience_cohort", spec, provenance, [spec.account])


def _frozen(
    connection: Connection,
    kind: str,
    spec: BehavioralMetricDefinition | AudienceCohort,
    provenance: str,
    entities: list[EntityRef],
) -> dict[str, Any]:
    repo = EvidenceRepository(connection)
    previous = repo.latest(kind, stable_id("behavioral", kind, spec.key))
    raw = spec.model_dump(mode="json")
    if previous and json.loads(repo.entity(previous)["payload_json"])["spec"] != raw:
        raise ConfigurationError("Behavioral definition/cohort changed; use a new versioned key")
    ref = save(
        connection, kind, spec.key, {"spec": raw}, provenance, entities=entities, key=spec.key
    )
    return {"ref": ref.model_dump(), "key": spec.key}


def persist_observation(
    connection: Connection, spec: MetricMeasurement | MetricSeries, provenance: str
) -> dict[str, Any]:
    if (
        spec.definition.kind != "behavioral_metric_definition"
        or spec.cohort.kind != "audience_cohort"
    ):
        raise ConfigurationError(
            "Observations need exact behavioral definition and cohort revisions"
        )
    definition = BehavioralMetricDefinition.model_validate(
        active(connection, spec.definition)["spec"]
    )
    cohort = AudienceCohort.model_validate(active(connection, spec.cohort)["spec"])
    subject = active(connection, spec.subject)
    if spec.subject.kind != definition.subject_type:
        raise ConfigurationError("Metric subject does not match its definition")
    account_id = spec.subject.id if spec.subject.kind == "account" else subject.get("account_id")
    if account_id != cohort.account.id:
        raise ConfigurationError("Metric cohort belongs to a different account")
    account = active(connection, cohort.account)
    if definition.platform != account["platform"]:
        raise ConfigurationError("Behavioral platform definition does not match the account")
    if spec.clock.collected_at > utc_now():
        raise ConfigurationError("Behavioral collection time cannot be in the future")
    if spec.subject.kind == "post" and (
        not subject["published_at"] or spec.clock.window_start < subject["published_at"]
    ):
        raise ConfigurationError("Post measurement window precedes actual publication")
    if (
        definition.measurement in ("period", "series")
        and spec.clock.window_start == spec.clock.window_end
    ):
        raise ConfigurationError("Period metrics require a nonempty reporting window")
    is_series = isinstance(spec, MetricSeries)
    if is_series != (definition.measurement == "series"):
        raise ConfigurationError("Series and scalar definitions are not interchangeable")
    kind = spec.record_type
    prior = EvidenceRepository(connection).latest(kind, stable_id("behavioral", kind, spec.key))
    if prior:
        original = json.loads(EvidenceRepository(connection).entity(prior)["payload_json"])["spec"]
        if any(
            original[k] != spec.model_dump(mode="json")[k]
            for k in ("subject", "definition", "cohort")
        ) or any(
            original["clock"][k] != getattr(spec.clock, k) for k in ("window_start", "window_end")
        ):
            raise ConfigurationError(
                "Correction cannot change observation ownership/definition/window; use a new key"
            )
    entities = [spec.subject, spec.definition, spec.cohort]
    extra: dict[str, Any] = {"cohort_known": cohort.known}
    results = []
    if is_series:
        assert isinstance(spec, MetricSeries)
        duration = None
        if spec.media:
            media = active(connection, spec.media)
            links = metadata.tables["post_media"]
            if not connection.scalar(
                select(links.c.post_id).where(
                    links.c.post_id == spec.subject.id, links.c.media_asset_id == spec.media.id
                )
            ):
                raise ConfigurationError("Series media does not belong to the measured post")
            duration = media["duration_ms"]
            if duration is None or duration <= 0:
                raise ConfigurationError("Series media mapping needs a known original duration")
            entities.append(spec.media)
        results = [
            metric_value(b.measurement, definition, spec.cohort, spec.clock) for b in spec.bins
        ]
        for item in spec.bins:
            if (
                spec.coordinate_kind == "media_ms"
                and duration is not None
                and max(v for v in (item.start, item.end, item.point) if v is not None) > duration
            ):
                raise ConfigurationError("Source bin exceeds the original media duration")
        extra.update(
            media_duration_ms=duration,
            post_age_window_seconds=[
                (
                    datetime.fromisoformat(t) - datetime.fromisoformat(subject["published_at"])
                ).total_seconds()
                for t in (spec.clock.window_start, spec.clock.window_end)
            ],
        )
        result = None
    else:
        assert isinstance(spec, MetricMeasurement)
        result = metric_value(spec.measurement, definition, spec.cohort, spec.clock)
    if isinstance(spec, AttributionObservation):
        if definition.meaning != "conversion" or definition.measurement != "period":
            raise ConfigurationError("Attribution requires a period conversion definition")
        for credit in spec.credits:
            post = active(connection, credit.post)
            if post["account_id"] != account_id:
                raise ConfigurationError("Attribution credit belongs to another account")
            if (
                not spec.lookback_start
                or not spec.lookback_start <= post["published_at"] <= spec.lookback_end
            ):
                raise ConfigurationError(
                    "Supplied post credit lies outside the attribution lookback"
                )
            entities.append(credit.post)
        extra["claim_scope"] = "source-reported attribution, not an identified causal effect"
    ref = save(
        connection,
        kind,
        spec.key,
        {"spec": spec.model_dump(mode="json"), "result": result, **extra},
        provenance,
        entities=entities,
        key=spec.key,
        subject_revision_id=spec.subject.revision_id,
        definition_revision_id=spec.definition.revision_id,
        cohort_revision_id=spec.cohort.revision_id,
        window_start=spec.clock.window_start,
        window_end=spec.clock.window_end,
        data_cutoff=spec.clock.data_cutoff,
        value=result["value"] if result else None,
        availability=result["availability"] if result else None,
    )
    bins = []
    if is_series:
        assert isinstance(spec, MetricSeries)
        for item, value in zip(spec.bins, results, strict=True):
            mapped = None
            if extra["media_duration_ms"] and spec.coordinate_kind != "provider_index":
                factor = (
                    extra["media_duration_ms"]
                    if spec.coordinate_kind == "normalized_progress"
                    else 1
                )
                mapped = {
                    k + "_ms": getattr(item, k) * factor if getattr(item, k) is not None else None
                    for k in ("start", "end", "point")
                }
            child = save(
                connection,
                "metric_bin",
                ref.revision_id + ":" + str(item.ordinal),
                {
                    "spec": item.model_dump(mode="json"),
                    "result": value,
                    "series": ref.model_dump(),
                    "media_mapping": mapped,
                    "precision": "source grid only; no interpolation",
                },
                provenance,
                entities=entities,
                series_revision_id=ref.revision_id,
                ordinal=item.ordinal,
                source_start=item.start,
                source_end=item.end,
                source_point=item.point,
                value=value["value"],
                availability=value["availability"],
            )
            bins.append(
                {"ref": child.model_dump(), "evidence": cite(connection, child).model_dump()}
            )
    return {
        "ref": ref.model_dump(),
        "key": spec.key,
        "evidence": cite(connection, ref).model_dump(),
        **({"bins": bins} if is_series else {}),
    }


def validate_projection(repo: EvidenceRepository, ref: EntityRef, payload: dict[str, Any]) -> None:
    row = repo.get(KINDS[ref.kind], ref.revision_id, "revision_id")
    spec = payload.get("spec", {})
    expected: dict[str, Any] = {}
    if ref.kind in ("behavioral_metric_definition", "audience_cohort"):
        expected = {"key": spec["key"]}
    elif ref.kind in ("metric_measurement", "metric_series", "attribution_observation"):
        result = payload["result"]
        expected = {
            "key": spec["key"],
            "subject_revision_id": spec["subject"]["revision_id"],
            "definition_revision_id": spec["definition"]["revision_id"],
            "cohort_revision_id": spec["cohort"]["revision_id"],
            "window_start": spec["clock"]["window_start"],
            "window_end": spec["clock"]["window_end"],
            "data_cutoff": spec["clock"]["data_cutoff"],
            "value": result["value"] if result else None,
            "availability": result["availability"] if result else None,
        }
        if ref.kind == "metric_series":
            bins = metadata.tables["metric_bins"]
            revisions = metadata.tables["entity_revisions"]
            children: list[str] = list(
                repo.connection.scalars(
                    select(revisions.c.payload_json)
                    .join(bins, bins.c.revision_id == revisions.c.id)
                    .where(bins.c.series_revision_id == ref.revision_id)
                    .order_by(bins.c.ordinal)
                )
            )
            actual = [json.loads(raw)["spec"] for raw in children]
            if actual != spec["bins"]:
                raise StorageIntegrityError("Series disagrees with its exact bin membership")
    elif ref.kind == "metric_bin":
        expected = {
            "series_revision_id": payload["series"]["revision_id"],
            "ordinal": spec["ordinal"],
            "source_start": spec["start"],
            "source_end": spec["end"],
            "source_point": spec["point"],
            "value": payload["result"]["value"],
            "availability": payload["result"]["availability"],
        }
        parent_ref = EntityRef.model_validate(payload["series"])
        revisions = metadata.tables["entity_revisions"]
        parent = repo.connection.execute(
            select(revisions.c.kind, revisions.c.entity_id).where(
                revisions.c.id == parent_ref.revision_id
            )
        ).first()
        if (
            parent is None
            or tuple(parent) != (parent_ref.kind, parent_ref.id)
            or parent_ref.kind != "metric_series"
        ):
            raise StorageIntegrityError("Bin has a wrong-kind or mismatched parent series")
    elif ref.kind == "signed_metric_change":
        expected = payload["projection"]
    elif ref.kind == "behavioral_analysis":
        expected = {"run_id": payload["report"]["run_id"], "fingerprint": payload["fingerprint"]}
    if any(row[k] != v for k, v in expected.items()):
        raise StorageIntegrityError("Behavioral document disagrees with its typed projection")
    table = metadata.tables["behavioral_dependencies"]
    actual_deps = list(
        repo.connection.execute(
            select(table.c.entity_revision_id, table.c.evidence_revision_id)
            .where(table.c.parent_revision_id == ref.revision_id)
            .order_by(table.c.ordinal)
        )
    )
    wanted = [
        *((r["revision_id"], None) for r in payload["entity_inputs"]),
        *((None, r["revision_id"]) for r in payload["evidence_inputs"]),
    ]
    if actual_deps != wanted:
        raise StorageIntegrityError("Behavioral dependency projection mismatch")
