"""Durable bounded search lifecycle, shared test/holdout ledger and exact reproduction."""

import importlib.metadata
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, func, select

from socialdna.application.bootstrap import Application
from socialdna.application.discovery_inputs import build
from socialdna.application.evidence_service import EvidenceResolver
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.research import discovery
from socialdna.research.candidates import DiscoverySpec
from socialdna.storage import research_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def _versions() -> dict[str, str]:
    return {
        k: importlib.metadata.version(k) for k in ("numpy", "scipy", "scikit-learn", "statsmodels")
    }


def _members(row: dict[str, Any]) -> list[str]:
    keys = ["post:" + row["post_id"] if row["post_id"] else "unit:" + row["unit_id"]]
    if row.get("duplicate_group"):
        keys.append("sha256:" + row["duplicate_group"])
    # Account-period observation identity is insufficient: reimporting the same
    # measured event under another context key cannot create an untouched cohort.
    keys.extend("evidence:" + r["revision_id"] for r in row.get("evidence", []))
    if row.get("measurement_members"):
        keys.extend(row["measurement_members"])
    return keys


def assert_snapshot(connection: Connection, snapshot: dict[str, Any]) -> None:
    from socialdna.application.statistical_service import assert_design_inputs
    from socialdna.memory.documents import entity_active

    post_rows = [r for r in snapshot["rows"] if "source_ids" in r]
    if post_rows:
        assert_design_inputs(connection, post_rows)
    for raw in snapshot["entities"]:
        entity_active(connection, EntityRef.model_validate(raw))
    resolver = EvidenceResolver(connection)
    for raw in {r["revision_id"]: r for row in snapshot["rows"] for r in row["evidence"]}.values():
        resolver.resolve(EvidenceRef.model_validate(raw), purpose="new_claim")


def _bind(connection: Connection, ref: EntityRef, key: str, role: str) -> None:
    connection.execute(
        metadata.tables["discovery_bindings"]
        .insert()
        .values(revision_id=ref.revision_id, round_id=key, role=role)
    )


def _register(
    app: Application, spec: DiscoverySpec, snapshot: dict[str, Any], split: dict[str, Any]
) -> tuple[EntityRef, str, dict[str, Any]]:
    with app.database.transaction() as connection:
        assert_snapshot(connection, snapshot)
        rounds, table = metadata.tables["discovery_rounds"], metadata.tables["test_families"]
        if connection.scalar(select(rounds.c.id).where(rounds.c.id == spec.key)):
            raise ConfigurationError(
                "Search key already registered; show/reproduce it or declare a new parented round"
            )
        parent = spec.parent_search
        if parent:
            if parent.kind != "discovery_search":
                raise ConfigurationError("Parent must be an exact registered discovery search")
            show(app, parent, connection=connection)
        family_id = "discovery:" + spec.family_id
        manifest = {
            "candidates": [c.model_dump(mode="json") for c in spec.candidates],
            "input": spec.input.model_dump(mode="json"),
            "scope": spec.scope.model_dump(mode="json"),
            "split": spec.split,
            "transfer_niches": spec.transfer_niches,
            "stopping_rule": spec.stopping_rule,
            "max_fits": spec.max_fits,
        }
        previous = connection.scalar(select(table.c.spec_json).where(table.c.id == family_id))
        if previous and previous != canonical_json(manifest):
            raise ConfigurationError(
                "Search-family manifest is immutable; declare a disclosed new family"
            )
        if not previous:
            connection.execute(
                table.insert().values(
                    id=family_id, spec_json=canonical_json(manifest), created_at=utc_now()
                )
            )
        member_table = metadata.tables["discovery_members"]
        by_id = {r["unit_id"]: r for r in snapshot["rows"]}
        members: dict[str, str] = {}
        for role in ("purged", "train", "test", "transfer"):
            for identity in split[role]:
                for key in _members(by_id[identity]):
                    members[key] = role
        prior_rounds: list[str] = sorted(
            set(
                connection.scalars(
                    select(member_table.c.round_id).where(
                        member_table.c.member_key.in_(list(members)),
                        member_table.c.role != "purged",
                    )
                )
            )
        )
        if prior_rounds and parent is None:
            raise ConfigurationError(
                "Previously inspected search data requires explicit parent_search lineage"
            )
        held_keys = [k for k, role in members.items() if role in ("test", "transfer")]
        uses, old_members = metadata.tables["holdout_uses"], metadata.tables["holdout_members"]
        refusal = None
        if connection.scalar(select(uses.c.id).where(uses.c.id == spec.holdout_id)) or (
            held_keys
            and (
                connection.scalar(
                    select(member_table.c.member_key).where(
                        member_table.c.member_key.in_(held_keys), member_table.c.role != "purged"
                    )
                )
                or connection.scalar(
                    select(old_members.c.member_key).where(old_members.c.member_key.in_(held_keys))
                )
            )
        ):
            refusal = (
                "Consumed or previously trained-on holdout cannot support independent evaluation"
            )
        if held_keys and refusal is None:
            document: str
            for document in connection.scalars(
                select(metadata.tables["statistical_analyses"].c.result_json)
            ):
                prior = json.loads(document)
                prior_keys = {key for row in prior.get("posts", []) for key in _members(row)}
                if prior_keys.intersection(held_keys):
                    refusal = (
                        "Previously inspected statistical population is not an untouched holdout"
                    )
                    break
        attempt_id = new_id()
        connection.execute(
            metadata.tables["test_attempts"]
            .insert()
            .values(
                id=attempt_id,
                family_id=family_id,
                status="refused" if refusal else "started",
                result_json=canonical_json({"search_key": spec.key, "refusal": refusal}),
                created_at=utc_now(),
            )
        )
        provenance = repository.provenance(
            connection,
            "discovery:" + spec.key,
            {"spec_hash": hash_config(spec.model_dump(mode="json"))},
        )
        registration = repository.save(
            connection,
            "discovery_search",
            spec.key,
            {
                "spec": spec.model_dump(mode="json"),
                "snapshot": snapshot,
                "split": split,
                "libraries": _versions(),
                "method": discovery.METHOD,
                "prior_rounds": prior_rounds,
                "refusal": refusal,
                "claim_level": spec.claim_level,
            },
            provenance,
            entities=tuple(EntityRef.model_validate(r) for r in snapshot["entities"])
            + ((parent,) if parent else ()),
            evidence=tuple(
                {
                    r["revision_id"]: EvidenceRef.model_validate(r)
                    for row in snapshot["rows"]
                    for r in row["evidence"]
                }.values()
            ),
        )
        connection.execute(
            rounds.insert().values(
                id=spec.key,
                registration_revision_id=registration.revision_id,
                attempt_id=attempt_id,
                parent_revision_id=parent.revision_id if parent else None,
                status="refused" if refusal else "started",
                max_fits=spec.max_fits,
                created_at=utc_now(),
            )
        )
        _bind(connection, registration, spec.key, "registration")
        if members:
            connection.execute(
                member_table.insert(),
                [{"round_id": spec.key, "member_key": k, "role": r} for k, r in members.items()],
            )
        if not refusal and held_keys:
            connection.execute(
                uses.insert().values(
                    id=spec.holdout_id,
                    fingerprint=hash_config({"members": held_keys}),
                    attempt_id=attempt_id,
                    split_json=canonical_json(split),
                    consumed_at=utc_now(),
                )
            )
            # Existing R2 reservations see these real post/media members too.
            values = []
            for key in held_keys:
                if key.startswith("post:"):
                    values.append({"member_key": key, "post_id": key[5:], "media_sha256": None})
                elif key.startswith("sha256:"):
                    values.append({"member_key": key, "post_id": None, "media_sha256": key[7:]})
            if values:
                connection.execute(
                    old_members.insert(), [{**v, "holdout_id": spec.holdout_id} for v in values]
                )
        info = {"refusal": refusal, "prior_rounds": prior_rounds, "attempt_id": attempt_id}
    if refusal:
        raise ConfigurationError(refusal + "; refusal preserved under search " + spec.key)
    return registration, provenance, info


def _attempt(app: Application, spec: DiscoverySpec) -> Callable[..., dict[str, Any]]:
    def execute(
        candidate: str,
        phase: str,
        alpha: float | None,
        fold: int | None,
        train: list[str],
        test: list[str],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        identity = new_id()
        table = metadata.tables["discovery_attempts"]
        descriptor = {"alpha": alpha, "fold": fold, "train": train, "test": test}
        with app.database.transaction() as connection:
            count = int(
                connection.scalar(
                    select(func.count()).select_from(table).where(table.c.round_id == spec.key)
                )
                or 0
            )
            if count >= spec.max_fits:
                raise ConfigurationError("Fixed search fit budget exhausted")
            connection.execute(
                table.insert().values(
                    id=identity,
                    round_id=spec.key,
                    ordinal=count,
                    candidate_key=candidate,
                    phase=phase,
                    status="started",
                    result_json=canonical_json(descriptor),
                )
            )
        try:
            result = operation()
        except ConfigurationError as exc:
            result = {"status": "insufficient_data", "reason": str(exc)}
        except Exception as exc:
            with app.database.transaction() as connection:
                connection.execute(
                    table.update()
                    .where(table.c.id == identity)
                    .values(
                        status="failed",
                        result_json=canonical_json(
                            {**descriptor, "error_type": type(exc).__name__}
                        ),
                    )
                )
            raise
        with app.database.transaction() as connection:
            connection.execute(
                table.update()
                .where(table.c.id == identity)
                .values(
                    status="refused" if result["status"] == "insufficient_data" else "completed",
                    result_json=canonical_json({**descriptor, "result": result}),
                )
            )
        return result

    return execute


def discover(app: Application, spec: DiscoverySpec) -> dict[str, Any]:
    if spec.as_of > utc_now():
        raise ConfigurationError("Discovery knowledge cutoff cannot be in the future")
    snapshot = build(app, spec)
    split = discovery.partitions(snapshot["rows"], spec)
    registration, provenance, info = _register(app, spec, snapshot, split)
    try:
        result = discovery.run(snapshot["rows"], spec, split, _attempt(app, spec))
        with app.database.transaction() as connection:
            assert_snapshot(connection, snapshot)
            payload = {
                "registration": registration.model_dump(),
                "spec": spec.model_dump(mode="json"),
                "result": result,
                "scope_conditions": spec.scope.model_dump(mode="json"),
                "claim_level": spec.claim_level,
                "summary": "Bounded exploratory search; not independent confirmation",
            }
            ref = repository.save(
                connection,
                "discovery_search",
                spec.key,
                payload,
                provenance,
                entities=(registration,),
            )
            _bind(connection, ref, spec.key, "result")
            connection.execute(
                metadata.tables["discovery_rounds"]
                .update()
                .where(metadata.tables["discovery_rounds"].c.id == spec.key)
                .values(status="completed", result_revision_id=ref.revision_id)
            )
            patterns = []
            if result["selected"]:
                candidate = next(c for c in spec.candidates if c.key == result["selected"])
                pattern = repository.save(
                    connection,
                    "creative_pattern",
                    spec.key + ":" + candidate.key,
                    {
                        "spec": candidate.model_dump(mode="json"),
                        "search": ref.model_dump(),
                        "scope_conditions": spec.scope.model_dump(mode="json"),
                        "constituents": [
                            {"role": "driver", "feature": k} for k in candidate.features
                        ]
                        + [{"role": "adjuster", "feature": k} for k in candidate.adjusters],
                        "claim_level": spec.claim_level,
                        "summary": "Exploratory candidate proposal: " + candidate.prediction,
                        "status": "not_confirmed",
                    },
                    provenance,
                    entities=(ref,),
                )
                _bind(connection, pattern, spec.key, "pattern")
                patterns.append(
                    {
                        "ref": pattern.model_dump(),
                        "evidence": repository.cite(connection, pattern).model_dump(),
                    }
                )
            citation = repository.cite(connection, ref)
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
        return {
            "ref": ref.model_dump(),
            "evidence": citation.model_dump(),
            "patterns": patterns,
            "result": result,
            "split": split,
            "excluded": snapshot["excluded"],
            "ledger": info,
        }
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


def show(
    app: Application, ref: EntityRef, *, connection: Connection | None = None
) -> dict[str, Any]:
    if connection is None:
        with app.database.transaction() as opened:
            return show(app, ref, connection=opened)
    EvidenceResolver(connection).resolve(repository.cite(connection, ref), purpose="new_claim")
    from socialdna.memory.documents import current_revision

    payload = dict(json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]))
    return {
        **payload,
        "ref": ref.model_dump(),
        "operational_freshness": "current"
        if current_revision(connection, ref)
        else "stale_frozen_context",
    }


def reproduce(app: Application, ref: EntityRef) -> dict[str, Any]:
    payload = show(app, ref)
    if ref.kind != "discovery_search" or "registration" not in payload:
        raise ConfigurationError("Reproduction needs an exact completed discovery result")
    registration = EntityRef.model_validate(payload["registration"])
    with app.database.transaction() as connection:
        frozen = json.loads(EvidenceRepository(connection).entity(registration)["payload_json"])
        assert_snapshot(connection, frozen["snapshot"])
    if frozen["libraries"] != _versions() or frozen["method"] != discovery.METHOD:
        raise ConfigurationError(
            "Reproduction requires the recorded method and numerical libraries"
        )

    def attempt(
        _candidate: str,
        _phase: str,
        _alpha: float | None,
        _fold: int | None,
        _train: list[str],
        _test: list[str],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            return operation()
        except ConfigurationError as exc:
            return {"status": "insufficient_data", "reason": str(exc)}

    if "confirmation_spec" in frozen["snapshot"]:
        from socialdna.application.discovery_confirmation import evaluate
        from socialdna.research.candidates import Candidate, ConfirmationSpec

        computed = evaluate(
            frozen["snapshot"]["rows"],
            Candidate.model_validate(frozen["spec"]["candidates"][0]),
            ConfirmationSpec.model_validate(frozen["snapshot"]["confirmation_spec"]),
        )
    else:
        computed = discovery.run(
            frozen["snapshot"]["rows"],
            DiscoverySpec.model_validate(frozen["spec"]),
            frozen["split"],
            attempt,
        )
    if canonical_json(computed) != canonical_json(payload["result"]):
        raise StorageIntegrityError("Frozen discovery reproduction differs")
    return {
        "reproduced": True,
        "ref": ref.model_dump(),
        "result": computed,
        "holdout_consumed_again": False,
    }
