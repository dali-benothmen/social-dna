"""Actual experiment feedback, preserved contradiction history and terminal erasure."""

from pathlib import Path

import pytest
import test_psychological_research
from sqlalchemy import func, select
from test_behavioral_analysis import export
from test_experiments import clock, setup_plan, supplied_results
from test_psychological_research import evaluation
from test_psychological_research import library as prior_library

from socialdna.application import (
    audience_service,
    behavioral_service,
    investigation_service,
    recommendation_service,
    reevaluation_service,
)
from socialdna.application import experiment_service as service
from socialdna.application.bootstrap import open_application
from socialdna.application.evidence_service import ClaimValidator
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.memory import documents
from socialdna.research.recommendations import RecommendationSpec
from socialdna.storage import behavioral_repository as behavior
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def test_feedback_preserves_registered_rivals_and_original_assessment(
    settings: Settings, tmp_path: Path, account_export: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    monkeypatch.setattr(test_psychological_research, "utc_now", lambda: moment[0])
    prior_data = prior_library.__wrapped__(settings, account_export, tmp_path)
    with open_application(settings) as app:
        prior = investigation_service.evaluate(app, evaluation(prior_data))
        prior_ref = EntityRef.model_validate(prior["assessment"])
        with app.database.transaction() as connection:
            original = EvidenceRepository(connection).entity(prior_ref)["payload_json"]
    feedback = {
        "prior_assessment": prior_ref.model_dump(),
        "predictions": [
            {
                "hypothesis": h,
                "outcome_key": "plays",
                "direction": "negative" if i == 1 else "positive",
                "rationale": "Predeclared creative contrast; "
                "a mediator requires additional identification",
            }
            for i, h in enumerate(prior_data["registered"]["hypotheses"])
        ],
    }
    library = setup_plan(settings, tmp_path / "owned.json", feedback=feedback)
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    with open_application(settings) as app:
        imported = service.import_results(app, data)
        analyzed = service.analyze(app, EntityRef.model_validate(imported["ref"]))
        assert analyzed["assessment"]
        judgments = analyzed["assessment"]["content"]["judgments"]
        assert [j["treatment_prediction_disposition"] for j in judgments] == [
            "supported_in_scope",
            "contradicted_in_scope",
            "supported_in_scope",
        ]
        assert all(j["mechanism_status"] == "not_identified" for j in judgments)
        assert service.analyze(app, EntityRef.model_validate(imported["ref"])) == analyzed
        history = reevaluation_service.history(app, prior_data["registered"]["hypotheses"][0]["id"])
        assert history["experiment_assessments"][0]["judgments"] == judgments
        with app.database.transaction() as connection:
            assert EvidenceRepository(connection).entity(prior_ref)["payload_json"] == original
            validator = ClaimValidator(connection)
            citation = EvidenceRef.model_validate(analyzed["evidence"])
            assert validator.validate_experiment(analyzed["content"]["claim_level"], (citation,))
            with pytest.raises(ConfigurationError, match="mediator|mechanism"):
                validator.validate_experiment("mechanism_proof", (citation,))
            indexed = documents.build(
                connection, "evidence", analyzed["assessment"]["evidence"]["revision_id"]
            )
            assert indexed and "contradicted_in_scope" in indexed["text"]
        specification = RecommendationSpec.model_validate(
            {
                "key": "cooking-next-test",
                "domain": "production",
                "scope": library["spec"].scope.model_dump(mode="json"),
                "actions": [
                    {
                        "target": "pacing",
                        "change": "Try a restrained final-plate insert followed immediately "
                        "by the preparation demonstration.",
                        "hold_constant": "Keep recipe, audio and caption matched",
                        "measure": "Actual permitted period plays",
                        "falsifier": "A suitable independently registered comparison "
                        "with no useful gain",
                    }
                ],
                "evidence": [
                    {
                        "evidence": analyzed["evidence"],
                        "role": "support",
                        "applicability": "direct",
                        "rationale": "Actual scoped assignment estimate, not mediator proof",
                    },
                    {
                        "evidence": analyzed["assessment"]["evidence"],
                        "role": "counterevidence",
                        "applicability": "direct",
                        "rationale": "Registered contrary rival prediction "
                        "and unresolved mechanisms",
                    },
                ],
                "counterevidence_search": "Retain every registered rival "
                "and the contradictory directional prediction",
                "uncertainty": ["A new variation and psychological mediation remain untested"],
                "next_test": "Register a separate exposure/measurement design "
                "before any authorized execution",
            }
        )
        recommendation = recommendation_service.create(app, specification)
        assert recommendation["content"]["expected_lift"] is None
        assert recommendation["content"]["sources"][1]["role"] == "counterevidence"


def test_corrections_preserve_bytes_and_contradictions_before_erasure(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moment = clock(monkeypatch)
    library = setup_plan(settings, tmp_path / "owned.json")
    data = supplied_results(settings, tmp_path / "owned.json", library, moment)
    with open_application(settings) as app:
        original = service.import_results(app, data)
        first = service.analyze(app, EntityRef.model_validate(original["ref"]))
        first_ref = EntityRef.model_validate(first["ref"])
        with app.database.transaction() as connection:
            original_bytes = EvidenceRepository(connection).entity(first_ref)["payload_json"]
        corrections = []
        with app.database.transaction() as connection:
            for unit in data.units:
                if unit.implemented_variant == "treatment":
                    raw = behavior.read(connection, unit.outcomes["plays"])["spec"]
                    raw["measurement"]["value"] -= 20
                    corrections.append(raw)
        moment[0] = "2026-08-10T00:00:00.000000Z"
        imported_metrics = behavioral_service.import_into_application(app, export(corrections))[
            "records"
        ]
        with app.database.transaction() as connection:
            assert not documents.current_revision(connection, first_ref)
        assert (
            service.show(app, first_ref, reproduce=True)["operational_freshness"]
            == "stale_frozen_context"
        )
        updates = {raw["key"]: imported_metrics[i]["ref"] for i, raw in enumerate(corrections)}
        revised = data.model_copy(
            update={
                "supersedes": EntityRef.model_validate(original["ref"]),
                "correction_reason": "Source corrected the controlled treatment period counters",
                "collected_at": moment[0],
                "review": data.review.model_copy(
                    update={
                        "evidence": (EvidenceRef.model_validate(imported_metrics[0]["evidence"]),)
                    }
                ),
                "units": tuple(
                    u.model_copy(
                        update={
                            "outcomes": {"plays": EntityRef.model_validate(updates[u.unit_key])}
                        }
                    )
                    if u.unit_key in updates
                    else u
                    for u in data.units
                ),
            }
        )
        second_results = service.import_results(app, revised)
        second = service.analyze(app, EntityRef.model_validate(second_results["ref"]))
        assert (
            second["content"]["analysis"]["outcomes"][0]["disposition"] == "contradicted_in_scope"
        )
        assert second["content"]["independent_replication"] is False
        assert service.show(app, first_ref, reproduce=True)["reproduced"]
        with app.database.transaction() as connection:
            assert (
                EvidenceRepository(connection).entity(first_ref)["payload_json"] == original_bytes
            )
            assert not documents.current_revision(connection, first_ref)
            source = EvidenceRepository(connection).entity(
                EntityRef.model_validate(original["ref"])
            )["source_id"]
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["test_attempts"])
                )
                == 2
            )
        preview = audience_service.redact(app, source_id=source)
        assert preview["counts"]["entity_revision"] >= 4
        audience_service.redact(
            app,
            source_id=source,
            confirmation=preview["confirmation"],
            reason="Controlled experiment source erasure",
        )
        with pytest.raises(ConfigurationError, match="erased|Ineligible"):
            service.show(app, first_ref)
