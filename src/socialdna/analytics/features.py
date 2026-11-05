"""Versioned production features with content, knowledge and recipe clocks."""

import json
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.research import CorrectedPerformanceSpec
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

RECIPE_ID = "primitive-content-2"
RECIPE = {
    "version": "2.0",
    "missing": "no_imputation",
    "duration_seconds": "immutable primary-media duration_ms / 1000",
    "caption_length": "Unicode code points of captured caption version",
    "publishing_hour_utc": "captured publication timestamp UTC hour; not circular",
    "visual.motion": "opening (<3000ms) median optical flow",
    "visual.appearance": "opening (<3000ms) median brightness",
    "audio.loudness": "opening (<3000ms) median RMS dBFS",
    "annotation": "deterministic, outcome-blind; no semantic or psychological inference",
}


def captured_entities(
    connection: Connection, kind: str, cutoff: str
) -> dict[str, list[dict[str, Any]]]:
    """Canonical SQL history only, in revision order. Unknown legacy time is not backdated."""
    table = metadata.tables["entity_revisions"]
    result: dict[str, list[dict[str, Any]]] = {}
    repository = EvidenceRepository(connection)
    for record in connection.execute(
        select(table)
        .where(
            table.c.kind == kind, table.c.available_at.is_not(None), table.c.available_at <= cutoff
        )
        .order_by(table.c.entity_id, table.c.revision_no)
    ).mappings():
        row = repository.entity(repository.ref(dict(record)))
        row["payload"] = json.loads(row["payload_json"])
        result.setdefault(row["entity_id"], []).append(row)
    return result


def field_revision(history: list[dict[str, Any]], field: str) -> dict[str, Any]:
    """Inherited partial-update fields retain their original supplying revision.

    Only the current contiguous value history is traversed: an edit back to an
    earlier spelling does not prove that spelling persisted through the edit.
    """
    current = history[-1]
    value = current["payload"].get(field)
    for previous in reversed(history[:-1]):
        if previous["payload"].get(field) != value:
            break
        current = previous
    return current


class FeatureMaterializer:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.now = utc_now()
        table = metadata.tables["feature_recipes"]
        connection.execute(
            insert(table)
            .values(
                id=RECIPE_ID, version="2.0", spec_json=canonical_json(RECIPE), available_at=self.now
            )
            .on_conflict_do_nothing()
        )
        self.recipe_available_at = str(
            connection.scalar(select(table.c.available_at).where(table.c.id == RECIPE_ID))
        )
        if connection.scalar(
            select(table.c.spec_json).where(table.c.id == RECIPE_ID)
        ) != canonical_json(RECIPE):
            raise StorageIntegrityError("Feature recipe changed without a new immutable version")

    def materialize(
        self,
        history: list[dict[str, Any]],
        values: dict[str, float | None],
        *,
        media: dict[str, Any],
        media_run: dict[str, Any],
        spec: CorrectedPerformanceSpec,
        creative_bundle: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        result = {}
        for key in sorted(set(spec.features) | set(spec.covariates)):
            if key in spec.creative_recipes:
                continue
            field = "caption" if key == "caption_length" else "published_at"
            origin = field_revision(history, field)
            revision_ids = [origin["id"]]
            source_ids = [origin["source_id"]] if origin["source_id"] else []
            available_at = origin["available_at"]
            content_valid_at = None
            evidence = []
            if key == "duration_seconds" or "." in key:
                available_at = media.get("available_at")
                source_ids.extend(media.get("source_ids", []))
                revision_ids.extend(media.get("revision_ids", []))
                # Media identity proves bytes, not an unobserved historical post/media association.
                content_valid_at = media.get("association_available_at")
                if "." in key:
                    available_at = (
                        max(available_at, media_run["available_at"])
                        if (available_at and media_run.get("available_at"))
                        else None
                    )
                    evidence = media_run.get("evidence_refs", [])
            value = values.get(key)
            lineage = {
                "entity_revision_ids": sorted(set(revision_ids)),
                "source_ids": sorted(set(source_ids)),
                "evidence_refs": evidence,
                "media_sha256": media.get("sha256"),
                "media_association_revision_id": media.get("association_revision_id"),
                "input_available_at": available_at,
                "recipe_available_at": self.recipe_available_at,
                "historical_content_validity": "unverified"
                if content_valid_at is None
                else "captured",
                "annotation_protocol": RECIPE["annotation"],
            }
            deployable_at = max(available_at, self.recipe_available_at) if available_at else None
            decision = history[-1]["payload"].get("published_at")
            eligible = value is not None
            if spec.feature_policy == "historical_prediction":
                eligible = bool(
                    eligible and deployable_at and decision and deployable_at <= decision
                )
            document = {
                "post_id": history[-1]["entity_id"],
                "subject_revision_id": history[-1]["id"],
                "recipe_id": RECIPE_ID,
                "feature_key": key,
                "value": value,
                "available_at": deployable_at,
                "content_valid_at": content_valid_at,
                "lineage_json": canonical_json(lineage),
                "coverage": "observed" if value is not None else "missing",
            }
            identity = stable_id("feature-value", hash_config(document))
            self.connection.execute(
                insert(metadata.tables["feature_values"])
                .values(id=identity, **document, materialized_at=self.now)
                .on_conflict_do_nothing()
            )
            result[key] = {
                "id": identity,
                "value": value,
                "eligible": eligible,
                "available_at": deployable_at,
                "content_valid_at": content_valid_at,
                "lineage": lineage,
                "coverage": document["coverage"],
            }
        if spec.creative_recipes:
            for key, recipe_id in sorted(spec.creative_recipes.items()):
                result[key] = materialize_creative_value(
                    self.connection,
                    recipe_id,
                    feature_key=key,
                    subject={
                        "kind": "post",
                        "id": history[-1]["entity_id"],
                        "revision_id": history[-1]["id"],
                    },
                    bundle=creative_bundle
                    or {"events": [], "coverage": [], "reason": "missing_media"},
                    post_payload=history[-1]["payload"],
                    feature_policy=spec.feature_policy,
                    proposals=spec.creative_label_policy == "proposals_exploratory",
                    cutoff=spec.knowledge_cutoff,
                )
        return result


def materialize_creative_value(
    connection: Connection,
    recipe_id: str,
    *,
    feature_key: str,
    subject: dict[str, str],
    bundle: dict[str, Any],
    post_payload: dict[str, Any] | None = None,
    feature_policy: str = "retrospective_content",
    proposals: bool = False,
    cutoff: str | None = None,
) -> dict[str, Any]:
    from socialdna.analytics.creative_recipes import dependencies, evaluate_recipe
    from socialdna.analyzers.creative import RECIPES
    from socialdna.analyzers.production import RECIPES as PRODUCTION_RECIPES
    from socialdna.domain.creative import FeatureRecipe
    from socialdna.domain.evidence import EntityRef, PostTextLocator
    from socialdna.domain.production import ProductionRecipe
    from socialdna.storage.creative_repository import (
        cite_post_text,
        post_text,
        register_definitions,
    )

    recipes: dict[str, FeatureRecipe | ProductionRecipe] = {**RECIPES, **PRODUCTION_RECIPES}
    if recipe_id not in recipes:
        from socialdna.core.exceptions import ConfigurationError

        raise ConfigurationError("Unknown pinned creative recipe: " + recipe_id)
    register_definitions(connection)
    recipe = recipes[recipe_id]
    repository = EvidenceRepository(connection)
    entity = repository.entity(EntityRef.model_validate(subject))
    recipe_record = repository.get("feature_recipes", recipe_id)
    relevant = dependencies(recipe) | {"unclassified"}
    events = []
    for item in bundle["events"]:
        event = item["annotation"]
        if event["technique"] not in relevant:
            continue
        if event["post"]:
            if subject["kind"] != "post" or event["post"]["id"] != subject["id"]:
                continue
            matching = True
            for data in item["inputs"]:
                evidence = repository.get("evidence_revisions", data["ref"]["revision_id"])
                if evidence["locator_kind"] == "post_text":
                    locator = PostTextLocator.model_validate_json(evidence["locator_json"])
                    original = post_text(
                        repository, locator.subject, locator.field, locator.tag_index
                    )
                    current = (
                        (post_payload or {}).get("caption")
                        if locator.field == "caption"
                        else (post_payload or {}).get("hashtags", [])
                    )
                    matching = matching and (
                        original == current
                        if locator.field == "caption"
                        else isinstance(current, list) and original in current
                    )
            if not matching:
                continue
        events.append(item)
    coverages = [
        item
        for item in bundle["coverage"]
        if set(item["coverage"]["techniques"]).intersection(relevant)
    ]
    selected = {**bundle, "events": events, "coverage": coverages}
    evidence_refs = [item["evidence"] for item in events + coverages]
    entities = [item["ref"] for item in events + coverages]
    source_ids = {item["source_id"] for item in events + coverages if item["source_id"]}
    available_times = [item["available_at"] for item in events + coverages]
    recipe_document = json.loads(recipe_record["spec_json"])
    for technique in recipe_document["techniques"]:
        definition = repository.entity(EntityRef.model_validate(technique))
        entities.append(technique)
        if definition["source_id"]:
            source_ids.add(definition["source_id"])
        available_times.append(definition["available_at"])
    protocols = [item["protocol"] for item in events + coverages]
    if recipe.operation == "hashtag_count":
        tags = (post_payload or {}).get("hashtags")
        evaluated = {
            "value": float(len(tags)) if isinstance(tags, list) else None,
            "coverage": "observed" if isinstance(tags, list) else "unknown",
            "reason": "captured_normalized_hashtag_inventory"
            if isinstance(tags, list)
            else "unknown_hashtag_inventory",
        }
        entities.append(subject)
        if entity["source_id"]:
            source_ids.add(entity["source_id"])
        available_times.append(entity["available_at"])
        if tags:
            for index in range(len(tags)):
                evidence_refs.append(
                    cite_post_text(
                        connection, EntityRef.model_validate(subject), "hashtag", tag_index=index
                    ).model_dump()
                )
    else:
        from socialdna.analytics.production_recipes import evaluate_recipe as production_recipe

        evaluated = (
            production_recipe(recipe, selected)
            if isinstance(recipe, ProductionRecipe)
            else evaluate_recipe(recipe, selected, proposals=proposals)
        )
    # Absence is an assertion about coverage as well as a lack of positive events.
    # Whole selection revisions live in the analysis row, not the dependency cache
    # key; unrelated annotation changes do not invalidate an unchanged measurement.
    known_times = [time for time in available_times if time]
    available_at = (
        max([recipe_record["available_at"], *known_times])
        if known_times and len(known_times) == len(available_times)
        else None
    )
    eligible = evaluated["value"] is not None
    if cutoff and (available_at is None or available_at > cutoff):
        eligible = False
    if feature_policy == "historical_prediction":
        decision = (post_payload or {}).get("published_at")
        eligible = bool(eligible and available_at and decision and available_at <= decision)
    lineage = {
        "recipe_spec": json.loads(recipe_record["spec_json"]),
        "recipe_available_at": recipe_record["available_at"],
        "entity_refs": sorted(entities, key=lambda item: item["revision_id"]),
        "evidence_refs": sorted(evidence_refs, key=lambda item: item["revision_id"]),
        "source_ids": sorted(source_ids),
        "reason": evaluated["reason"],
        "annotation_protocols": protocols,
        "label_policy": "proposals_exploratory" if proposals else "reviewed_only",
        "outcome_blind": bool(protocols)
        and all(p["outcome_access"] == "blinded" for p in protocols),
        "scientific_scope": "observable annotation only; no psychological or causal claim",
    }
    document = {
        "post_id": subject["id"] if subject["kind"] == "post" else None,
        "subject_revision_id": subject["revision_id"],
        "recipe_id": recipe_id,
        "feature_key": feature_key,
        "value": evaluated["value"],
        "available_at": available_at,
        "content_valid_at": None,
        "lineage_json": canonical_json(lineage),
        "coverage": evaluated["coverage"],
        "media_id": subject["id"] if subject["kind"] == "media" else None,
    }
    identity = stable_id("creative-feature-value", hash_config(document))
    connection.execute(
        insert(metadata.tables["feature_values"])
        .values(id=identity, **document, materialized_at=utc_now())
        .on_conflict_do_nothing()
    )
    return {
        "id": identity,
        "value": evaluated["value"],
        "available_at": available_at,
        "content_valid_at": None,
        "coverage": evaluated["coverage"],
        "eligible": eligible,
        "lineage": lineage,
    }


def eligible_rows(
    rows: list[dict[str, Any]], spec: CorrectedPerformanceSpec
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["outcome"] is not None
        and row["published_at"]
        and all(row["feature_values"].get(key, {}).get("eligible", False) for key in spec.features)
    ]
