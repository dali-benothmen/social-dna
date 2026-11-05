"""Public profile/rubric observations versus actual canonical owner-analytics counts."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from test_behavioral_analysis import export

from socialdna.application import behavioral_service
from socialdna.application import profile_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.profile import CRITERIA, ProfileExport, ProfileReportSpec
from socialdna.storage import context_repository as context
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.health import artifact_checks, database_checks


def profile_export(records: list[dict[str, Any]]) -> ProfileExport:
    return ProfileExport.model_validate(
        {
            "dataset_id": "owned-profile",
            "source_uri": "urn:owned:profile",
            "permission_basis": "Owned public-profile captures and authorized owner analytics",
            "records": records,
        }
    )


def owner_metrics(app: Any, account: dict[str, Any]) -> dict[str, Any]:
    signals = ("attention", "profile_visits", "follows", "link_clicks", "app_installs", "purchases")
    counts = (10000, 1000, 100, 200, 20, 5)
    base = {
        "record_type": "behavioral_definition",
        "platform": "demo",
        "subject_type": "account",
        "semantics": "count",
        "unit": "accounts",
        "domain": "nonnegative",
        "measurement": "period",
        "population_basis": "accounts",
        "replay_policy": "not_applicable",
        "source_definition_uri": "urn:owned:source-event-dictionary",
        "description": "Controlled authorized software fixture; "
        "not empirical profile effectiveness",
    }
    definitions = [
        {
            **base,
            "key": f"demo.{signal}.funnel.v1",
            "meaning": "conversion"
            if signal in ("follows", "app_installs", "purchases")
            else "other",
            "numerator_definition": f"Source-reported unique eligible accounts with event {signal} "
            "in the reporting window",
        }
        for signal in signals
    ]
    imported = behavioral_service.import_into_application(
        app,
        export(
            [
                *definitions,
                {
                    "record_type": "audience_cohort",
                    "key": "eligible-profile-accounts",
                    "account": account,
                    "known": True,
                    "eligibility": "Source-reported same eligible account cohort",
                    "aggregation_limitations": "No individual user paths supplied or reconstructed",
                },
            ]
        ),
    )
    refs = [r["ref"] for r in imported["records"]]
    clock = {
        "window_start": "2026-01-01T00:00:00Z",
        "window_end": "2026-02-01T00:00:00Z",
        "data_cutoff": "2026-02-01T00:00:00Z",
        "collected_at": "2026-02-02T00:00:00Z",
    }
    records = [
        {
            "record_type": "metric_measurement",
            "key": f"owned-{signal}",
            "subject": account,
            "definition": refs[i],
            "cohort": refs[-1],
            "clock": clock,
            "measurement": {"value": counts[i]},
        }
        for i, signal in enumerate(signals)
    ]
    measured = behavioral_service.import_into_application(app, export(records))
    return {
        "signals": signals,
        "definitions": refs[:-1],
        "definition_specs": definitions,
        "measurements": [r["ref"] for r in measured["records"]],
        "source_records": records,
        "clock": clock,
        "cohort": refs[-1],
    }


def test_profile_quality_actual_follows_installs_and_history_are_distinct(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    raw_accounts = json.loads(account_export.read_text())
    raw_accounts["records"].append(
        {
            "record_type": "account",
            "platform": "demo",
            "external_id": "other",
            "creator_key": "other",
        }
    )
    account_export.write_text(json.dumps(raw_accounts))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            account = repo.latest("account", stable_id("account", "demo", "0001"))
            pins = [repo.latest("post", stable_id("post", "demo", f"p{i}")) for i in range(2)]
        assert account and all(pins)
        photo = tmp_path / "owned-photo.png"
        Image.new("RGB", (16, 16), "blue").save(photo)
        snapshot = {
            "record_type": "profile_snapshot",
            "key": "public-profile",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-01-10T00:00:00Z"},
            "username": {"state": "present", "value": "ownedcreator"},
            "display_name": {"state": "present", "value": "Owned Creator"},
            "bio": {"state": "present", "value": "Simple cooking lessons."},
            "category": {"state": "not_collected"},
            "positioning": {"state": "present", "value": "Owner-declared practical cooking"},
            "declaration_basis": "owner_declared",
            "content_pillars": ["simple meals", "technique"],
            "photo_state": "present",
            "photo": {"path": str(photo), "sha256": hashlib.sha256(photo.read_bytes()).hexdigest()},
            "links_state": "collected",
            "links": [
                {"key": "app", "label": "Get the app", "destination": "https://example.com/app"}
            ],
            "pins_state": "collected",
            "pins": [p.model_dump() for p in pins if p],
        }
        prior = service.import_into_application(app, profile_export([snapshot]))
        assert service.import_into_application(app, profile_export([snapshot])) == prior
        prior_ref = EntityRef.model_validate(prior["records"][0]["ref"])
        later_snapshot = json.loads(json.dumps(snapshot))
        later_snapshot["clock"]["captured_at"] = "2026-02-02T00:00:00Z"
        later_snapshot["bio"]["value"] = "Simple cooking lessons. Get the app."
        later_snapshot["pins"].reverse()
        later = service.import_into_application(app, profile_export([later_snapshot]))
        later_ref = EntityRef.model_validate(later["records"][0]["ref"])
        assert later_ref.id == prior_ref.id and later_ref.revision_id != prior_ref.revision_id
        with app.database.transaction() as connection:
            bio = context.cite(
                connection,
                later_ref,
                field="bio/value",
                start=0,
                end=len(later_snapshot["bio"]["value"]),
            )
            photo_id = context.read(connection, later_ref)["spec"]["photo"]["artifact_id"]
            assert (
                EvidenceResolver(connection)
                .resolve(context.cite(connection, later_ref, artifact_id=photo_id))
                .eligible
            )
        review = {
            "record_type": "profile_review",
            "key": "rubric-review",
            "account": account.model_dump(),
            "snapshot": later_ref.model_dump(),
            "reviewer": "controlled human-review fixture",
            "procedure": "Review exact captured text and retain unknowns; "
            "not a conversion inference",
            "reviewed_at": utc_now(),
            "outcome_access": "unknown",
            "criteria": [
                {
                    "key": criterion,
                    "verdict": "supported"
                    if criterion in ("bio_clarity", "cta_clarity")
                    else "unknown",
                    "rationale": "Literal app CTA is visible; no inferred performance"
                    if criterion in ("bio_clarity", "cta_clarity")
                    else "Not assessed with adequate sampled evidence",
                    "evidence": [bio.model_dump()]
                    if criterion in ("bio_clarity", "cta_clarity")
                    else [],
                }
                for criterion in CRITERIA
            ],
        }
        review_result = service.import_into_application(app, profile_export([review]))
        review_ref = EntityRef.model_validate(review_result["records"][0]["ref"])
        measured = owner_metrics(app, account.model_dump())
        definition = {
            "record_type": "funnel_definition",
            "key": "source-event-map",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-02-02T00:00:00Z"},
            "reviewer": "controlled source reviewer",
            "source_report": "owned controlled nested-account report",
            "join_basis": "source_reported_nested_counts",
            "deduplication": "source_unique_per_window",
            "linkage_limitations": "Source-attested aggregate subset/dedup only; "
            "no raw individuals or causal effect",
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
        defined = service.import_into_application(app, profile_export([definition]))
        definition_ref = EntityRef.model_validate(defined["records"][0]["ref"])
        manifest_evidence = defined["records"][0]["evidence"]
        funnel = {
            "record_type": "funnel_context",
            "key": "actual-owner-funnel",
            "account": account.model_dump(),
            "clock": {"captured_at": "2026-02-03T00:00:00Z"},
            "definition": definition_ref.model_dump(),
            "profile": later_ref.model_dump(),
            "profile_exposure": "unknown",
            "stages": [
                {"key": signal, "measurement": ref}
                for signal, ref in zip(measured["signals"], measured["measurements"], strict=True)
            ],
            "rates": [
                {
                    "numerator": left,
                    "denominator": right,
                    "source_reports_subset": True,
                    "linkage_evidence": [manifest_evidence],
                }
                for left, right in (
                    ("follows", "profile_visits"),
                    ("app_installs", "link_clicks"),
                    ("purchases", "app_installs"),
                )
            ],
        }
        observed = service.import_into_application(app, profile_export([funnel]))
        funnel_ref = EntityRef.model_validate(observed["records"][0]["ref"])
        request = ProfileReportSpec(
            prior=prior_ref,
            later=later_ref,
            reviews=(review_ref,),
            funnel=funnel_ref,
            as_of=utc_now(),
        )
        report = service.report(app, request)
        assert (
            report["result"]["changes"]["pins"]["prior"]
            != report["result"]["changes"]["pins"]["later"]
        )
        assert (
            report["result"]["profile_assessments"][0]["claim_level"]
            == "qualitative_human_assessment"
        )
        outcome = report["result"]["measured_account_funnel"]
        assert [rate["value"] for rate in outcome["rates"]] == [0.1, 0.1, 0.25]
        assert outcome["stages"]["app_installs"]["value"] == 20
        assert not outcome["profile_effect_estimated"] and outcome["profile_exposure"] == "unknown"
        assert not report["result"]["historical_exposure_inferred"]
        suppressed = json.loads(json.dumps(measured["source_records"][4]))
        suppressed["key"] = "source-suppressed-installs"
        suppressed["measurement"] = {
            "availability": "source_suppressed",
            "reason": "Source privacy threshold",
        }
        suppressed_ref = behavioral_service.import_into_application(app, export([suppressed]))[
            "records"
        ][0]["ref"]
        private = json.loads(json.dumps(funnel))
        private["key"] = "missing-private-installs"
        private["stages"][4]["measurement"] = suppressed_ref
        private_context = service.import_into_application(app, profile_export([private]))
        with app.database.transaction() as connection:
            private_result = context.read(
                connection, EntityRef.model_validate(private_context["records"][0]["ref"])
            )["result"]
            assert private_result["stages"]["app_installs"]["value"] is None
            assert private_result["rates"][1]["value"] is None
        stock = dict(
            measured["definition_specs"][2],
            key="demo.follower_stock.funnel.v1",
            meaning="followers",
            measurement="cumulative",
        )
        stock_ref = behavioral_service.import_into_application(app, export([stock]))["records"][0][
            "ref"
        ]
        invalid_stock = json.loads(json.dumps(definition))
        invalid_stock["bindings"][2]["definition"] = stock_ref
        with pytest.raises(ConfigurationError, match="follower stock"):
            service.import_into_application(app, profile_export([invalid_stock]))
        historical = json.loads(json.dumps(snapshot))
        historical["bio"]["value"] = "Corrected old source text, not the latest public observation"
        service.import_into_application(app, profile_export([historical]))
        from socialdna.application import context_service

        assert context_service.show(app, later_ref.id)["ref"] == later_ref.model_dump()
        assert all(c.status != "error" for c in database_checks(app) + artifact_checks(app))
        relabeled = json.loads(json.dumps(definition))
        relabeled["bindings"][3]["signal"] = "profile_visits"
        with pytest.raises(ConfigurationError, match="cannot be relabeled"):
            service.import_into_application(app, profile_export([relabeled]))
        relabeled["bindings"][3]["signal"] = "app_installs"
        with pytest.raises(ConfigurationError, match="conversion definitions"):
            service.import_into_application(app, profile_export([relabeled]))
        bad = json.loads(json.dumps(funnel))
        bad.update(profile_exposure="source_attested", exposure_evidence=[bio.model_dump()])
        with pytest.raises(ConfigurationError, match="covering interval"):
            service.import_into_application(app, profile_export([bad]))
        historical_exposure = json.loads(json.dumps(later_snapshot))
        historical_exposure["key"] = "source-attested-history"
        historical_exposure["clock"].update(
            validity_basis="source_attested",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-02-01T00:00:00Z",
        )
        historical_exposure.update(pins_state="empty", pins=[])
        supplied = service.import_into_application(app, profile_export([historical_exposure]))
        known = {
            **funnel,
            "key": "source-attested-exposure",
            "profile": supplied["records"][0]["ref"],
            "profile_exposure": "source_attested",
            "exposure_evidence": [supplied["records"][0]["evidence"]],
        }
        known_context = service.import_into_application(app, profile_export([known]))
        known_ref = EntityRef.model_validate(known_context["records"][0]["ref"])
        with app.database.transaction() as connection:
            assert (
                context.read(connection, known_ref)["result"]["profile_exposure"]
                == "source_attested"
            )
        with pytest.raises(ConfigurationError, match="different profile version"):
            service.report(
                app, request.model_copy(update={"funnel": known_ref, "as_of": utc_now()})
            )
        with app.database.transaction() as connection:
            other = EvidenceRepository(connection).latest(
                "account", stable_id("account", "demo", "other")
            )
            assert other
        with pytest.raises(ConfigurationError, match="wrong ownership"):
            service.import_into_application(
                app, profile_export([{**snapshot, "account": other.model_dump()}])
            )
        unlinked = json.loads(json.dumps(funnel))
        unlinked["rates"][0]["source_reports_subset"] = False
        unlinked_result = service.import_into_application(app, profile_export([unlinked]))
        with app.database.transaction() as connection:
            assert (
                context.read(
                    connection, EntityRef.model_validate(unlinked_result["records"][0]["ref"])
                )["result"]["rates"][0]["value"]
                is None
            )
            artifact = EvidenceRepository(connection).get("artifact_objects", report["artifact_id"])
            frozen_path = app.artifacts.path_for(artifact["relative_path"])
            frozen = frozen_path.read_bytes()
        assert (
            service.report(app, request)["ref"] == report["ref"]
            and frozen_path.read_bytes() == frozen
        )
        attribution = {
            **measured["source_records"][4],
            "record_type": "attribution_observation",
            "key": "owned-installs-attribution",
            "attribution_type": "platform_reported",
            "model": "controlled-source-last-touch",
            "lookback_start": measured["clock"]["window_start"],
            "lookback_end": measured["clock"]["window_end"],
            "allocation_policy": "fractional",
            "deduplication_key": "controlled-owned-install-events",
            "credits": [{"post": pins[0].model_dump(), "weight": 0.5}],
        }
        attributed = behavioral_service.import_into_application(app, export([attribution]))
        attributed_ref = attributed["records"][0]["ref"]
        attributed_funnel = {
            **funnel,
            "key": "source-attributed-funnel",
            "attributions": [attributed_ref],
        }
        attributed_context = service.import_into_application(
            app, profile_export([attributed_funnel])
        )
        with app.database.transaction() as connection:
            data = context.read(
                connection, EntityRef.model_validate(attributed_context["records"][0]["ref"])
            )
            summary = data["result"]["source_attribution"]["app_installs"]
            assert summary["source_reported_total"] == 20
            assert summary["unassigned_credit"][0]["value"] == 10
            assert summary["causal_effect"] is None
        duplicate = behavioral_service.import_into_application(
            app, export([{**attribution, "key": "duplicate-source-events"}])
        )
        with pytest.raises(ConfigurationError, match="Repeated or overlapping"):
            service.import_into_application(
                app,
                profile_export(
                    [
                        {
                            **attributed_funnel,
                            "attributions": [attributed_ref, duplicate["records"][0]["ref"]],
                        }
                    ]
                ),
            )
        from socialdna.memory import documents, lexical

        with app.database.transaction() as connection:
            document = documents.build(
                connection, "evidence", review_result["records"][0]["evidence"]["revision_id"]
            )
            assert document and document["claim_level"] == "qualitative_human_assessment"
            lexical.project(connection, document)
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
    assert (
        json.loads(completed.stdout)["data"]["content"]["result"]["measured_account_funnel"][
            "stages"
        ]["follows"]["value"]
        == 100
    )
    with open_application(settings) as app:
        from socialdna.application import audience_service
        from socialdna.domain.memory import QuerySpec
        from socialdna.memory import hybrid

        assert hybrid.search(app, QuerySpec(text="Literal app CTA"))["hits"]
        with app.database.transaction() as connection:
            withdraw(
                connection,
                source_id=observed["source_id"],
                reason="Owner analytics permission revoked",
            )
            assert (
                not EvidenceResolver(connection)
                .resolve(EvidenceRef.model_validate(report["evidence"]))
                .eligible
            )
        assert frozen_path.read_bytes() == frozen
        assert hybrid.search(app, QuerySpec(text="Literal app CTA"))["hits"]
        plan = audience_service.redact(app, source_id=later["source_id"])
        audience_service.redact(
            app,
            source_id=later["source_id"],
            confirmation=plan["confirmation"],
            reason="Erase owned profile capture and dependent copies",
        )
        assert not frozen_path.exists()
        assert not hybrid.search(app, QuerySpec(text="Literal app CTA"))["hits"]
        with pytest.raises(ConfigurationError, match="erased"):
            service.import_into_application(app, profile_export([later_snapshot]))
