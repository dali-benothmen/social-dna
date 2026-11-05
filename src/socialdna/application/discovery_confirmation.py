"""Prespecified independent focal replication, not promotion from prediction accuracy."""

from typing import Any

from socialdna.application.bootstrap import Application
from socialdna.application.discovery_inputs import build
from socialdna.application.discovery_service import (
    _attempt,
    _bind,
    _register,
    assert_snapshot,
    show,
)
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.research import discovery
from socialdna.research.candidates import Candidate, ConfirmationSpec, DiscoverySpec
from socialdna.storage import research_repository as repository
from socialdna.storage.schema import metadata


def evaluate(
    rows: list[dict[str, Any]], candidate: Candidate, spec: ConfirmationSpec
) -> dict[str, Any]:
    try:
        pipeline = discovery.fit(rows, candidate, 0.0)
    except ConfigurationError as exc:
        return {"status": "insufficient_data", "reason": str(exc)}
    term = discovery.contrast(pipeline, rows)
    disposition = "insufficient_independent_clusters_or_uncertainty"
    if term["p_value"] is not None:
        effect = term["coefficients"][0]
        low, high = effect["raw_basis_ci_low"], effect["raw_basis_ci_high"]
        lower, upper = (low, high) if spec.direction == "positive" else (-high, -low)
        disposition = (
            "supports_prespecified_contrast"
            if lower > spec.minimum_absolute_effect
            else "contradicts_prespecified_direction"
            if upper < 0
            else "inconclusive"
        )
    return {
        "status": "evaluated",
        "contrast": term,
        "disposition": disposition,
        "pipeline": pipeline.manifest,
        "spec": spec.model_dump(mode="json"),
        "independent_cohort": True,
        "causal_or_mechanism_proof": False,
        "multiplicity": "one frozen contrast; repeated looks not error-controlled",
    }


def confirm(app: Application, spec: ConfirmationSpec) -> dict[str, Any]:
    original = show(app, spec.discovery)
    if spec.discovery.kind != "discovery_search" or "result" not in original:
        raise ConfigurationError("Confirmation requires an exact completed discovery result")
    selected = original["result"].get("selected")
    candidate = next(
        (
            Candidate.model_validate(c)
            for c in original["spec"]["candidates"]
            if c["key"] == selected
        ),
        None,
    )
    if candidate is None or candidate.alphas != (0.0,) or candidate.kind == "spline":
        raise ConfigurationError(
            "Focal replication requires fixed OLS main/interaction/quadratic; "
            "no tuning or reknotted splines"
        )
    for field in (
        "platform",
        "surface",
        "native_format",
        "language",
        "audience",
        "market",
        "objective",
        "traffic",
    ):
        if getattr(spec.scope, field) != original["spec"]["scope"][field]:
            raise ConfigurationError(
                "Confirmation cannot silently change the objective/source scope"
            )
    options = DiscoverySpec(
        key=spec.key,
        family_id=spec.family_id,
        parent_search=spec.discovery,
        input=spec.input,
        scope=spec.scope,
        as_of=spec.as_of,
        candidates=(candidate,),
        holdout_id=spec.holdout_id,
        max_fits=5,
    )
    snapshot = build(app, options)
    snapshot["confirmation_spec"] = spec.model_dump(mode="json")
    seen, unique = set(), []
    for row in snapshot["rows"]:
        identity = row.get("duplicate_group") or row["unit_id"]
        if identity not in seen:
            unique.append(row)
            seen.add(identity)
    snapshot["rows"] = unique
    split = {"train": [], "test": [r["unit_id"] for r in unique], "transfer": [], "purged": []}
    registration, provenance, info = _register(app, options, snapshot, split)
    try:
        result = _attempt(app, options)(
            candidate.key,
            "outer",
            0.0,
            None,
            [],
            split["test"],
            lambda: evaluate(unique, candidate, spec),
        )
        with app.database.transaction() as connection:
            assert_snapshot(connection, snapshot)
            ref = repository.save(
                connection,
                "discovery_search",
                spec.key,
                {
                    "registration": registration.model_dump(),
                    "spec": options.model_dump(mode="json"),
                    "result": result,
                    "claim_level": "independent_observational_contrast",
                    "summary": "Independent focal contrast; not causal or mechanism proof",
                },
                provenance,
                entities=(registration, spec.discovery),
            )
            _bind(connection, ref, spec.key, "result")
            connection.execute(
                metadata.tables["discovery_rounds"]
                .update()
                .where(metadata.tables["discovery_rounds"].c.id == spec.key)
                .values(status="completed", result_revision_id=ref.revision_id)
            )
            connection.execute(
                metadata.tables["test_attempts"]
                .update()
                .where(metadata.tables["test_attempts"].c.id == info["attempt_id"])
                .values(
                    status="completed",
                    result_json=canonical_json(
                        {"search": ref.model_dump(), "result_hash": hash_config(result)}
                    ),
                )
            )
            citation = repository.cite(connection, ref)
        return {"ref": ref.model_dump(), "evidence": citation.model_dump(), "result": result}
    except Exception:
        with app.database.transaction() as connection:
            for name, identity in (
                ("discovery_rounds", spec.key),
                ("test_attempts", info["attempt_id"]),
            ):
                table = metadata.tables[name]
                connection.execute(
                    table.update().where(table.c.id == identity).values(status="failed")
                )
        raise
