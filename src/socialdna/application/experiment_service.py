"""Explicit authorized registration → source outcomes → fixed analysis → assessment.

No execution, uploads, publishing, recruiting or spend occurs here.
"""

import importlib.metadata
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select

from socialdna.analytics import experiments as engine
from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.ingestion.tabular import timestamp
from socialdna.memory.documents import current_revision, entity_active
from socialdna.research.experiments import ExperimentResults, ExperimentSpec
from socialdna.storage import behavioral_repository as behavior
from socialdna.storage import context_repository as context
from socialdna.storage import experiment_repository as repository
from socialdna.storage import research_repository as research
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def _versions() -> dict[str, str]:
    return {k: importlib.metadata.version(k) for k in ("numpy", "scipy", "statsmodels")}


def _account(connection: Any, ref: EntityRef) -> dict[str, Any]:
    return dict(json.loads(entity_active(connection, ref)["payload_json"]))


def _response(connection: Any, ref: EntityRef) -> dict[str, Any]:
    response: dict[str, Any] = {
        "ref": ref.model_dump(),
        "evidence": research.cite(connection, ref).model_dump(),
        "content": json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]),
    }
    if ref.kind == "experiment_analysis":
        response["assessment"] = None
        table = metadata.tables["experiment_assessments"]
        identity = connection.scalar(
            select(table.c.revision_id).where(table.c.analysis_revision_id == ref.revision_id)
        )
        if identity:
            repo = EvidenceRepository(connection)
            response["assessment"] = _response(
                connection, repo.ref(repo.get("entity_revisions", identity))
            )
    return response


def _archive(app: Application, connection: Any, ref: EntityRef) -> None:
    row = EvidenceRepository(connection).entity(ref)
    artifact = app.artifacts.put_bytes(
        connection,
        row["payload_json"].encode(),
        kind="experiment-record",
        mime_type="application/json",
    )
    app.artifacts.add_reference(
        connection, artifact, owner_type="experiment", owner_id=ref.revision_id, role="frozen"
    )


def register(app: Application, spec: ExperimentSpec) -> dict[str, Any]:
    now = utc_now()
    raw = spec.model_dump(mode="json")
    identity = stable_id("research", "experiment_registration", spec.key)
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        previous = repo.latest("experiment_registration", identity)
        if previous:
            saved = repository.content(connection, previous)
            if saved["spec"] == raw:
                return _response(connection, previous)
            prior = ExperimentSpec.model_validate(saved["spec"])
            results = metadata.tables["experiment_results"]
            if (
                spec.predecessor != previous
                or spec.version != prior.version + 1
                or min(u.starts_at for u in prior.units) <= now
                or connection.scalar(
                    select(results.c.revision_id).where(
                        results.c.registration_revision_id == previous.revision_id
                    )
                )
            ):
                raise ConfigurationError(
                    "Amendments need a predecessor/next version, before execution or results"
                )
        elif spec.version != 1 or spec.predecessor:
            raise ConfigurationError("First registration must be version one without a predecessor")
        if spec.assignment_method == "engine_block_randomized" and any(
            u.starts_at <= now for u in spec.units
        ):
            raise ConfigurationError(
                "Engine randomization must precede all exposure; no backdated preregistration"
            )
        accounts = {u.account.revision_id: _account(connection, u.account) for u in spec.units}
        for unit in spec.units:
            account = accounts[unit.account.revision_id]
            if (
                account["platform"] != spec.scope.platform
                or account.get("niche") not in spec.scope.niches
            ):
                raise ConfigurationError(
                    "Assignment account is outside the declared platform/niche source frame"
                )
            if not spec.scope.period_start <= unit.starts_at < spec.scope.period_end:
                raise ConfigurationError("Unit exposure is outside the declared experiment period")
        definitions = []
        for outcome in spec.outcomes:
            definition = behavior.read(connection, outcome.definition)["spec"]
            expected = "post" if spec.assignment_unit in ("post", "impression") else "account"
            if (
                definition["subject_type"] != expected
                or definition["platform"] != spec.scope.platform
                or definition["measurement"] != "period"
                or definition["meaning"] == "followers"
                or definition["population_basis"] == "unknown"
            ):
                raise ConfigurationError(
                    "Use actual platform/subject period metrics, not stocks or unknown populations"
                )
            if spec.domain == "profile":
                binding = (
                    connection.execute(
                        select(metadata.tables["funnel_event_bindings"]).where(
                            metadata.tables["funnel_event_bindings"].c.definition_revision_id
                            == outcome.definition.revision_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if not binding or binding["signal"] not in ("follows", "app_installs", "purchases"):
                    raise ConfigurationError(
                        "Profile outcomes need C1 source-bound follow/install/purchase definitions"
                    )
            definitions.append(outcome.definition)
            if outcome.operationalization:
                entity_active(connection, outcome.operationalization)
        for ref in spec.context:
            entity_active(connection, ref)
        for citation in spec.origin:
            EvidenceResolver(connection).resolve(citation, purpose="new_claim")
        if spec.prior_assessment:
            if spec.prior_assessment.kind != "research_assessment":
                raise ConfigurationError("Hypothesis feedback requires an actual R7/R8 assessment")
            previous_assessment = research.active(connection, spec.prior_assessment)
            for citation in previous_assessment:
                EvidenceResolver(connection).resolve(citation, purpose="new_claim")
            prior_payload = json.loads(repo.entity(spec.prior_assessment)["payload_json"])
            for prediction in spec.predictions:
                entity_active(connection, prediction.hypothesis)
            if {p.hypothesis.revision_id for p in spec.predictions} != {
                j["hypothesis"]["revision_id"] for j in prior_payload["judgments"]
            }:
                raise ConfigurationError(
                    "Preserve all prior rival hypotheses in registered experiment predictions"
                )
        assignments = {u.key: u.variant for u in spec.units}
        if spec.assignment_method == "engine_block_randomized":
            rng = np.random.default_rng(spec.seed)
            for block in sorted({u.block for u in spec.units}):
                pair = sorted((u for u in spec.units if u.block == block), key=lambda u: u.key)
                arms = rng.permutation([v.key for v in spec.variants]).tolist()
                assignments.update({u.key: arm for u, arm in zip(pair, arms, strict=True)})
        payload = {
            "spec": raw,
            "registered_at": now,
            "assignments": assignments,
            "status": "registered_not_executed",
            "claim_level": "registered_design_not_evidence_of_effect",
            "summary": "Frozen assignment and analysis plan; no external action authorized",
        }
        provenance = research.provenance(connection, "experiment:" + spec.key, payload)
        entities = tuple(
            {
                r.revision_id: r
                for r in (
                    *(u.account for u in spec.units),
                    *definitions,
                    *spec.context,
                    *(o.operationalization for o in spec.outcomes if o.operationalization),
                    *((spec.predecessor,) if spec.predecessor else ()),
                    *((spec.prior_assessment,) if spec.prior_assessment else ()),
                )
            }.values()
        )
        ref = research.save(
            connection,
            "experiment_registration",
            spec.key,
            payload,
            provenance,
            entities=entities,
            evidence=spec.origin,
        )
        repository.put(
            connection,
            "experiment_registrations",
            revision_id=ref.revision_id,
            protocol_hash=hash_config(raw),
            registered_at=now,
        )
        _archive(app, connection, ref)
        return _response(connection, ref)


def _snapshot(
    connection: Any, registration: dict[str, Any], spec: ExperimentResults
) -> dict[str, Any]:
    plan = ExperimentSpec.model_validate(registration["spec"])
    repo = EvidenceRepository(connection)
    units = {u.key: u for u in plan.units}
    if set(u.unit_key for u in spec.units) - set(units):
        raise ConfigurationError("Results contain assignment units outside the frozen roster")
    if spec.collected_at > utc_now():
        raise ConfigurationError("Results collection cannot be in the future")
    latest_plan = repo.latest("experiment_registration", spec.registration.id)
    if latest_plan != spec.registration:
        threats_superseded = [
            "A superseded registration cannot support a new confirmatory interpretation"
        ]
    else:
        threats_superseded = []
    if (
        plan.assignment_unit == "impression"
        and spec.permission_basis != "permitted_native_experiment_export"
    ):
        raise ConfigurationError(
            "Native impression reports require explicit permitted experiment exports"
        )
    threats = threats_superseded
    if any(
        getattr(spec.review, key) is not True
        for key in (
            "allocation_intact",
            "no_spillover",
            "no_carryover",
            "no_concurrent_changes",
            "no_interim_looks",
            "complete_roster",
        )
    ):
        threats.append("Execution/assignment/interference/stopping review is false or unknown")
    if spec.deviations:
        threats.append("Reported protocol deviations: causal qualification withheld")
    if spec.collected_at < plan.final_cutoff():
        threats.append(
            "Final source collection precedes the registered complete stopping/lag cutoff"
        )
    if set(u.unit_key for u in spec.units) != set(units):
        threats.append("Incomplete randomized roster; missing assignments not dropped")
    if any(u.starts_at <= registration["registered_at"] for u in plan.units):
        threats.append("Retrospective registration cannot establish prospective assignment")
    submitted = {u.unit_key: u for u in spec.units}
    creators: dict[str, set[str]] = defaultdict(set)
    accounts_seen, subjects_seen, measurements_seen, media_seen = set(), set(), set(), set()
    rows, citations, entities = [], [], []
    for unit in plan.units:
        actual = submitted.get(unit.key)
        if actual and set(actual.outcomes) - {o.key for o in plan.outcomes}:
            raise ConfigurationError("Unregistered outcomes cannot enter the planned test family")
        account = _account(connection, unit.account)
        creator = account.get("creator_id")
        if not creator:
            threats.append("Supplied independent creator identities are required")
        creators[str(creator or unit.account.id)].add(unit.block)
        if plan.assignment_unit == "account_period" and unit.account.id in accounts_seen:
            threats.append("Repeated account periods require an unsupported carryover design")
        accounts_seen.add(unit.account.id)
        assigned = registration["assignments"][unit.key]
        if actual is None or actual.implemented_variant != assigned:
            threats.append(
                "Missing/changed treatment implementation; treatment-receipt effect not identified"
            )
        row = {
            "unit_key": unit.key,
            "block": unit.block,
            "creator_id": creator,
            "account_id": unit.account.id,
            "assigned": assigned,
            "values": {},
            "missingness": {},
        }
        if actual and actual.outcomes and actual.subject is None:
            raise ConfigurationError(
                "Actual outcomes need their measured subject, not a planned slot"
            )
        if actual and actual.subject:
            if actual.subject.kind not in ("post", "account"):
                raise ConfigurationError("Assignment outcomes require actual post/account subjects")
            subject = _account(connection, actual.subject)
            if plan.assignment_unit == "account_period":
                if actual.subject.kind != "account" or actual.subject.id != unit.account.id:
                    raise ConfigurationError(
                        "Account-period results must measure the assigned actual account"
                    )
            elif (
                actual.subject.kind != "post"
                or subject["account_id"] != unit.account.id
                or subject["published_at"] != unit.starts_at
            ):
                raise ConfigurationError(
                    "Post results must measure the assigned account's exact publication slot"
                )
            if actual.subject.id in subjects_seen and plan.assignment_unit != "impression":
                threats.append(
                    "Repeated measured subjects cannot increase assignment-unit sample size"
                )
            subjects_seen.add(actual.subject.id)
            entities.append(actual.subject)
            if actual.subject.kind == "post":
                versions, assets = (
                    metadata.tables["post_media_versions"],
                    metadata.tables["media_assets"],
                )
                digest = connection.scalar(
                    select(assets.c.sha256)
                    .join(versions, versions.c.media_id == assets.c.id)
                    .where(versions.c.post_id == actual.subject.id, versions.c.position == 0)
                    .order_by(versions.c.available_at.desc())
                    .limit(1)
                )
                if digest and digest in media_seen:
                    threats.append(
                        "Duplicate media do not establish independent experimental units"
                    )
                if digest:
                    media_seen.add(digest)
        contexts = []
        if actual:
            for ctx in actual.context:
                if ctx.kind not in context.KINDS:
                    raise ConfigurationError("Execution context needs a delivered C1 producer")
                captured = context.read(connection, ctx)
                if captured["account"]["id"] != unit.account.id or (
                    captured["post"]
                    and (actual.subject is None or captured["post"]["id"] != actual.subject.id)
                ):
                    raise ConfigurationError(
                        "Execution context belongs to another assigned account/post"
                    )
                contexts.append((ctx, captured))
                entities.append(ctx)
                citations.append(context.cite(connection, ctx))
        if plan.domain == "profile" and not any(
            ctx.kind == "funnel_context"
            and data["result"]["profile_exposure"] == "source_attested"
            and actual
            and all(
                measured.model_dump()
                in [s["measurement"] for s in data["result"]["stages"].values()]
                for measured in actual.outcomes.values()
            )
            for ctx, data in contexts
        ):
            threats.append(
                "Profile assignment requires actual exact-version exposed C1 funnel outcomes"
            )
        if plan.domain == "publishing":
            if not any(
                (
                    ctx.kind == "publication_context"
                    and data["spec"]["clock"]["validity_basis"] == "source_attested"
                    and data["spec"]["clock"]["valid_from"] <= unit.starts_at
                    and (
                        not data["spec"]["clock"]["valid_until"]
                        or unit.starts_at < data["spec"]["clock"]["valid_until"]
                    )
                )
                if plan.assignment_unit == "post"
                else (
                    ctx.kind == "publishing_window"
                    and data["spec"]["complete"]
                    and data["spec"]["includes_deleted_and_omitted"]
                    and data["spec"]["window_start"] <= unit.starts_at
                    and data["spec"]["window_end"]
                    >= timestamp(
                        (
                            datetime.fromisoformat(unit.starts_at)
                            + timedelta(
                                seconds=max(
                                    o.window_offset_seconds + o.window_seconds
                                    for o in plan.outcomes
                                )
                            )
                        ).isoformat()
                    )
                )
                for ctx, data in contexts
            ):
                threats.append(
                    "Publishing assignment needs historical packaging or complete exposure context"
                )
        distribution = [
            data["result"] for ctx, data in contexts if ctx.kind == "distribution_observation"
        ]
        if plan.domain == "distribution" and not distribution:
            threats.append(
                "Distribution requires C1 surface-qualified observations, not aggregate views"
            )
        for outcome in plan.outcomes:
            value, reason = None, actual.missing_reason if actual else "missing assigned unit"
            measured = actual.outcomes.get(outcome.key) if actual else None
            if measured:
                if measured.kind != "metric_measurement":
                    raise ConfigurationError(
                        "Use actual scalar measurements, not bins, series or attributed credits"
                    )
                data = behavior.read(connection, measured)
                raw = data["spec"]
                assert actual is not None and actual.subject is not None
                if (
                    raw["subject"] != actual.subject.model_dump()
                    or raw["definition"] != outcome.definition.model_dump()
                ):
                    raise ConfigurationError(
                        "Outcome definition/assigned measured subject mismatch"
                    )
                clock = raw["clock"]
                length = (
                    datetime.fromisoformat(clock["window_end"])
                    - datetime.fromisoformat(clock["window_start"])
                ).total_seconds()
                expected_start = timestamp(
                    (
                        datetime.fromisoformat(unit.starts_at)
                        + timedelta(seconds=outcome.window_offset_seconds)
                    ).isoformat()
                )
                if clock["window_start"] != expected_start or length != outcome.window_seconds:
                    raise ConfigurationError(
                        "Outcome measurement does not match the registered source window"
                    )
                if clock["collected_at"] > spec.collected_at:
                    raise ConfigurationError("Result export predates actual outcome collection")
                if measured.revision_id in measurements_seen:
                    raise ConfigurationError(
                        "A measurement cannot count as several independent assignment units"
                    )
                measurements_seen.add(measured.revision_id)
                bindings, result_sets = (
                    metadata.tables["experiment_measurement_bindings"],
                    metadata.tables["experiment_results"],
                )
                if connection.scalar(
                    select(bindings.c.results_revision_id)
                    .join(result_sets, result_sets.c.revision_id == bindings.c.results_revision_id)
                    .where(
                        bindings.c.measurement_revision_id == measured.revision_id,
                        result_sets.c.registration_revision_id != spec.registration.revision_id,
                    )
                ):
                    threats.append(
                        "Outcome inspected in another experiment; not independent replication"
                    )
                value = (
                    data["result"]["value"]
                    if data["result"]["availability"] == "available"
                    else None
                )
                reason = data["result"].get("reason")
                if clock["data_cutoff"] != clock["window_end"]:
                    value, reason = None, "incomplete effective source cutoff"
                cohort = behavior.read(connection, EntityRef.model_validate(raw["cohort"]))["spec"]
                if not cohort["known"]:
                    value, reason = None, "unknown outcome cohort"
                if plan.domain == "distribution" and not any(
                    d["mapping"]["surface"] == plan.scope.surface
                    and d["mapping"]["traffic"] == plan.scope.traffic
                    and all(
                        d["scope"][k] == getattr(plan.scope, k)
                        for k in (
                            "platform",
                            "surface",
                            "native_format",
                            "language",
                            "market",
                            "audience",
                        )
                    )
                    and d["scope"]["niche"] in plan.scope.niches
                    and measured.model_dump() in [d[p]["ref"] for p in ("early", "later")]
                    for d in distribution
                ):
                    threats.append(
                        "Outcome is incompatible with the distribution surface/source observation"
                    )
                row.setdefault("cohorts", {})[outcome.key] = {
                    k: cohort[k] for k in ("eligibility", "dimensions")
                }
                entities.append(measured)
                citations.append(behavior.evidence_ref(connection, measured))
            row["values"][outcome.key], row["missingness"][outcome.key] = (
                value,
                reason or ("not supplied" if value is None else None),
            )
        rows.append(row)
    if any(len(blocks) != 1 for blocks in creators.values()):
        threats.append("A creator spans blocks; independent block uncertainty is unsupported")
    if plan.assignment_unit == "post":
        for block in {r["block"] for r in rows}:
            if len({r["creator_id"] for r in rows if r["block"] == block}) != 1:
                threats.append("Post pairs must share one creator within each independent block")
    # Source cohort definitions cannot silently differ by variant.
    for outcome in plan.outcomes:
        if (
            len(
                {
                    canonical_json(r["cohorts"][outcome.key])
                    for r in rows
                    if outcome.key in r.get("cohorts", {})
                }
            )
            > 1
        ):
            threats.append("Incompatible source cohort populations across assigned units")
    allowed_subjects = {r.revision_id for r in entities} | {r.revision_id for r in plan.context}
    for ref in spec.review.evidence:
        resolved = EvidenceResolver(connection).resolve(ref, purpose="new_claim")
        if resolved.subject.revision_id not in allowed_subjects:
            raise ConfigurationError(
                "Execution review evidence is outside this experiment's actual sources"
            )
        citations.append(ref)
    return {
        "rows": rows,
        "threats": sorted(set(threats)),
        "entities": list({r.revision_id: r.model_dump() for r in entities}.values()),
        "evidence": list({r.revision_id: r.model_dump() for r in citations}.values()),
    }


def import_results(app: Application, spec: ExperimentResults) -> dict[str, Any]:
    with app.database.transaction() as connection:
        registered = repository.content(connection, spec.registration)
        table = metadata.tables["experiment_results"]
        refs: list[str] = list(
            connection.scalars(
                select(table.c.revision_id).where(
                    table.c.registration_revision_id == spec.registration.revision_id
                )
            )
        )
        previous = None
        if refs:
            repo = EvidenceRepository(connection)
            latest = max(
                (repo.get("entity_revisions", r) for r in refs), key=lambda r: r["revision_no"]
            )
            previous = repo.ref(latest)
            old = repository.content(connection, previous)
            if old["spec"] == spec.model_dump(mode="json"):
                return _response(connection, previous)
            if spec.supersedes != previous or old["spec"]["key"] != spec.key:
                raise ConfigurationError(
                    "One result stream; changes need supersedes and a correction reason"
                )
        elif spec.supersedes:
            raise ConfigurationError("Cannot correct an experiment without earlier results")
        snapshot = _snapshot(connection, registered, spec)
        payload = {
            "spec": spec.model_dump(mode="json"),
            "registration": spec.registration.model_dump(),
            "snapshot": snapshot,
            "claim_level": "source_attested_outcomes_not_effect",
            "summary": "Actual assigned-unit outcomes and execution review; not an analysis",
        }
        provenance = research.provenance(
            connection,
            "experiment-results:" + spec.registration.revision_id,
            payload,
            uri=spec.source_uri,
            permission=spec.permission_basis,
            source_kind="experiment_results_export",
        )
        ref = research.save(
            connection,
            "experiment_results",
            spec.registration.revision_id + ":" + spec.key,
            payload,
            provenance,
            entities=(
                spec.registration,
                *(EntityRef.model_validate(r) for r in snapshot["entities"]),
                *((previous,) if previous else ()),
            ),
            evidence=tuple(EvidenceRef.model_validate(r) for r in snapshot["evidence"]),
        )
        repository.put(
            connection,
            "experiment_results",
            revision_id=ref.revision_id,
            registration_revision_id=spec.registration.revision_id,
        )
        for unit in spec.units:
            for key, measured in unit.outcomes.items():
                assert unit.subject
                repository.put(
                    connection,
                    "experiment_measurement_bindings",
                    results_revision_id=ref.revision_id,
                    unit_key_hash=hash_config({"key": unit.unit_key}),
                    outcome_key_hash=hash_config({"key": key}),
                    subject_revision_id=unit.subject.revision_id,
                    measurement_revision_id=measured.revision_id,
                )
        _archive(app, connection, ref)
        return _response(connection, ref)


def analyze(app: Application, results: EntityRef) -> dict[str, Any]:
    if results.kind != "experiment_results":
        raise ConfigurationError("Analysis requires an exact experiment outcome revision")
    with app.database.transaction() as connection:
        source = repository.content(connection, results)
        registered_ref = EntityRef.model_validate(source["registration"])
        registered = repository.content(connection, registered_ref)
        spec = ExperimentSpec.model_validate(registered["spec"])
        table = metadata.tables["experiment_analyses"]
        saved = connection.scalar(
            select(table.c.revision_id).where(table.c.results_revision_id == results.revision_id)
        )
        if saved:
            ref = EvidenceRepository(connection).ref(
                EvidenceRepository(connection).get("entity_revisions", saved)
            )
            repository.content(connection, ref)
            return _response(connection, ref)
        family_id = "experiment:" + registered_ref.revision_id
        repository.put(
            connection,
            "test_families",
            id=family_id,
            spec_json=canonical_json(
                {
                    "outcomes": [o.model_dump(mode="json") for o in spec.outcomes],
                    "stopping": spec.stopping,
                    "method": engine.METHOD,
                }
            ),
            created_at=utc_now(),
        )
        attempt_id = new_id()
        connection.execute(
            metadata.tables["test_attempts"]
            .insert()
            .values(
                id=attempt_id,
                family_id=family_id,
                status="started",
                result_json=canonical_json({"results": results.model_dump()}),
                created_at=utc_now(),
            )
        )
    try:
        computed = engine.analyze(spec, source["snapshot"])
        with app.database.transaction() as connection:
            repository.content(connection, results)
            payload = {
                "registration": registered_ref.model_dump(),
                "results": results.model_dump(),
                "attempt_id": attempt_id,
                "libraries": _versions(),
                "analysis": computed,
                "claim_level": computed["claim_level"],
                "mechanism_status": computed["mechanism_status"],
                "summary": "Registered assignment contrast, conditional on source execution review",
                "independent_replication": False,
            }
            provenance = research.provenance(connection, "experiment-analysis", payload)
            ref = research.save(
                connection,
                "experiment_analysis",
                results.revision_id,
                payload,
                provenance,
                entities=(registered_ref, results),
            )
            repository.put(
                connection,
                "experiment_analyses",
                revision_id=ref.revision_id,
                registration_revision_id=registered_ref.revision_id,
                results_revision_id=results.revision_id,
                attempt_id=attempt_id,
            )
            assessment = _assess(connection, spec, ref, computed, provenance)
            connection.execute(
                metadata.tables["test_attempts"]
                .update()
                .where(metadata.tables["test_attempts"].c.id == attempt_id)
                .values(
                    status="completed",
                    result_json=canonical_json(
                        {"analysis": ref.model_dump(), "result_hash": hash_config(computed)}
                    ),
                )
            )
            _archive(app, connection, ref)
            return {**_response(connection, ref), "assessment": assessment}
    except Exception as exc:
        with app.database.transaction() as connection:
            connection.execute(
                metadata.tables["test_attempts"]
                .update()
                .where(metadata.tables["test_attempts"].c.id == attempt_id)
                .values(
                    status="failed", result_json=canonical_json({"error_type": type(exc).__name__})
                )
            )
        raise


def _assess(
    connection: Any,
    spec: ExperimentSpec,
    analysis: EntityRef,
    result: dict[str, Any],
    provenance: str,
) -> dict[str, Any] | None:
    if not spec.prior_assessment:
        return None
    previous = repository.content(connection, spec.prior_assessment)
    judgments = []
    for prediction in spec.predictions:
        outcome = next(o for o in result["outcomes"] if o["key"] == prediction.outcome_key)
        declared = next(o for o in spec.outcomes if o.key == prediction.outcome_key)
        disposition = "insufficient_data"
        if outcome["adjusted_p_value"] is not None:
            low, high = outcome["ci_low"], outcome["ci_high"]
            lower, upper = (low, high) if prediction.direction == "positive" else (-high, -low)
            disposition = (
                "supported_in_scope"
                if outcome["adjusted_p_value"] <= 0.05
                and lower > declared.minimum_meaningful_difference
                else "contradicted_in_scope"
                if outcome["adjusted_p_value"] <= 0.05 and upper < 0
                else "inconclusive"
            )
        judgments.append(
            {
                "hypothesis": prediction.hypothesis.model_dump(),
                "outcome": prediction.outcome_key,
                "treatment_prediction_disposition": disposition,
                "mechanism_status": "not_identified",
                "interpretation": "Assignment effects do not identify rivals or mediation",
            }
        )
    question = EntityRef.model_validate(previous["question"])
    payload = {
        "analysis": analysis.model_dump(),
        "prior": spec.prior_assessment.model_dump(),
        "question": question.model_dump(),
        "judgments": judgments,
        "claim_level": "qualified_experiment_feedback_not_mechanism_proof",
        "summary": "New experiment-linked assessment; prior observational assessment preserved",
    }
    ref = research.save(
        connection,
        "experiment_assessment",
        analysis.revision_id,
        payload,
        provenance,
        entities=(
            analysis,
            spec.prior_assessment,
            question,
            *(p.hypothesis for p in spec.predictions),
        ),
    )
    repository.put(
        connection,
        "experiment_assessments",
        revision_id=ref.revision_id,
        analysis_revision_id=analysis.revision_id,
        prior_revision_id=spec.prior_assessment.revision_id,
        question_revision_id=question.revision_id,
    )
    for prediction in spec.predictions:
        repository.put(
            connection,
            "experiment_hypotheses",
            assessment_revision_id=ref.revision_id,
            hypothesis_revision_id=prediction.hypothesis.revision_id,
        )
    return _response(connection, ref)


def show(app: Application, ref: EntityRef, *, reproduce: bool = False) -> dict[str, Any]:
    with app.database.transaction() as connection:
        payload = repository.content(connection, ref)
        if reproduce:
            if (
                ref.kind != "experiment_analysis"
                or payload["libraries"] != _versions()
                or payload["analysis"]["method"] != engine.METHOD
            ):
                raise ConfigurationError(
                    "Reproduction requires an analysis and its numerical libraries"
                )
            source = repository.content(connection, EntityRef.model_validate(payload["results"]))
            registration = repository.content(
                connection, EntityRef.model_validate(payload["registration"])
            )
            computed = engine.analyze(
                ExperimentSpec.model_validate(registration["spec"]), source["snapshot"]
            )
            if canonical_json(computed) != canonical_json(payload["analysis"]):
                raise StorageIntegrityError("Frozen experiment reproduction differs")
        return {
            **_response(connection, ref),
            "reproduced": reproduce,
            "operational_freshness": "current"
            if current_revision(connection, ref)
            else "stale_frozen_context",
        }
