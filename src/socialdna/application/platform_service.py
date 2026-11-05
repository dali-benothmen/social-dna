"""Reviewed source versions and source-qualified early/later distribution evidence."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from socialdna.application.bootstrap import Application, open_application
from socialdna.application.context_service import freeze_report, provenance, read_spec
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.platform_research import (
    DistributionObservation,
    PlatformCapabilities,
    PlatformDocument,
    PlatformExport,
    PlatformReportSpec,
    PlatformStatement,
)
from socialdna.storage import behavioral_repository as behavioral
from socialdna.storage import context_repository as context
from socialdna.storage.evidence_repository import EvidenceRepository


def import_document(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = read_spec(path, PlatformExport)
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "limitations": [
                "Schema only; review authenticity and source metric availability "
                "are not verified by a dry run."
            ],
        }
    with open_application(settings) as app:
        return import_into_application(app, spec)


def active_document(connection: Connection, ref: EntityRef) -> None:
    repo = EvidenceRepository(connection)
    data = json.loads(repo.entity(ref)["payload_json"])["spec"]
    latest = repo.latest("platform_document", ref.id)
    assert latest is not None
    current = json.loads(repo.entity(latest)["payload_json"])["spec"]
    if (
        data["review_status"] != "reviewed"
        or current["review_status"] != "reviewed"
        or (latest != ref and current["revision_reason"] in ("correction", "withdrawal"))
    ):
        raise ConfigurationError("Official source is unreviewed, corrected or withdrawn")


def observation_data(
    connection: Connection, spec: DistributionObservation, cutoff: str | None = None
) -> dict[str, Any]:
    if (
        spec.capabilities.kind != "platform_capabilities"
        or spec.early.kind != "metric_measurement"
        or spec.later.kind != "metric_measurement"
    ):
        raise ConfigurationError(
            "Distribution requires actual capabilities and scalar measurement revisions"
        )
    caps = context.read(connection, spec.capabilities, cutoff)
    manifest = caps["spec"]
    if caps["account"] != spec.account.model_dump() or not manifest["analytics_permitted"]:
        raise ConfigurationError("Distribution account or analytics permission mismatch")
    early, later = [behavioral.read(connection, ref, cutoff) for ref in (spec.early, spec.later)]
    definitions = {}
    for row in (early, later):
        if row["spec"]["subject"] != spec.post.model_dump():
            raise ConfigurationError("Distribution metrics must measure the exact declared post")
        if row["result"]["availability"] != "available":
            raise ConfigurationError(
                "Unavailable or suppressed metrics cannot support a distribution comparison"
            )
        clock = row["spec"]["clock"]
        if (
            clock["data_cutoff"] != clock["window_end"]
            or clock["window_start"] >= clock["window_end"]
        ):
            raise ConfigurationError(
                "Distribution windows require known complete effective cutoffs"
            )
        definition = behavioral.read(
            connection, EntityRef.model_validate(row["spec"]["definition"]), cutoff
        )["spec"]
        definitions[row["spec"]["definition"]["revision_id"]] = definition
        if (
            definition["platform"] != manifest["scope"]["platform"]
            or definition["measurement"] != "period"
        ):
            raise ConfigurationError(
                "Use platform-specific period measurements, not cumulative overlapping counters"
            )
    if early["spec"]["cohort"] != later["spec"]["cohort"]:
        raise ConfigurationError("Early and later observations need the exact same source cohort")
    cohort = behavioral.read(connection, EntityRef.model_validate(early["spec"]["cohort"]), cutoff)[
        "spec"
    ]
    if not cohort["known"] or cohort["dimensions"].get("traffic") != spec.raw_surface_code:
        raise ConfigurationError("Raw traffic code must come from a known source cohort")
    metric_roles = {}
    for field, row in (("early", early), ("later", later)):
        available = [
            m
            for m in manifest["metrics"]
            if m["definition"] == row["spec"]["definition"] and m["availability"] == "available"
        ]
        if len(available) != 1:
            raise ConfigurationError("Source capability manifest does not provide this metric")
        metric_roles[field] = available[0]["role"]
    if metric_roles["early"] not in (
        "shares",
        "saves",
        "retention",
        "completion",
        "watch_time",
    ) or metric_roles["later"] not in ("views", "impressions", "reach"):
        raise ConfigurationError("Declare an early response and a later distribution measure")
    lag = (
        datetime.fromisoformat(later["spec"]["clock"]["window_start"])
        - datetime.fromisoformat(early["spec"]["clock"]["window_end"])
    ).total_seconds()
    if lag < 0:
        raise ConfigurationError(
            "Overlapping response/distribution windows introduce feedback leakage"
        )
    mapping = next(
        (m for m in manifest["mappings"] if m["raw_code"] == spec.raw_surface_code), None
    )
    if mapping is None:
        raise ConfigurationError("No reviewed mapping for the raw source surface code")
    return {
        "scope": manifest["scope"],
        "mapping": mapping,
        "lag_seconds": lag,
        "early": {
            "ref": spec.early.model_dump(),
            "value": early["result"]["value"],
            "role": metric_roles["early"],
            "definition": early["spec"]["definition"],
            "unit": definitions[early["spec"]["definition"]["revision_id"]]["unit"],
            "population_basis": definitions[early["spec"]["definition"]["revision_id"]][
                "population_basis"
            ],
            "replay_policy": definitions[early["spec"]["definition"]["revision_id"]][
                "replay_policy"
            ],
            "clock": early["spec"]["clock"],
        },
        "later": {
            "ref": spec.later.model_dump(),
            "value": later["result"]["value"],
            "role": metric_roles["later"],
            "definition": later["spec"]["definition"],
            "unit": definitions[later["spec"]["definition"]["revision_id"]]["unit"],
            "population_basis": definitions[later["spec"]["definition"]["revision_id"]][
                "population_basis"
            ],
            "replay_policy": definitions[later["spec"]["definition"]["revision_id"]][
                "replay_policy"
            ],
            "clock": later["spec"]["clock"],
        },
        "cohort": early["spec"]["cohort"],
        "early_known_before_later": early["available_at"] <= later["spec"]["clock"]["window_start"],
        "source_lag_seconds": manifest["source_lag_seconds"],
    }


def import_into_application(app: Application, spec: PlatformExport) -> dict[str, Any]:
    raw = spec.model_dump(mode="json")
    with app.database.transaction() as connection:
        source, producer = provenance(connection, raw, spec.source_uri, spec.permission_basis)
        repo = EvidenceRepository(connection)
        records = []
        for record in spec.records:
            inputs: tuple[EntityRef, ...] = ()
            evidence: tuple[EvidenceRef, ...] = ()
            result = None
            post = record.post if isinstance(record, DistributionObservation) else None
            if isinstance(record, PlatformDocument):
                if hashlib.sha256(record.source_text.encode()).hexdigest() != record.sha256:
                    raise ConfigurationError("Official captured-text checksum mismatch")
                account = json.loads(repo.entity(record.account)["payload_json"])
                if account["platform"] != record.platform:
                    raise ConfigurationError(
                        "Official document differs from the research account platform"
                    )
            elif isinstance(record, PlatformStatement):
                if record.document.kind != "platform_document":
                    raise ConfigurationError(
                        "Official statements require an exact platform document"
                    )
                active_document(connection, record.document)
                document = context.read(connection, record.document)["spec"]
                if (
                    document["account"] != record.account.model_dump()
                    or record.surface not in document["surfaces"]
                    or not (
                        0 <= record.start_char < record.end_char <= len(document["source_text"])
                    )
                    or document["source_text"][record.start_char : record.end_char] != record.quote
                ):
                    raise ConfigurationError(
                        "Official statement source, surface or Unicode excerpt mismatch"
                    )
                inputs = (record.document,)
                evidence = (
                    context.cite(
                        connection,
                        record.document,
                        field="source_text",
                        start=record.start_char,
                        end=record.end_char,
                    ),
                )
            elif isinstance(record, PlatformCapabilities):
                account = json.loads(repo.entity(record.account)["payload_json"])
                if account["platform"] != record.scope.platform:
                    raise ConfigurationError("Capability platform differs from account")
                for metric in record.metrics:
                    if (
                        metric.definition.kind != "behavioral_metric_definition"
                        or behavioral.read(connection, metric.definition)["spec"]["platform"]
                        != record.scope.platform
                    ):
                        raise ConfigurationError(
                            "Capability definition needs the exact platform namespace"
                        )
                    definition = behavioral.read(connection, metric.definition)["spec"]
                    expected = (
                        metric.role
                        if metric.role in ("retention", "completion", "watch_time")
                        else "other"
                    )
                    if definition["meaning"] != expected or (
                        expected == "other" and definition["semantics"] != "count"
                    ):
                        raise ConfigurationError(
                            "Reviewed metric role conflicts with its actual source definition"
                        )
                    if metric.role == "reach" and definition["population_basis"] not in (
                        "unique_viewers",
                        "accounts",
                    ):
                        raise ConfigurationError(
                            "Reach requires an explicitly unique source population"
                        )
                inputs = tuple(m.definition for m in record.metrics)
            else:
                result = observation_data(connection, record)
                inputs = (record.capabilities, record.early, record.later)
                evidence = (
                    behavioral.evidence_ref(connection, record.early),
                    behavioral.evidence_ref(connection, record.later),
                )
                if (
                    max(result[part]["clock"]["collected_at"] for part in ("early", "later"))
                    > record.clock.captured_at
                ):
                    raise ConfigurationError("Observation capture predates source collection")
            ref = context.save(
                connection,
                record.record_type,
                spec.dataset_id + ":" + record.key,
                record.model_dump(mode="json"),
                producer,
                account=record.account,
                post=post,
                entities=inputs,
                evidence=evidence,
                result=result,
            )
            citation = context.cite(connection, ref)
            records.append({"ref": ref.model_dump(), "evidence": citation.model_dump()})
        artifact = app.artifacts.put_bytes(
            connection,
            canonical_json(raw).encode(),
            kind="platform-source",
            mime_type="application/json",
        )
        app.artifacts.add_reference(
            connection, artifact, owner_type="context_source", owner_id=source, role="raw"
        )
        from socialdna.storage.schema import metadata

        connection.execute(
            metadata.tables["source_records"]
            .update()
            .where(metadata.tables["source_records"].c.id == source)
            .values(raw_artifact_id=artifact)
        )
        return {"valid": True, "written": True, "source_id": source, "records": records}


def report(app: Application, spec: PlatformReportSpec) -> dict[str, Any]:
    if spec.as_of > utc_now():
        raise ConfigurationError("Platform cutoff cannot be in the future")
    with app.database.transaction() as connection:
        official, observations, refusals, citations, inputs = [], [], [], [], []
        account = json.loads(EvidenceRepository(connection).entity(spec.account)["payload_json"])
        if spec.account.kind != "account" or account["platform"] != spec.scope.platform:
            raise ConfigurationError("Research account and platform scope disagree")
        for ref in spec.statements:
            if ref.kind != "platform_statement":
                raise ConfigurationError("Official lane accepts only reviewed platform statements")
            data = context.read(connection, ref, spec.as_of)
            statement = data["spec"]
            doc = context.read(
                connection, EntityRef.model_validate(statement["document"]), spec.as_of
            )["spec"]
            if (
                data["account"] != spec.account.model_dump()
                or doc["platform"] != spec.scope.platform
                or statement["surface"] != spec.scope.surface
            ):
                raise ConfigurationError("Official statement account/platform/surface mismatch")
            official.append(
                {
                    "ref": ref.model_dump(),
                    "quote": statement["quote"],
                    "interpretation": statement["interpretation"],
                    "limitation": statement["limitation"],
                    "document": statement["document"],
                    "url": doc["url"],
                    "clock": doc["clock"],
                    "published_at": doc["published_at"],
                    "historical_applicability": "not_backdated_from_retrieval",
                    "claim_level": "official_guidance",
                }
            )
            inputs.append(ref)
            citations.append(context.cite(connection, ref))
        seen = set()
        for ref in spec.observations:
            if ref.kind != "distribution_observation":
                raise ConfigurationError("Observed lane requires distribution observations")
            data = context.read(connection, ref, spec.as_of)
            observation = DistributionObservation.model_validate(data["spec"])
            row = observation_data(connection, observation, spec.as_of)
            if (
                data["account"] != spec.account.model_dump()
                or row["scope"] != spec.scope.model_dump()
            ):
                raise ConfigurationError(
                    "Observations cannot pool different accounts/platforms/surfaces/contexts"
                )
            if observation.post.id in seen:
                raise ConfigurationError(
                    "One post cannot be counted as independent repeated observations"
                )
            seen.add(observation.post.id)
            inputs.append(ref)
            citations.append(context.cite(connection, ref))
            if (
                row["mapping"]["surface"] != spec.scope.surface
                or row["mapping"]["traffic"] != spec.traffic
                or row["lag_seconds"] < spec.minimum_lag_seconds
            ):
                refusals.append(
                    {
                        "ref": ref.model_dump(),
                        "reason": "unknown/incompatible surface, traffic or required lag",
                    }
                )
            else:
                observations.append(
                    {
                        "ref": ref.model_dump(),
                        "post": observation.post.model_dump(),
                        **row,
                        "claim_level": "local_observation",
                    }
                )
        pairs = {
            (r["early"]["definition"]["revision_id"], r["later"]["definition"]["revision_id"])
            for r in observations
        }
        if len(pairs) > 1:
            raise ConfigurationError(
                "Distribution comparisons require identical source metric definitions"
            )
        result = {
            "kind": "platform_research",
            "scope": spec.scope.model_dump(),
            "traffic": spec.traffic,
            "official_guidance": official,
            "local_observations": observations,
            "observed_pair_count": len(observations),
            "refusals": refusals,
            "claim_level": "descriptive_observational",
            "status": "descriptive_pairs" if observations else "insufficient_distribution_access",
            "limitations": [
                "Paired windows are observations, not recovered ranking weights, "
                "causal effects or guaranteed reach.",
                "Official documentation is not an empirical effect or executed creator experiment. "
                "Hidden eligibility and satisfaction signals remain unobserved.",
                "Retrospectively imported early windows are not prospective predictions; "
                "event-window order and actual knowledge availability are reported separately.",
            ],
        }
        return freeze_report(
            app,
            connection,
            spec.account,
            spec.model_dump(mode="json"),
            result,
            tuple(inputs),
            tuple(citations),
            uri="urn:socialdna:platform-report",
        )
