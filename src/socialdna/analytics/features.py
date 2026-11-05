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
    ) -> dict[str, dict[str, Any]]:
        result = {}
        for key in sorted(set(spec.features) | set(spec.covariates)):
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
        return result


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
