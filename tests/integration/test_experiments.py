"""Real prospective registration and authorized source-result pipeline on controlled data."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from test_behavioral_analysis import export

from socialdna.application import behavioral_service
from socialdna.application import experiment_service as service
from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import EvidenceResolver, withdraw
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.core.time import format_utc
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.research.experiments import ExperimentResults, ExperimentSpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def clock(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    moment = ["2026-08-01T00:00:00.000000Z"]

    def now() -> str:
        return moment[0]

    for module in list(sys.modules.values()):
        if (
            module
            and getattr(module, "__name__", "").startswith("socialdna")
            and hasattr(module, "utc_now")
        ):
            monkeypatch.setattr(module, "utc_now", now)
    return moment


def accounts(path: Path, blocks: int, *, posts: bool = False) -> None:
    records: list[dict[str, Any]] = []
    for i in range(blocks):
        records.append(
            {
                "record_type": "account",
                "platform": "demo",
                "external_id": f"c{i}",
                "creator_key": f"c{i}",
                "niche": "cooking",
            }
        )
        if posts:
            for j in range(2):
                records.append(
                    {
                        "record_type": "post",
                        "platform": "demo",
                        "external_id": f"p{i}-{j}",
                        "account_external_id": f"c{i}",
                        "published_at": f"2026-08-{5 + j:02}T00:00:00Z",
                        "caption": "Controlled original cooking variant",
                    }
                )
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "dataset_id": "experiment-accounts" if not posts else "experiment-posts",
                    "source_uri": "urn:owned:experiment",
                    "permission_basis": "creator_owned_export",
                },
                "records": records,
            }
        )
    )


def setup_plan(
    settings: Settings,
    path: Path,
    *,
    blocks: int = 20,
    method: str = "engine_block_randomized",
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accounts(path, blocks)
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        definition = behavioral_service.import_into_application(
            app,
            export(
                [
                    {
                        "record_type": "behavioral_definition",
                        "key": "demo.experiment_views.v1",
                        "platform": "demo",
                        "subject_type": "post",
                        "meaning": "other",
                        "semantics": "count",
                        "unit": "plays",
                        "domain": "nonnegative",
                        "measurement": "period",
                        "population_basis": "plays",
                        "replay_policy": "includes_replays",
                        "source_definition_uri": "urn:owned:period-counter",
                        "numerator_definition": "Source full-period plays per assigned post",
                        "description": "Controlled software fixture, not real platform performance",
                    }
                ]
            ),
        )["records"][0]["ref"]
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            roster = []
            for i in range(blocks):
                account = repo.latest("account", stable_id("account", "demo", f"c{i}"))
                assert account
                for j in range(2):
                    roster.append(
                        {
                            "key": f"p{i}-{j}",
                            "account": account.model_dump(),
                            "block": f"creator-{i}",
                            "starts_at": f"2026-08-{5 + j:02}T00:00:00Z",
                            **(
                                {"variant": ("control", "treatment")[j]}
                                if method != "engine_block_randomized"
                                else {}
                            ),
                        }
                    )
        spec = ExperimentSpec.model_validate(
            {
                "key": "original-cooking",
                "domain": "production",
                "assignment_unit": "post",
                "assignment_method": method,
                "scope": {
                    "platform": "demo",
                    "surface": "aggregate",
                    "native_format": "video",
                    "language": "en",
                    "market": "GB",
                    "audience": "Controlled authorized cohort",
                    "niches": ["cooking"],
                    "objective": "aggregate_attention",
                    "traffic": "unknown",
                    "period_start": "2026-08-01T00:00:00Z",
                    "period_end": "2026-09-01T00:00:00Z",
                    "basis": "Source-attested controlled fixture frame",
                },
                "variants": [
                    {"key": "control", "change": "Show the preparation before the plated result"},
                    {
                        "key": "treatment",
                        "change": "Show a short plated-result preview before preparation",
                    },
                ],
                "units": roster,
                "outcomes": [
                    {
                        "key": "plays",
                        "definition": definition,
                        "role": "primary",
                        "direction": "positive",
                        "minimum_meaningful_difference": 5,
                        "window_seconds": 86400,
                    }
                ],
                "permutation_resamples": 999,
                "precision_rationale": "Controlled recovery test, not a real power calculation",
                "held_constant": ["Recipe, duration, captions and source window"],
                "interference_plan": "Source-reviewed independent creator blocks",
                "authority": "Creator-authorized controlled fixture",
                "ethics_and_permissions": "No viewers recruited or private identities collected",
                **(feedback or {}),
            }
        )
        registered = service.register(app, spec)
        assert service.register(app, spec) == registered
        return {"spec": spec, "registered": registered, "definition": definition, "blocks": blocks}


def supplied_results(
    settings: Settings, path: Path, library: dict[str, Any], moment: list[str]
) -> ExperimentResults:
    moment[0] = "2026-08-09T00:00:00.000000Z"
    accounts(path, library["blocks"], posts=True)
    assert import_dataset(settings, path, "json")["valid"]
    with open_application(settings) as app:
        with app.database.transaction() as connection:
            repo = EvidenceRepository(connection)
            refs = {
                u.key: repo.latest("post", stable_id("post", "demo", u.key))
                for u in library["spec"].units
            }
        cohorts = []
        for i in range(library["blocks"]):
            cohorts.append(
                {
                    "record_type": "audience_cohort",
                    "key": f"creator-{i}",
                    "account": library["spec"].units[2 * i].account.model_dump(),
                    "known": True,
                    "eligibility": "Source-reported eligible plays in the assigned post window",
                    "aggregation_limitations": "Post aggregates; independent people not inferred",
                }
            )
        captured = behavioral_service.import_into_application(app, export(cohorts))["records"]
        measured = []
        for i, unit in enumerate(library["spec"].units):
            arm = library["registered"]["content"]["assignments"][unit.key]
            value = 100 + (i // 2) * 5 + (10 + (i // 2) % 3 if arm == "treatment" else 0)
            measured.append(
                {
                    "record_type": "metric_measurement",
                    "key": unit.key,
                    "subject": refs[unit.key].model_dump(),
                    "definition": library["definition"],
                    "cohort": captured[i // 2]["ref"],
                    "clock": {
                        "window_start": unit.starts_at,
                        "window_end": format_utc(
                            datetime.fromisoformat(unit.starts_at) + timedelta(days=1)
                        ),
                        "data_cutoff": format_utc(
                            datetime.fromisoformat(unit.starts_at) + timedelta(days=1)
                        ),
                        "collected_at": "2026-08-08T00:00:00Z",
                    },
                    "measurement": {"value": value},
                }
            )
        outcomes = behavioral_service.import_into_application(app, export(measured))["records"]
        raw = {
            "key": "authorized-final",
            "registration": library["registered"]["ref"],
            "source_uri": "urn:owned:experiment-results",
            "permission_basis": "creator_authorized_results",
            "collected_at": moment[0],
            "review": {
                "reviewer": "Controlled source auditor",
                "basis": "Actual allocation/measurement export review; fixture attestations",
                "allocation_intact": True,
                "no_spillover": True,
                "no_carryover": True,
                "no_concurrent_changes": True,
                "no_interim_looks": True,
                "complete_roster": True,
                "evidence": [outcomes[0]["evidence"]],
            },
            "units": [
                {
                    "unit_key": u.key,
                    "subject": refs[u.key].model_dump(),
                    "implemented_variant": library["registered"]["content"]["assignments"][u.key],
                    "outcomes": {"plays": outcomes[i]["ref"]},
                }
                for i, u in enumerate(library["spec"].units)
            ],
        }
        return ExperimentResults.model_validate(raw)


def test_registered_randomization_real_outcomes_reproduction_and_withdrawal(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(settings, tmp_path / "owned.json")
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    with open_application(settings) as app:
        imported = service.import_results(app, data)
        assert service.import_results(app, data) == imported
        analyzed = service.analyze(app, EntityRef.model_validate(imported["ref"]))
        result = analyzed["content"]["analysis"]
        assert result["outcomes"][0]["disposition"] == "supported_in_scope"
        assert result["outcomes"][0]["estimate"] == pytest.approx(10.95)
        assert result["mechanism_status"].startswith("not_identified")
        assert service.analyze(app, EntityRef.model_validate(imported["ref"])) == analyzed
        analysis = EntityRef.model_validate(analyzed["ref"])
        assert service.show(app, analysis, reproduce=True)["reproduced"]
        with app.database.transaction() as connection:
            citation = EvidenceRef.model_validate(analyzed["evidence"])
            assert EvidenceResolver(connection).resolve(citation, purpose="new_claim").eligible
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["test_attempts"])
                )
                == 1
            )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(settings.data_dir),
            "--format",
            "json",
            "experiment",
            "show",
            analysis.id,
            "--kind",
            analysis.kind,
            "--revision",
            analysis.revision_id,
            "--reproduce",
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["data"]["reproduced"]
    with open_application(settings) as app:
        assert service.show(app, analysis, reproduce=True)["reproduced"]
        with app.database.transaction() as connection:
            row = EvidenceRepository(connection).entity(EntityRef.model_validate(imported["ref"]))
            withdraw(connection, source_id=row["source_id"], reason="Controlled withdrawal")
            assert not EvidenceResolver(connection).resolve(citation).eligible
        with pytest.raises(ConfigurationError, match="Ineligible"):
            service.show(app, analysis)


@pytest.mark.parametrize(
    "failure",
    [
        "sequential",
        "attrition",
        "unplanned_look",
        "fidelity",
        "small_clusters",
        "spillover",
        "deviations",
        "lag",
    ],
)
def test_execution_failures_are_retained_without_causal_promotion(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(
        settings,
        tmp_path / "owned.json",
        blocks=3 if failure == "small_clusters" else 20,
        method="nonrandomized" if failure == "sequential" else "engine_block_randomized",
    )
    if failure == "lag":
        with open_application(settings) as app:
            amended = library["spec"].model_copy(
                update={
                    "version": 2,
                    "predecessor": EntityRef.model_validate(library["registered"]["ref"]),
                    "outcomes": (
                        library["spec"].outcomes[0].model_copy(update={"lag_seconds": 604800}),
                    ),
                }
            )
            library["spec"] = amended
            library["registered"] = service.register(app, amended)
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    if failure == "attrition":
        data = data.model_copy(update={"units": data.units[:-1]})
    elif failure == "unplanned_look":
        data = data.model_copy(
            update={"review": data.review.model_copy(update={"no_interim_looks": False})}
        )
    elif failure == "fidelity":
        data = data.model_copy(
            update={
                "units": (
                    data.units[0].model_copy(update={"implemented_variant": None}),
                    *data.units[1:],
                )
            }
        )
    elif failure == "spillover":
        data = data.model_copy(
            update={"review": data.review.model_copy(update={"no_spillover": None})}
        )
    elif failure == "deviations":
        data = data.model_copy(update={"deviations": ("Unplanned concurrent packaging changes",)})
    with open_application(settings) as app:
        imported = service.import_results(app, data)
        report = service.analyze(app, EntityRef.model_validate(imported["ref"]))["content"][
            "analysis"
        ]
        assert report["claim_level"] == "descriptive_observational"
        assert report["outcomes"][0]["p_value"] is None
        assert report["outcomes"][0]["disposition"] == "insufficient_data"


def test_wrong_subject_duplicate_metric_and_posthoc_changes_are_refused(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(settings, tmp_path / "owned.json", blocks=3)
    with open_application(settings) as app:
        amended = library["spec"].model_copy(
            update={
                "version": 2,
                "predecessor": EntityRef.model_validate(library["registered"]["ref"]),
                "seed": 99,
            }
        )
        latest = service.register(app, amended)
        assert latest["ref"] != library["registered"]["ref"]
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    with open_application(settings) as app:
        with pytest.raises(ConfigurationError, match="Amendments"):
            service.register(app, amended.model_copy(update={"seed": 1}))
        wrong = data.units[0].model_copy(update={"subject": data.units[1].subject})
        with pytest.raises(ConfigurationError, match="publication slot|subject mismatch"):
            service.import_results(app, data.model_copy(update={"units": (wrong, *data.units[1:])}))
        extra = data.units[0].model_copy(
            update={
                "outcomes": {
                    **data.units[0].outcomes,
                    "unregistered": data.units[0].outcomes["plays"],
                }
            }
        )
        with pytest.raises(ConfigurationError, match="Unregistered"):
            service.import_results(app, data.model_copy(update={"units": (extra, *data.units[1:])}))
