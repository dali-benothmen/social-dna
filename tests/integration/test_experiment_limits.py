"""Actual account-period outcomes and durable refusals, not fictitious randomization."""

from pathlib import Path

import pytest
from sqlalchemy import select
from test_behavioral_analysis import export
from test_experiments import clock, setup_plan, supplied_results
from test_profile_conversion import owner_metrics, profile_export

from socialdna.application import behavioral_service, profile_service
from socialdna.application import experiment_service as service
from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EntityRef
from socialdna.research.experiments import ExperimentResults, ExperimentSpec
from socialdna.storage.schema import metadata


def test_actual_profile_pre_post_follows_are_not_profile_caused_growth(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(settings, tmp_path / "owned.json", blocks=1)
    account = library["spec"].units[0].account.model_dump()
    with open_application(settings) as app:
        actual = owner_metrics(app, account)
        mapped = profile_service.import_into_application(
            app,
            profile_export(
                [
                    {
                        "record_type": "funnel_definition",
                        "key": "source-events",
                        "account": account,
                        "clock": {"captured_at": "2026-02-02T00:00:00Z"},
                        "reviewer": "Source reviewer",
                        "source_report": "Actual owner export",
                        "join_basis": "source_reported_nested_counts",
                        "deduplication": "source_unique_per_window",
                        "linkage_limitations": "Aggregate events, not an intervention estimate",
                        "bindings": [
                            {
                                "definition": actual["definitions"][2],
                                "signal": "follows",
                                "uniqueness": "unique_accounts",
                                "source_event_code": "new_follow",
                                "source_definition_excerpt": actual["definition_specs"][2][
                                    "numerator_definition"
                                ],
                            }
                        ],
                    }
                ]
            ),
        )
        assert mapped["records"]
        base = library["spec"].model_dump(mode="json")
        base.update(
            key="profile-history",
            domain="profile",
            assignment_unit="account_period",
            assignment_method="nonrandomized",
        )
        base["scope"].update(objective="conversion", period_start="2026-01-01T00:00:00Z")
        for i, unit in enumerate(base["units"]):
            unit.update(
                starts_at=f"2026-0{i + 1}-01T00:00:00Z", variant=("control", "treatment")[i]
            )
        base["outcomes"][0].update(definition=actual["definitions"][2], window_seconds=31 * 86400)
        registered = service.register(app, ExperimentSpec.model_validate(base))
        second = actual["source_records"][2].copy()
        second.update(
            key="later-follows",
            measurement={"value": 200},
            clock={
                "window_start": "2026-02-01T00:00:00Z",
                "window_end": "2026-03-04T00:00:00Z",
                "data_cutoff": "2026-03-04T00:00:00Z",
                "collected_at": "2026-03-05T00:00:00Z",
            },
        )
        later = behavioral_service.import_into_application(app, export([second]))["records"][0]
        results = ExperimentResults.model_validate(
            {
                "key": "profile-actual",
                "registration": registered["ref"],
                "source_uri": "urn:owner:profile-periods",
                "permission_basis": "creator_authorized_results",
                "collected_at": moment[0],
                "review": {
                    "reviewer": "Source reviewer",
                    "basis": "Actual exported account-period counters",
                    "allocation_intact": True,
                    "no_spillover": True,
                    "no_carryover": True,
                    "no_concurrent_changes": True,
                    "no_interim_looks": True,
                    "complete_roster": True,
                    "evidence": [later["evidence"]],
                },
                "units": [
                    {
                        "unit_key": u["key"],
                        "subject": account,
                        "implemented_variant": u["variant"],
                        "outcomes": {"plays": ref},
                    }
                    for u, ref in zip(
                        base["units"], [actual["measurements"][2], later["ref"]], strict=True
                    )
                ],
            }
        )
        imported = service.import_results(app, results)
        report = service.analyze(app, EntityRef.model_validate(imported["ref"]))["content"][
            "analysis"
        ]
        assert report["claim_level"] == "descriptive_observational"
        assert report["outcomes"][0]["estimate"] == 100
        assert report["outcomes"][0]["p_value"] is None
        assert any("carryover" in reason for reason in report["threats"])
        assert any("exact-version exposed" in reason for reason in report["threats"])


def test_failed_fit_is_durable_and_source_window_cannot_be_redefined(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(settings, tmp_path / "owned.json", blocks=3)
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    with open_application(settings) as app:
        imported = service.import_results(app, data)
        real_engine = service.engine.analyze

        def fail(*args: object) -> None:
            raise RuntimeError("Controlled interrupted numerical fit")

        monkeypatch.setattr(service.engine, "analyze", fail)
        with pytest.raises(RuntimeError, match="Controlled"):
            service.analyze(app, EntityRef.model_validate(imported["ref"]))
        monkeypatch.setattr(service.engine, "analyze", real_engine)
        assert service.analyze(app, EntityRef.model_validate(imported["ref"]))
        with app.database.transaction() as connection:
            statuses = list(connection.scalars(select(metadata.tables["test_attempts"].c.status)))
        assert sorted(statuses) == ["completed", "failed"]
        corrected = data.model_copy(
            update={
                "supersedes": EntityRef.model_validate(imported["ref"]),
                "correction_reason": "Wrong source window",
            }
        )
        raw = library["spec"].model_dump(mode="json")
        raw["outcomes"][0]["window_offset_seconds"] = 1
        with app.database.transaction() as connection:
            # Exercise the real snapshot join using a changed plan; do not write forged revisions.
            with pytest.raises(ConfigurationError, match="registered source window"):
                service._snapshot(
                    connection, {**library["registered"]["content"], "spec": raw}, corrected
                )
