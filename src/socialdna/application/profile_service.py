"""Dated public profiles, frozen human rubrics and separately measured account funnels."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from socialdna.analytics.attribution import summarize_attribution
from socialdna.analytics.funnels import rates
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.context_service import (
    capture_image,
    freeze_report,
    provenance,
    read_spec,
)
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import ContextLocator, EntityRef, EvidenceRef, PostTextLocator
from socialdna.domain.profile import (
    RUBRIC,
    FunnelContext,
    FunnelDefinition,
    ProfileExport,
    ProfileReportSpec,
    ProfileReview,
    ProfileSnapshot,
)
from socialdna.storage import behavioral_repository as behavioral
from socialdna.storage import context_repository as context
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.profile_repository import bind_events
from socialdna.storage.schema import metadata


def register_rubric(connection: Connection) -> EntityRef:
    _, producer = provenance(
        connection,
        RUBRIC,
        "urn:socialdna:profile-rubric/1",
        "locally_installed_versioned_engine_rubric",
    )
    repo = EvidenceRepository(connection)
    identity = stable_id("profile-rubric", RUBRIC["id"])
    previous = repo.latest("profile_rubric", identity)
    if previous and json.loads(repo.entity(previous)["payload_json"]) != RUBRIC:
        raise StorageIntegrityError("Profile rubric changed without a new pin")
    return repo.save_entity("profile_rubric", identity, RUBRIC, producer, available_at=utc_now())


def owned_post(repo: EvidenceRepository, post: EntityRef, account: EntityRef, capture: str) -> None:
    data = json.loads(repo.entity(post)["payload_json"])
    if (
        post.kind != "post"
        or data["account_id"] != account.id
        or (data["published_at"] and data["published_at"] > capture)
    ):
        raise ConfigurationError("Profile/sample post has wrong ownership or date")


def validate_review(connection: Connection, review: ProfileReview) -> tuple[EvidenceRef, ...]:
    if review.snapshot.kind != "profile_snapshot":
        raise ConfigurationError("Profile assessment requires an exact public snapshot")
    snapshot = context.read(connection, review.snapshot)
    if (
        snapshot["account"]["id"] != review.account.id
        or not snapshot["spec"]["clock"]["captured_at"] <= review.reviewed_at <= utc_now()
    ):
        raise ConfigurationError("Profile review account/date mismatch")
    repo = EvidenceRepository(connection)
    for post_ref in review.sample_posts:
        owned_post(repo, post_ref, review.account, review.reviewed_at)
        published = json.loads(repo.entity(post_ref)["payload_json"])["published_at"]
        if (
            not published
            or not review.sample_window_start
            or not review.sample_window_end
            or not review.sample_window_start <= published < review.sample_window_end
        ):
            raise ConfigurationError(
                "Review sample post is outside the declared source-time window"
            )
    evidence = tuple(
        {
            r.revision_id: r for c in review.criteria for r in (*c.evidence, *c.counterexamples)
        }.values()
    )
    for ref in evidence:
        resolved = EvidenceResolver(connection).resolve(ref, purpose="new_claim")
        locator = resolved.locator
        if not (
            isinstance(locator, ContextLocator)
            and locator.subject == review.snapshot
            or isinstance(locator, PostTextLocator)
            and locator.subject in review.sample_posts
        ):
            raise ConfigurationError(
                "Rubric evidence must belong to the actual profile or declared post sample, "
                "not performance metrics"
            )
    return evidence


def validate_definition(connection: Connection, definition: FunnelDefinition) -> None:
    for binding in definition.bindings:
        if binding.definition.kind != "behavioral_metric_definition":
            raise ConfigurationError("Funnel event bindings require actual R5 definitions")
        metric = behavioral.read(connection, binding.definition)["spec"]
        account = json.loads(
            EvidenceRepository(connection).entity(definition.account)["payload_json"]
        )
        if (
            metric["platform"] != account["platform"]
            or metric["subject_type"] != "account"
            or metric["measurement"] != "period"
            or metric["semantics"] != "count"
        ):
            raise ConfigurationError(
                "Funnel stages require source-defined account-period counts, "
                "not follower stock or signed net growth"
            )
        if metric["numerator_definition"] != binding.source_definition_excerpt:
            raise ConfigurationError("Event mapping must quote the actual source definition")
        if (
            binding.signal in ("app_installs", "purchases", "follows")
            and metric["meaning"] != "conversion"
        ):
            raise ConfigurationError(
                "Measured acquisition/install/purchase outcomes require actual conversion "
                "definitions, not clicks"
            )
        if binding.uniqueness == "unique_accounts" and (
            metric["population_basis"] != "accounts"
            or metric["replay_policy"] not in ("not_applicable", "excludes_replays")
        ):
            raise ConfigurationError(
                "Unique-account bindings require compatible source population/replay semantics"
            )


def funnel_data(
    connection: Connection, spec: FunnelContext, cutoff: str | None = None
) -> dict[str, Any]:
    if spec.definition.kind != "funnel_definition":
        raise ConfigurationError("Funnel observations require a reviewed source event definition")
    definition = context.read(connection, spec.definition, cutoff)
    if definition["account"]["id"] != spec.account.id:
        raise ConfigurationError("Funnel definition belongs to another account")
    manifest = definition["spec"]
    bindings = {b["definition"]["revision_id"]: b for b in manifest["bindings"]}
    stages: dict[str, dict[str, Any]] = {}
    signatures: set[tuple[str, str, str, str]] = set()
    for stage in spec.stages:
        if stage.measurement.kind != "metric_measurement":
            raise ConfigurationError(
                "Funnel stages need actual scalar owner-analytics measurements"
            )
        row = behavioral.read(connection, stage.measurement, cutoff)
        raw = row["spec"]
        if raw["subject"]["kind"] != "account" or raw["subject"]["id"] != spec.account.id:
            raise ConfigurationError("Funnel stages must measure the actual declared account")
        binding = bindings.get(raw["definition"]["revision_id"])
        if not binding:
            raise ConfigurationError("Counter has no source event binding; it cannot be relabeled")
        metric = behavioral.read(connection, EntityRef.model_validate(raw["definition"]), cutoff)[
            "spec"
        ]
        cohort = behavioral.read(connection, EntityRef.model_validate(raw["cohort"]), cutoff)[
            "spec"
        ]
        if (
            raw["clock"]["window_start"] >= raw["clock"]["window_end"]
            or raw["clock"]["collected_at"] > spec.clock.captured_at
        ):
            raise ConfigurationError("Funnel window/capture predates actual collection")
        signature = (
            binding["source_event_code"],
            raw["cohort"]["revision_id"],
            raw["clock"]["window_start"],
            raw["clock"]["window_end"],
        )
        if signature in signatures:
            raise ConfigurationError(
                "A repeated source counter/window cannot receive duplicate conversion credit"
            )
        signatures.add(signature)
        stages[stage.key] = {
            "signal": binding["signal"],
            "measurement": stage.measurement.model_dump(),
            "definition": raw["definition"],
            "cohort": raw["cohort"],
            "cohort_known": cohort["known"],
            "clock": raw["clock"],
            "value": row["result"]["value"],
            "availability": row["result"]["availability"],
            "reason": row["result"].get("reason"),
            "unit": metric["unit"],
            "population_basis": metric["population_basis"],
            "uniqueness": binding["uniqueness"],
            "evidence": behavioral.evidence_ref(connection, stage.measurement).model_dump(),
        }
    for rate in spec.rates:
        for ref in rate.linkage_evidence:
            evidence = EvidenceResolver(connection).resolve(ref, purpose="new_claim", as_of=cutoff)
            if (
                not isinstance(evidence.locator, ContextLocator)
                or evidence.subject != spec.definition
            ):
                raise ConfigurationError(
                    "Funnel linkage evidence must cite the actual source-join manifest"
                )
    if spec.profile:
        if spec.profile.kind != "profile_snapshot":
            raise ConfigurationError(
                "Profile context must cite a real snapshot, not a fake metric subject"
            )
        profile = context.read(connection, spec.profile, cutoff)
        if profile["account"]["id"] != spec.account.id:
            raise ConfigurationError("Profile belongs to another account")
        if spec.profile_exposure == "source_attested":
            clock = profile["spec"]["clock"]
            if (
                clock["validity_basis"] != "source_attested"
                or not clock["valid_from"]
                or not clock["valid_until"]
                or any(
                    not clock["valid_from"]
                    <= stage["clock"]["window_start"]
                    < stage["clock"]["window_end"]
                    <= clock["valid_until"]
                    for stage in stages.values()
                )
            ):
                raise ConfigurationError(
                    "Historical profile exposure requires a source-attested covering interval"
                )
        for ref in spec.exposure_evidence:
            evidence = EvidenceResolver(connection).resolve(ref, purpose="new_claim", as_of=cutoff)
            if evidence.subject != spec.profile:
                raise ConfigurationError("Exposure evidence belongs to another profile version")
    attribution_rows: dict[str, list[dict[str, Any]]] = {}
    event_sets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for attribution_ref in spec.attributions:
        if attribution_ref.kind != "attribution_observation":
            raise ConfigurationError("Use actual R5 source-reported attribution")
        row = behavioral.read(connection, attribution_ref, cutoff)
        if (
            row["spec"]["subject"]["kind"] != "account"
            or row["spec"]["subject"]["id"] != spec.account.id
        ):
            raise ConfigurationError("Attribution belongs to another account")
        matching = [
            key
            for key, stage in stages.items()
            if stage["definition"] == row["spec"]["definition"]
            and stage["cohort"] == row["spec"]["cohort"]
            and all(
                stage["clock"][part] == row["spec"]["clock"][part]
                for part in ("window_start", "window_end", "data_cutoff")
            )
            and stage["value"] == row["result"]["value"]
        ]
        if len(matching) != 1:
            raise ConfigurationError(
                "Attribution must match one actual stage counter, cohort, value and window"
            )
        attribution_rows.setdefault(matching[0], []).append(row)
        event_key = (
            bindings[row["spec"]["definition"]["revision_id"]]["source_event_code"],
            row["spec"]["cohort"]["revision_id"],
        )
        event_sets.setdefault(event_key, []).append(row)
    for rows in event_sets.values():
        check = summarize_attribution(rows)
        if check["duplicate_refs_excluded"] or any(
            "overlapping_conversion_windows" in reason or "conflicting_duplicate" in reason
            for reason in check["limitations"]
        ):
            raise ConfigurationError("Repeated or overlapping conversion credit cannot be combined")
    attribution = {key: summarize_attribution(rows) for key, rows in attribution_rows.items()}
    if any(
        summary["duplicate_refs_excluded"]
        or any(
            "overlapping_conversion_windows" in r or "conflicting_duplicate" in r
            for r in summary["limitations"]
        )
        for summary in attribution.values()
    ):
        raise ConfigurationError("Repeated or overlapping conversion credit cannot be combined")
    for summary in attribution.values():
        summary["unassigned_credit"] = [
            {
                "source_ref": row["ref"],
                "value": None
                if row["result"]["value"] is None
                or row["spec"]["allocation_policy"] == "full_credit_each"
                else row["result"]["value"]
                * (
                    1
                    if row["spec"]["allocation_policy"] == "unallocated"
                    else max(0, 1 - sum(c["weight"] for c in row["spec"]["credits"]))
                ),
                "interpretation": "remainder_of_source_allocation_not_individual_people",
            }
            for row in summary["observations"]
        ]
    return {
        "stages": stages,
        "rates": rates(stages, spec.rates, manifest),
        "profile_exposure": spec.profile_exposure,
        "source_attribution": attribution,
        "profile_effect_estimated": False,
        "individual_journeys_reconstructed": False,
        "credit_to_profile_or_nearest_post": "not_created",
        "limitations": [
            "Public profile quality is not measured conversion. Aggregate source rates do not "
            "identify individual journeys or causal profile effects.",
            "Actual counter meanings, units, cohorts, windows and source-reported joins "
            "are required; missing owner data stays unknown.",
        ],
    }


def import_document(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = read_spec(path, ProfileExport)
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "limitations": [
                "Schema only; actual ownership, source metrics, joins and review evidence "
                "checked on import."
            ],
        }
    with open_application(settings) as app:
        return import_into_application(app, spec, base=path.parent)


def import_into_application(
    app: Application, spec: ProfileExport, *, base: Path | None = None
) -> dict[str, Any]:
    raw = spec.model_dump(mode="json")
    with app.database.transaction() as connection:
        source, producer = provenance(connection, raw, spec.source_uri, spec.permission_basis)
        records = []
        for record in spec.records:
            data = record.model_dump(mode="json")
            inputs: tuple[EntityRef, ...] = ()
            evidence: tuple[EvidenceRef, ...] = ()
            result = None
            asset = None
            if isinstance(record, ProfileSnapshot):
                for pin in record.pins:
                    owned_post(
                        EvidenceRepository(connection),
                        pin,
                        record.account,
                        record.clock.valid_from or record.clock.captured_at,
                    )
                inputs = record.pins
                if record.photo:
                    asset = capture_image(
                        app,
                        connection,
                        Path(record.photo.path),
                        record.photo.sha256,
                        variant="profile-photo",
                        placement="profile",
                        kind="profile-photo",
                        base=base,
                    )
                    data["photo"] = asset
            elif isinstance(record, ProfileReview):
                evidence = validate_review(connection, record)
                rubric = register_rubric(connection)
                inputs = (record.snapshot, rubric, *record.sample_posts)
                data["rubric"] = RUBRIC
                result = {"claim_level": "qualitative_human_assessment", "conversion_effect": None}
            elif isinstance(record, FunnelDefinition):
                validate_definition(connection, record)
                inputs = tuple(b.definition for b in record.bindings)
            else:
                result = funnel_data(connection, record)
                inputs = (
                    record.definition,
                    *(s.measurement for s in record.stages),
                    *record.attributions,
                    *((record.profile,) if record.profile else ()),
                )
                evidence = tuple(
                    [behavioral.evidence_ref(connection, s.measurement) for s in record.stages]
                    + [r for rate in record.rates for r in rate.linkage_evidence]
                    + list(record.exposure_evidence)
                    + [behavioral.evidence_ref(connection, ref) for ref in record.attributions]
                )
            ref = context.save(
                connection,
                record.record_type,
                spec.dataset_id + ":" + record.key,
                data,
                producer,
                account=record.account,
                entities=inputs,
                evidence=evidence,
                result=result,
            )
            if isinstance(record, FunnelDefinition):
                bind_events(connection, ref, record.bindings)
            citation = context.cite(connection, ref)
            EvidenceResolver(connection).resolve(citation, purpose="new_claim")
            if asset:
                app.artifacts.add_reference(
                    connection,
                    asset["artifact_id"],
                    owner_type="context",
                    owner_id=ref.revision_id,
                    role="profile-photo",
                )
            records.append({"ref": ref.model_dump(), "evidence": citation.model_dump()})
        artifact = app.artifacts.put_bytes(
            connection,
            canonical_json(raw).encode(),
            kind="profile-source",
            mime_type="application/json",
        )
        app.artifacts.add_reference(
            connection, artifact, owner_type="context_source", owner_id=source, role="raw"
        )
        connection.execute(
            metadata.tables["source_records"]
            .update()
            .where(metadata.tables["source_records"].c.id == source)
            .values(raw_artifact_id=artifact)
        )
        return {"valid": True, "written": True, "source_id": source, "records": records}


def report(app: Application, spec: ProfileReportSpec) -> dict[str, Any]:
    if (
        spec.as_of > utc_now()
        or spec.prior.kind != "profile_snapshot"
        or spec.later.kind != "profile_snapshot"
    ):
        raise ConfigurationError(
            "Profile comparison needs actual dated snapshots and a nonfuture cutoff"
        )
    with app.database.transaction() as connection:
        prior, later = [
            context.read(connection, ref, spec.as_of) for ref in (spec.prior, spec.later)
        ]
        if (
            prior["account"]["id"] != later["account"]["id"]
            or prior["spec"]["clock"]["captured_at"] > later["spec"]["clock"]["captured_at"]
            or spec.prior == spec.later
        ):
            raise ConfigurationError(
                "Profile comparison requires distinct chronologically ordered snapshots "
                "of one account"
            )
        account = EntityRef.model_validate(later["account"])
        inputs, evidence = (
            [spec.prior, spec.later],
            [context.cite(connection, spec.prior), context.cite(connection, spec.later)],
        )
        assessments = []
        for ref in spec.reviews:
            if ref.kind != "profile_review":
                raise ConfigurationError(
                    "Profile quality lane requires actual rubric reviews, not metrics"
                )
            data = context.read(connection, ref, spec.as_of)
            if data["spec"]["snapshot"] not in (spec.prior.model_dump(), spec.later.model_dump()):
                raise ConfigurationError("Review belongs to a different profile version")
            assessments.append(
                {
                    "ref": ref.model_dump(),
                    "snapshot": data["spec"]["snapshot"],
                    "rubric": data["spec"]["rubric"],
                    "criteria": data["spec"]["criteria"],
                    "claim_level": "qualitative_human_assessment",
                    "outcome_access": data["spec"]["outcome_access"],
                }
            )
            inputs.append(ref)
            evidence.append(context.cite(connection, ref))
        measured = None
        if spec.funnel:
            if spec.funnel.kind != "funnel_context":
                raise ConfigurationError("Measured lane requires an actual owner-analytics funnel")
            data = context.read(connection, spec.funnel, spec.as_of)
            if data["account"]["id"] != account.id:
                raise ConfigurationError("Funnel belongs to a different account")
            if data["spec"]["profile"] and data["spec"]["profile"] not in (
                spec.prior.model_dump(),
                spec.later.model_dump(),
            ):
                raise ConfigurationError("Funnel exposure refers to a different profile version")
            measured = funnel_data(
                connection, FunnelContext.model_validate(data["spec"]), spec.as_of
            )
            inputs.append(spec.funnel)
            evidence.append(context.cite(connection, spec.funnel))
        fields = (
            "username",
            "display_name",
            "bio",
            "category",
            "positioning",
            "content_pillars",
            "photo",
            "photo_state",
            "links",
            "links_state",
            "pins",
            "pins_state",
        )
        result = {
            "kind": "profile_conversion",
            "comparison_scope": "captured_values_and_availability_not_proven_profile_effects",
            "prior": spec.prior.model_dump(),
            "later": spec.later.model_dump(),
            "changes": {
                field: {"prior": prior["spec"][field], "later": later["spec"][field]}
                for field in fields
                if prior["spec"][field] != later["spec"][field]
            },
            "profile_assessments": assessments,
            "measured_account_funnel": measured,
            "profile_effect_estimated": False,
            "historical_exposure_inferred": False,
            "limitations": [
                "A profile difference or favorable rubric assessment does not establish "
                "measured follows, installs or causal growth.",
                "Per-link/campaign metric subjects and individual journeys are not inferred "
                "from account aggregates. Static visual interpretation requires U1.",
            ],
        }
        return freeze_report(
            app,
            connection,
            account,
            spec.model_dump(mode="json"),
            result,
            tuple(inputs),
            tuple(evidence),
            uri="urn:socialdna:profile-report",
        )
