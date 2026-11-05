"""Canonical SQL adapters, not retrieval samples or arbitrary predictor/value uploads."""

import json
import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.application.performance_service import build_design_population
from socialdna.application.statistical_service import assert_design_inputs
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef
from socialdna.research.candidates import DiscoverySpec, DistributionInput, FunnelsInput, PostsInput
from socialdna.storage import behavioral_repository as behavioral
from socialdna.storage import context_repository as context
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

PUBLICATION_FEATURES = {
    "publication.hour_sin",
    "publication.hour_cos",
    "publication.weekday_sin",
    "publication.weekday_cos",
    "publication.title_length",
    "publication.hashtag_count",
    "publication.cadence",
}
PROFILE_FEATURES = {
    "profile.bio_length",
    "profile.links_count",
    "profile.pins_count",
    "profile.pillar_count",
}
RECIPE = {
    "pin": "discovery-context-1",
    "missing": "unknown_not_zero",
    "local_clock": "supplied IANA zone and original timestamp, circular 24h/7d",
    "metadata": "source-attested interval covering original publication only",
    "cadence": "complete including deleted/omitted inventory, count/elapsed UTC days",
    "profile": "literal fields with source-attested exact-version exposure; no rubric score",
    "distribution": "actual R5 early value and non-overlapping later count",
}


def _account(connection: Connection, ref: EntityRef) -> dict[str, Any]:
    return dict(json.loads(EvidenceRepository(connection).entity(ref)["payload_json"]))


def _unit(
    connection: Connection,
    account: EntityRef,
    identity: str,
    when: str,
    end: str,
    available: str,
    features: dict[str, Any],
    value: float,
    evidence: list[dict[str, Any]],
    *,
    post_id: str | None = None,
) -> dict[str, Any]:
    data = _account(connection, account)
    return {
        "unit_id": identity,
        "post_id": post_id,
        "account_id": account.id,
        "creator_id": data.get("creator_id") or account.id,
        "creator_identity": "supplied" if data.get("creator_id") else "account_proxy",
        "platform": data["platform"],
        "niche": data.get("niche"),
        "published_at": when,
        "outcome_end": end,
        "outcome_available_at": available,
        "features": features,
        "outcome": value,
        "evidence": evidence,
        "duplicate_group": None,
        "forecast": False,
    }


def _publications(
    connection: Connection,
    rows: list[dict[str, Any]],
    spec: DiscoverySpec,
    source: PostsInput,
    inputs: list[EntityRef],
) -> None:
    by_post = {}
    for ref in source.publications:
        if ref.kind != "publication_context":
            raise ConfigurationError("Publishing features require actual publication contexts")
        payload = context.read(connection, ref, spec.as_of)
        post = payload["post"]["id"]
        if post in by_post:
            raise ConfigurationError("One exact historical publication context per post")
        by_post[post] = (ref, payload)
        inputs.append(ref)
    windows = [context.read(connection, ref, spec.as_of) for ref in source.windows]
    if any(ref.kind != "publishing_window" for ref in source.windows):
        raise ConfigurationError("Cadence needs actual publishing-window revisions")
    inputs.extend(source.windows)
    for row in rows:
        row["features"].update(dict.fromkeys(PUBLICATION_FEATURES))
        pair = by_post.get(row["post_id"])
        if pair:
            ref, payload = pair
            data = payload["spec"]
            if payload["post"] != row["post_ref"]:
                raise ConfigurationError("Publication metadata must pin the selected post revision")
            if (
                any(
                    data[k] != getattr(spec.scope, k)
                    for k in ("language", "native_format", "audience")
                )
                or data["niche"] != row["niche"]
            ):
                raise ConfigurationError(
                    "Publication language/format/audience/niche scope mismatch"
                )
            literal = datetime.fromisoformat(data["published_original"])
            if data["timezone"]:
                local = literal.astimezone(ZoneInfo(data["timezone"]))
                hour = local.hour + local.minute / 60 + local.second / 3600
                for prefix, value, period in (("hour", hour, 24), ("weekday", local.weekday(), 7)):
                    row["features"][f"publication.{prefix}_sin"] = math.sin(
                        2 * math.pi * value / period
                    )
                    row["features"][f"publication.{prefix}_cos"] = math.cos(
                        2 * math.pi * value / period
                    )
            clock = data["clock"]
            if (
                clock["validity_basis"] == "source_attested"
                and clock["valid_from"] <= row["published_at"]
                and (not clock["valid_until"] or row["published_at"] < clock["valid_until"])
            ):
                title = data["title"]
                if title["state"] in ("present", "empty"):
                    row["features"]["publication.title_length"] = float(len(title["value"]))
                if data["hashtags"] is not None:
                    row["features"]["publication.hashtag_count"] = float(len(data["hashtags"]))
            row["evidence"].append(context.cite(connection, ref).model_dump())
            if source.analysis.feature_policy == "historical_prediction" and (
                EvidenceRepository(connection).entity(ref)["available_at"] > row["published_at"]
            ):
                row["features"].update(dict.fromkeys(PUBLICATION_FEATURES))
        matching = [
            w
            for w in windows
            if w["account"]["id"] == row["account_id"]
            and row["post_id"] in {p["id"] for p in w["spec"]["posts"]}
        ]
        if len(matching) > 1:
            raise ConfigurationError("Overlapping cadence inventories for the same post")
        if matching:
            window = matching[0]["spec"]
            if (
                window["complete"]
                and window["includes_deleted_and_omitted"]
                and not row["forecast"]
            ):
                days = (
                    datetime.fromisoformat(window["window_end"])
                    - datetime.fromisoformat(window["window_start"])
                ).total_seconds() / 86400
                row["features"]["publication.cadence"] = len(window["posts"]) / days


def build(app: Application, spec: DiscoverySpec) -> dict[str, Any]:
    with app.database.transaction() as connection:
        recipes = metadata.tables["feature_recipes"]
        connection.execute(
            insert(recipes)
            .values(
                id=RECIPE["pin"],
                version="1.0",
                spec_json=canonical_json(RECIPE),
                available_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        if connection.scalar(
            select(recipes.c.spec_json).where(recipes.c.id == RECIPE["pin"])
        ) != canonical_json(RECIPE):
            raise StorageIntegrityError("Discovery context recipe changed without a new pin")
    if isinstance(spec.input, PostsInput):
        rows, definitions, _history = build_design_population(app, spec.input.analysis)
        inputs: list[EntityRef] = []
        with app.database.transaction() as connection:
            assert_design_inputs(connection, rows)
            for row in rows:
                row.update(
                    unit_id=row["post_id"],
                    evidence=[],
                    forecast=spec.input.analysis.feature_policy == "historical_prediction",
                    outcome_end=max((s["window_end"] for s in row["snapshots"]), default=""),
                )
                for snapshot in row["snapshots"]:
                    row["evidence"].append(
                        EvidenceRepository(connection).metric_evidence(snapshot["id"]).model_dump()
                    )
                inputs.append(EntityRef.model_validate(row["post_ref"]))
                if row["account_context_ref"]:
                    inputs.append(EntityRef.model_validate(row["account_context_ref"]))
                for key in spec.input.analysis.features:
                    if not row["feature_values"][key]["eligible"]:
                        row["features"][key] = None
            _publications(connection, rows, spec, spec.input, inputs)
        allowed = set(spec.input.analysis.features) | PUBLICATION_FEATURES
        return _finalize(
            rows,
            inputs,
            spec,
            allowed,
            {
                "metric_definitions": definitions,
                "lane": "aggregate post attention; traffic channel not identified",
            },
        )
    with app.database.transaction() as connection:
        if isinstance(spec.input, DistributionInput):
            return _distribution(connection, spec, spec.input)
        return _funnels(connection, spec, spec.input)


def _finalize(
    rows: list[dict[str, Any]],
    inputs: list[EntityRef],
    spec: DiscoverySpec,
    allowed: set[str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    keys = {k for c in spec.candidates for k in c.features + c.adjusters}
    if keys - allowed:
        raise ConfigurationError(
            "Unknown, unavailable or target-derived discovery feature: "
            + ", ".join(sorted(keys - allowed))
        )
    if len({r["unit_id"] for r in rows}) != len(rows):
        raise ConfigurationError("Duplicate research units cannot increase sample size")
    eligible, excluded = [], []
    for row in rows:
        reason = None
        if row["platform"] != spec.scope.platform or row["niche"] not in spec.scope.niches:
            reason = "outside_platform_or_niche_scope"
        elif (
            not row["published_at"]
            or not spec.scope.period_start <= row["published_at"] < spec.scope.period_end
        ):
            reason = "outside_declared_period"
        elif row["outcome"] is None or any(row["features"].get(k) is None for k in keys):
            reason = "missing_outcome_or_declared_feature_complete_case_union"
        if reason:
            excluded.append({"unit_id": row["unit_id"], "reason": reason})
        else:
            eligible.append(row)
    return {
        "rows": eligible,
        "excluded": excluded,
        "entities": list({r.revision_id: r.model_dump() for r in inputs}.values()),
        "provenance": provenance,
        "context_recipe": RECIPE,
    }


def _distribution(
    connection: Connection, spec: DiscoverySpec, source: DistributionInput
) -> dict[str, Any]:
    from socialdna.application.platform_service import observation_data
    from socialdna.domain.platform_research import DistributionObservation

    rows, inputs, signatures = [], [], set()
    for ref in source.observations:
        if ref.kind != "distribution_observation":
            raise ConfigurationError("Distribution input requires actual C1 observations")
        payload = context.read(connection, ref, spec.as_of)
        raw = DistributionObservation.model_validate(payload["spec"])
        data = observation_data(connection, raw, spec.as_of)
        if any(
            data["scope"][k] != getattr(spec.scope, k)
            for k in ("platform", "surface", "native_format", "language", "market", "audience")
        ) or (
            data["mapping"]["surface"] != spec.scope.surface
            or data["mapping"]["traffic"] != spec.scope.traffic
        ):
            raise ConfigurationError(
                "Incompatible platform/surface/language/audience/exposure scope"
            )
        if (
            source.timing == "available_before_later_window"
            and not data["early_known_before_later"]
        ):
            raise ConfigurationError("Early response was not known before later distribution")
        cohort = behavioral.read(connection, EntityRef.model_validate(data["cohort"]), spec.as_of)[
            "spec"
        ]
        post = _account(connection, raw.post)
        signatures.add(
            (
                hash_config(
                    {"eligibility": cohort["eligibility"], "dimensions": cohort["dimensions"]}
                ),
                tuple(
                    (
                        data[p]["definition"]["revision_id"],
                        data[p]["unit"],
                        (
                            datetime.fromisoformat(data[p]["clock"]["window_end"])
                            - datetime.fromisoformat(data[p]["clock"]["window_start"])
                        ).total_seconds(),
                        (
                            datetime.fromisoformat(data[p]["clock"]["window_start"])
                            - datetime.fromisoformat(post["published_at"])
                        ).total_seconds(),
                    )
                    for p in ("early", "later")
                ),
            )
        )
        row = _unit(
            connection,
            raw.account,
            raw.post.id,
            post["published_at"],
            data["later"]["clock"]["window_end"],
            EvidenceRepository(connection).entity(raw.later)["available_at"],
            {"distribution.early": data["early"]["value"]},
            data["later"]["value"],
            [context.cite(connection, ref).model_dump()],
            post_id=raw.post.id,
        )
        row["niche"] = data["scope"]["niche"]
        row["original_published_at"] = post["published_at"]
        if source.timing == "available_before_later_window":
            row["published_at"] = data["later"]["clock"]["window_start"]
            row["forecast"] = True
        versions, assets = metadata.tables["post_media_versions"], metadata.tables["media_assets"]
        row["duplicate_group"] = connection.scalar(
            select(assets.c.sha256)
            .join(versions, versions.c.media_id == assets.c.id)
            .where(
                versions.c.post_id == raw.post.id,
                versions.c.position == 0,
                versions.c.available_at <= spec.as_of,
            )
            .order_by(versions.c.available_at.desc())
            .limit(1)
        )
        rows.append(row)
        inputs.append(ref)
    if len(signatures) != 1:
        raise ConfigurationError(
            "Distribution comparisons require identical source definitions and window lengths"
        )
    official = []
    for ref in source.statements:
        if ref.kind != "platform_statement":
            raise ConfigurationError("Official lane requires actual reviewed statements")
        statement = context.read(connection, ref, spec.as_of)
        document = context.read(
            connection, EntityRef.model_validate(statement["spec"]["document"]), spec.as_of
        )
        if (
            document["spec"]["platform"] != spec.scope.platform
            or statement["spec"]["surface"] != spec.scope.surface
        ):
            raise ConfigurationError("Official guidance belongs to a different surface")
        inputs.append(ref)
        official.append({"ref": ref.model_dump(), "claim_level": "official_guidance"})
    return _finalize(
        rows,
        inputs,
        spec,
        {"distribution.early"},
        {
            "lane": "local_observational_not_ranking_weights",
            "official_guidance": official,
            "prior_exposure": "not adjusted; unobserved allocation/feedback confounding remains",
        },
    )


def _funnels(connection: Connection, spec: DiscoverySpec, source: FunnelsInput) -> dict[str, Any]:
    from socialdna.application.profile_service import funnel_data
    from socialdna.domain.profile import FunnelContext

    rows, inputs, signatures, accounts = [], [], set(), set()
    for ref in source.observations:
        if ref.kind != "funnel_context":
            raise ConfigurationError("Conversion input requires actual measured C1 account funnels")
        payload = context.read(connection, ref, spec.as_of)
        raw = FunnelContext.model_validate(payload["spec"])
        data = funnel_data(connection, raw, spec.as_of)
        if data["profile_exposure"] != "source_attested" or raw.profile is None:
            raise ConfigurationError("Profile predictors require known exact-version exposure")
        if raw.account.id in accounts:
            raise ConfigurationError(
                "Initial profile discovery uses one period per account; carryover not modeled"
            )
        accounts.add(raw.account.id)
        matches = [
            r
            for r in data["rates"]
            if r["numerator"] == source.numerator
            and r["denominator"] == source.denominator
            and r["reason"] is None
        ]
        if len(matches) != 1:
            raise ConfigurationError(
                "Requested funnel rate is absent, ambiguous or has incompatible denominators"
            )
        stages = [
            next(s for s in data["stages"].values() if s["signal"] == signal)
            for signal in (source.numerator, source.denominator)
        ]
        signatures.add(
            tuple(
                (
                    s["definition"]["revision_id"],
                    hash_config(
                        {
                            k: v
                            for k, v in behavioral.read(
                                connection, EntityRef.model_validate(s["cohort"]), spec.as_of
                            )["spec"].items()
                            if k in ("eligibility", "dimensions")
                        }
                    ),
                    (
                        datetime.fromisoformat(s["clock"]["window_end"])
                        - datetime.fromisoformat(s["clock"]["window_start"])
                    ).total_seconds(),
                )
                for s in stages
            )
        )
        profile = context.read(connection, raw.profile, spec.as_of)["spec"]
        features: dict[str, float | None] = {
            "profile.bio_length": float(len(profile["bio"]["value"]))
            if profile["bio"]["state"] in ("present", "empty")
            else None,
            "profile.pillar_count": float(len(profile["content_pillars"]))
            if profile["declaration_basis"] != "unknown"
            else None,
        }
        for name in ("links", "pins"):
            features[f"profile.{name}_count"] = (
                float(len(profile[name]))
                if profile[f"{name}_state"] in ("collected", "empty")
                else None
            )
        row = _unit(
            connection,
            raw.account,
            ref.id,
            stages[0]["clock"]["window_start"],
            stages[0]["clock"]["window_end"],
            EvidenceRepository(connection).entity(ref)["available_at"],
            features,
            matches[0]["value"],
            [context.cite(connection, ref).model_dump()],
        )
        row["measurement_members"] = [
            "measurement:" + stage.measurement.revision_id for stage in raw.stages
        ]
        row["measurement_members"].extend(
            "account-event:"
            + hash_config(
                {
                    "account": raw.account.id,
                    "definition": s["definition"],
                    "cohort": s["cohort"],
                    "start": s["clock"]["window_start"],
                    "end": s["clock"]["window_end"],
                }
            )
            for s in stages
        )
        rows.append(row)
        inputs.append(ref)
    if len(signatures) != 1:
        raise ConfigurationError(
            "Funnel comparisons require the same actual source event definitions"
        )
    return _finalize(
        rows,
        inputs,
        spec,
        PROFILE_FEATURES,
        {
            "lane": "account_aggregate_rate_not_profile_effect",
            "attribution": "not reassigned",
            "context": "language/audience/source frame analyst-declared, not inferred from a bio",
        },
    )
