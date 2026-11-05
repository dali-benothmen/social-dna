"""Canonical revisions and first-use typed bindings; no model/index dependencies."""

import json
from typing import Any

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import MediaInterval, utc_now
from socialdna.domain.evidence import (
    AudienceLocator,
    BehavioralLocator,
    CommentLocator,
    ContextLocator,
    CreativeEventLocator,
    EntityRef,
    EvidenceRef,
    MediaLocator,
    MetricLocator,
    PostTextLocator,
    ResearchLocator,
    StatisticalLocator,
    StudyLocator,
)
from socialdna.storage.schema import metadata

LEGACY_KINDS = {
    "account": ("accounts", "id"),
    "post": ("posts", "id"),
    "media": ("media_assets", "id"),
    "comment": ("comments", "id"),
    "metric_snapshot": ("metric_observations", "id"),
    "metric_definition": ("metric_definitions", "key"),
    "frame": ("frames", "id"),
    "scene": ("scenes", "id"),
    "observation": ("observations", "id"),
    "text_segment": ("text_segments", "id"),
    "audio_segment": ("audio_segments", "id"),
    "ocr_box": ("ocr_boxes", "id"),
}
AUTHORED_KINDS = {
    "profile_snapshot",
    "profile_review",
    "profile_rubric",
    "funnel_definition",
    "funnel_context",
    "platform_document",
    "platform_statement",
    "platform_capabilities",
    "distribution_observation",
    "publication_context",
    "publishing_window",
    "trend_context",
    "context_report",
    "literature_source",
    "study_finding",
    "psychological_construct",
    "operationalization",
    "research_protocol",
    "research_assessment",
    "research_finding",
    "experiment_brief",
    "behavioral_metric_definition",
    "audience_cohort",
    "metric_measurement",
    "metric_series",
    "metric_bin",
    "attribution_observation",
    "signed_metric_change",
    "behavioral_analysis",
    "reaction_rubric",
    "audience_collection",
    "audience_annotation_set",
    "reaction_annotation",
    "reaction_cluster",
    "content_reaction_link",
    "audience_analysis",
    "research_question",
    "hypothesis",
    "citation_report",
    "statistical_analysis",
    "creative_technique",
    "creative_annotation_set",
    "creative_event",
    "creative_relation",
    "creative_coverage",
}


class EvidenceRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def get(self, table_name: str, identity: str, key: str = "id") -> dict[str, Any]:
        table = metadata.tables[table_name]
        row = (
            self.connection.execute(select(table).where(table.c[key] == identity))
            .mappings()
            .first()
        )
        if row is None:
            raise ConfigurationError(f"Unknown {table_name} identity: {identity}")
        return dict(row)

    def entity(self, ref: EntityRef) -> dict[str, Any]:
        from socialdna.storage.audience_retention import guard

        guard(self.connection, "entity_revision", ref.revision_id)
        row = self.get("entity_revisions", ref.revision_id)
        if (row["kind"], row["entity_id"]) != (ref.kind, ref.id):
            raise ConfigurationError("Entity kind/identity does not match its revision")
        if hash_config(json.loads(row["payload_json"])) != row["content_hash"]:
            raise StorageIntegrityError("Entity revision payload hash mismatch")
        if row["kind"] in LEGACY_KINDS:
            binding = self.get("legacy_entity_bindings", ref.revision_id, "revision_id")
            if binding[row["kind"] + "_id"] != ref.id:
                raise StorageIntegrityError("Entity revision has a wrong-kind legacy binding")
            payload = json.loads(row["payload_json"])
            _, key = LEGACY_KINDS[row["kind"]]
            if payload.get(key) != ref.id:
                raise StorageIntegrityError("Captured entity identity does not match its binding")
        elif row["kind"] == "statistical_analysis":
            binding = self.get("statistical_entity_bindings", ref.revision_id, "revision_id")
            analysis = self.get("statistical_analyses", binding["analysis_id"])
            report = json.loads(analysis["result_json"])
            configuration = report["analysis_configuration"]
            payload = json.loads(row["payload_json"])
            if (
                binding["analysis_id"] != ref.id
                or payload
                != {
                    "analysis_id": ref.id,
                    "run_id": analysis["run_id"],
                    "input_hash": configuration["input_hash"],
                    "reference_hash": configuration["reference_hash"],
                    "results_hash": hash_config(report["results"]),
                }
                or hash_config(
                    {"rows": report["posts"], "definitions": report["metric_definitions"]}
                )
                != payload["input_hash"]
                or hash_config({"rows": report["reference_population"]})
                != payload["reference_hash"]
            ):
                raise StorageIntegrityError(
                    "Statistical subject does not match its frozen analysis"
                )
        elif row["kind"] in (
            "creative_annotation_set",
            "creative_event",
            "creative_relation",
            "creative_coverage",
        ):
            from socialdna.storage.creative_repository import validate_projection

            validate_projection(self, ref, json.loads(row["payload_json"]))
        if row["kind"] in (
            "audience_collection",
            "audience_annotation_set",
            "reaction_annotation",
            "reaction_cluster",
            "content_reaction_link",
            "audience_analysis",
        ):
            from socialdna.storage.audience_repository import validate_projection

            validate_projection(self, ref, json.loads(row["payload_json"]))
        if row["kind"] in (
            "behavioral_metric_definition",
            "audience_cohort",
            "metric_measurement",
            "metric_series",
            "metric_bin",
            "attribution_observation",
            "signed_metric_change",
            "behavioral_analysis",
        ):
            from socialdna.storage.behavioral_repository import (
                validate_projection as validate_behavioral,
            )

            validate_behavioral(self, ref, json.loads(row["payload_json"]))
        if ref.kind in ("research_protocol", "research_assessment"):
            from socialdna.storage.research_repository import validate_projection as research_check

            research_check(self, ref, json.loads(row["payload_json"]))
        if ref.kind in (
            "publication_context",
            "publishing_window",
            "trend_context",
            "context_report",
            "platform_document",
            "platform_statement",
            "platform_capabilities",
            "distribution_observation",
            "profile_snapshot",
            "profile_review",
            "funnel_definition",
            "funnel_context",
        ):
            from socialdna.storage.context_repository import validate_projection as context_check

            context_check(self, ref, json.loads(row["payload_json"]))
        provenance = self.get("provenance_records", row["provenance_id"])
        if provenance["source_record_id"] != row["source_id"]:
            raise StorageIntegrityError("Entity provenance/source mismatch")
        return row

    @staticmethod
    def ref(row: dict[str, Any]) -> EntityRef:
        return EntityRef(kind=row["kind"], id=row["entity_id"], revision_id=row["id"])

    def latest(self, kind: str, identity: str) -> EntityRef | None:
        table = metadata.tables["entity_revisions"]
        row = (
            self.connection.execute(
                select(table)
                .where(table.c.kind == kind, table.c.entity_id == identity)
                .order_by(table.c.revision_no.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return self.ref(dict(row)) if row else None

    def provenance(self, kind: str, identity: str) -> str:
        links, records = (
            metadata.tables[name] for name in ("provenance_links", "provenance_records")
        )
        value = self.connection.scalar(
            select(records.c.id)
            .join(links, links.c.provenance_id == records.c.id)
            .where(links.c.entity_type == kind, links.c.entity_id == identity)
            .order_by(records.c.created_at.desc(), records.c.id.desc())
            .limit(1)
        )
        if value:
            return str(value)
        value = stable_id("r1-legacy-capture", kind, identity)
        self.connection.execute(
            insert(records)
            .values(
                id=value,
                method="legacy_capture",
                tool_name="socialdna",
                config_json=canonical_json({"historical_validity": "unknown"}),
                created_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        return value

    def save_entity(
        self,
        kind: str,
        identity: str,
        payload: dict[str, Any],
        provenance_id: str,
        *,
        mode: str = "authored",
        available_at: str | None = None,
    ) -> EntityRef:
        from socialdna.storage.audience_retention import guard

        if kind == "comment":
            guard(self.connection, "comment", identity)
        if kind not in LEGACY_KINDS and kind not in AUTHORED_KINDS:
            raise ConfigurationError(f"Unregistered entity kind: {kind}")
        provenance = self.get("provenance_records", provenance_id)
        if provenance["source_record_id"] and not (
            mode == "legacy_capture" and kind in LEGACY_KINDS and kind != "comment"
        ):
            guard(self.connection, "source", provenance["source_record_id"])
        digest = hash_config(payload)
        revision_id = stable_id("entity-revision", kind, identity, digest, provenance_id, mode)
        table = metadata.tables["entity_revisions"]
        if self.connection.scalar(select(table.c.id).where(table.c.id == revision_id)):
            return EntityRef(kind=kind, id=identity, revision_id=revision_id)
        self.connection.execute(
            insert(metadata.tables["entity_identities"])
            .values(
                kind=kind,
                entity_id=identity,
                created_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        number = (
            self.connection.scalar(
                select(func.max(table.c.revision_no)).where(
                    table.c.kind == kind,
                    table.c.entity_id == identity,
                )
            )
            or 0
        )
        self.connection.execute(
            table.insert().values(
                id=revision_id,
                kind=kind,
                entity_id=identity,
                revision_no=number + 1,
                schema_version="1.0",
                content_hash=digest,
                payload_json=canonical_json(payload),
                recorded_at=utc_now(),
                available_at=available_at,
                capture_mode=mode,
                provenance_id=provenance_id,
                source_id=provenance["source_record_id"],
            )
        )
        return EntityRef(kind=kind, id=identity, revision_id=revision_id)

    def capture(
        self,
        kind: str,
        identity: str,
        provenance_id: str | None = None,
        *,
        mode: str = "legacy_capture",
    ) -> EntityRef:
        if kind not in LEGACY_KINDS:
            raise ConfigurationError(f"Not a registered legacy kind: {kind}")
        if kind == "metric_snapshot" and (existing := self.latest(kind, identity)):
            # An old measurement's subject context cannot be rebound to today's
            # edited post merely because another import repeats the same value.
            return existing
        name, key = LEGACY_KINDS[kind]
        payload = self.get(name, identity, key)
        provenance_id = (
            provenance_id or payload.get("provenance_id") or self.provenance(kind, identity)
        )
        if kind == "post" and mode == "source_capture":
            tags, links = (metadata.tables[name] for name in ("tags", "post_tags"))
            payload["topics"] = sorted(
                self.connection.scalars(
                    select(tags.c.normalized_value)
                    .join(links, links.c.tag_id == tags.c.id)
                    .where(links.c.post_id == identity, tags.c.kind == "topic")
                )
            )
            payload["hashtags"] = sorted(
                self.connection.scalars(
                    select(tags.c.normalized_value)
                    .join(links, links.c.tag_id == tags.c.id)
                    .where(links.c.post_id == identity, tags.c.kind == "hashtag")
                )
            )
        if kind == "comment":
            post = self.latest("post", payload["post_id"]) or self.capture(
                "post", payload["post_id"]
            )
            payload["post_ref"] = post.model_dump()
        elif kind == "metric_snapshot":
            definition = self.latest("metric_definition", payload["metric_key"]) or self.capture(
                "metric_definition", payload["metric_key"]
            )
            subject = self.latest(payload["subject_type"], payload["subject_id"]) or self.capture(
                payload["subject_type"], payload["subject_id"]
            )
            payload.update(
                definition_ref=definition.model_dump(), measured_subject_ref=subject.model_dump()
            )
        # Legacy capture time is known; historical validity/availability generally is not.
        available_at = utc_now() if mode == "source_capture" else None
        ref = self.save_entity(
            kind, identity, payload, provenance_id, mode=mode, available_at=available_at
        )
        self.connection.execute(
            insert(metadata.tables["legacy_entity_bindings"])
            .values(
                revision_id=ref.revision_id,
                **{kind + "_id": identity},
            )
            .on_conflict_do_nothing()
        )
        return ref

    def save_evidence(
        self,
        identity: str,
        locator: MediaLocator
        | CommentLocator
        | MetricLocator
        | StatisticalLocator
        | PostTextLocator
        | CreativeEventLocator
        | AudienceLocator
        | BehavioralLocator
        | StudyLocator
        | ContextLocator
        | ResearchLocator,
        provenance_id: str,
        *,
        task_id: str | None = None,
        run_id: str | None = None,
        available_at: str | None = None,
    ) -> EvidenceRef:
        self.entity(locator.subject)
        provenance = self.get("provenance_records", provenance_id)
        payload = locator.model_dump(mode="json")
        digest = hash_config(payload)
        revision_id = stable_id("evidence-revision", identity, digest)
        self.connection.execute(
            insert(metadata.tables["evidence_records"])
            .values(
                id=identity,
                created_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )
        self.connection.execute(
            insert(metadata.tables["evidence_revisions"])
            .values(
                id=revision_id,
                evidence_id=identity,
                subject_revision_id=locator.subject.revision_id,
                locator_kind=locator.kind,
                schema_version="1.0",
                locator_json=canonical_json(payload),
                content_hash=digest,
                captured_at=utc_now(),
                available_at=available_at,
                provenance_id=provenance_id,
                source_id=provenance["source_record_id"],
                producer_task_id=task_id,
                producer_run_id=run_id,
            )
            .on_conflict_do_nothing()
        )
        return EvidenceRef(id=identity, revision_id=revision_id)

    def media_evidence(self, evidence_id: str, *, legacy: bool = True) -> EvidenceRef:
        bindings = metadata.tables["legacy_media_evidence_bindings"]
        existing = self.connection.scalar(
            select(bindings.c.evidence_revision_id).where(
                bindings.c.legacy_evidence_id == evidence_id
            )
        )
        if existing:
            return EvidenceRef(id=evidence_id, revision_id=existing)
        row = self.get("evidence_items", evidence_id)
        kind = row["subject_type"]
        mode = "legacy_capture" if legacy else "source_capture"
        subject = self.capture(kind, row["subject_id"], row["provenance_id"], mode=mode)
        target = json.loads(self.entity(subject)["payload_json"])
        owner = target
        if kind == "text_segment":
            owner = self.get("text_tracks", target["track_id"])
        elif kind == "ocr_box":
            frame = self.get("frames", target["frame_id"])
            segment = self.get("text_segments", target["text_segment_id"])
            owner = self.get("text_tracks", segment["track_id"])
            if frame["media_asset_id"] != owner["media_asset_id"]:
                raise StorageIntegrityError("OCR region frame/track media disagree")
        if (
            owner.get("media_asset_id") != row["media_asset_id"]
            or owner.get("task_id") != row["task_id"]
        ):
            raise StorageIntegrityError("Legacy evidence subject belongs to a different media/task")
        media = self.capture("media", row["media_asset_id"], row["provenance_id"], mode=mode)
        asset = json.loads(self.entity(media)["payload_json"])
        if row["start_ms"] < 0 or row["end_ms"] <= row["start_ms"]:
            raise StorageIntegrityError("Invalid legacy media interval")
        if asset["duration_ms"] is not None and row["end_ms"] > asset["duration_ms"]:
            raise StorageIntegrityError("Legacy evidence interval exceeds media duration")
        task = self.get("analysis_tasks", row["task_id"])
        run = self.get("analysis_runs", task["run_id"])
        if run["target_type"] != "media" or run["target_id"] != row["media_asset_id"]:
            raise StorageIntegrityError("Legacy evidence run does not target its media")
        locator = MediaLocator(
            subject=subject,
            media=media,
            interval=MediaInterval(start_ms=row["start_ms"], end_ms=row["end_ms"]),
            artifact_id=row["artifact_id"],
            excerpt=row["excerpt"],
        )
        ref = self.save_evidence(
            evidence_id,
            locator,
            row["provenance_id"],
            task_id=row["task_id"],
            run_id=task["run_id"],
            available_at=None if legacy else utc_now(),
        )
        self.connection.execute(
            bindings.insert().values(
                evidence_revision_id=ref.revision_id,
                legacy_evidence_id=evidence_id,
                media_revision_id=media.revision_id,
            )
        )
        return ref

    def comment_evidence(
        self,
        comment_id: str,
        start: int,
        end: int,
        *,
        revision_id: str | None = None,
    ) -> EvidenceRef:
        subject = (
            EntityRef(kind="comment", id=comment_id, revision_id=revision_id)
            if revision_id
            else (self.latest("comment", comment_id) or self.capture("comment", comment_id))
        )
        row = self.entity(subject)
        payload = json.loads(row["payload_json"])
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(payload["body"])
        ):
            raise ConfigurationError("Comment span is outside its exact original Unicode text")
        locator = CommentLocator(
            subject=subject,
            post=EntityRef.model_validate(payload["post_ref"]),
            start_char=start,
            end_char=end,
            quote=payload["body"][start:end],
        )
        identity = stable_id("comment-evidence", subject.revision_id, str(start), str(end))
        ref = self.save_evidence(
            identity, locator, row["provenance_id"], available_at=row["available_at"]
        )
        self.connection.execute(
            insert(metadata.tables["comment_evidence_bindings"])
            .values(
                evidence_revision_id=ref.revision_id,
                comment_revision_id=subject.revision_id,
                comment_id=comment_id,
                start_char=start,
                end_char=end,
            )
            .on_conflict_do_nothing()
        )
        return ref

    def metric_evidence(self, snapshot_id: str) -> EvidenceRef:
        subject = self.latest("metric_snapshot", snapshot_id) or self.capture(
            "metric_snapshot", snapshot_id
        )
        row = self.entity(subject)
        payload = json.loads(row["payload_json"])
        locator = MetricLocator(
            subject=subject,
            measured_subject=EntityRef.model_validate(payload["measured_subject_ref"]),
            definition=EntityRef.model_validate(payload["definition_ref"]),
            **{
                key: payload[key]
                for key in (
                    "value",
                    "availability",
                    "reason",
                    "observed_at",
                    "window_start",
                    "window_end",
                )
            },
        )
        identity = stable_id("metric-evidence", snapshot_id)
        ref = self.save_evidence(
            identity, locator, row["provenance_id"], available_at=row["available_at"]
        )
        self.connection.execute(
            insert(metadata.tables["metric_evidence_bindings"])
            .values(
                evidence_revision_id=ref.revision_id,
                metric_observation_id=snapshot_id,
                definition_revision_id=locator.definition.revision_id,
            )
            .on_conflict_do_nothing()
        )
        for alias in (f"metric:{snapshot_id}", f"socialdna:metric/{snapshot_id}"):
            self.connection.execute(
                insert(metadata.tables["evidence_aliases"])
                .values(
                    alias=alias,
                    evidence_revision_id=ref.revision_id,
                )
                .on_conflict_do_nothing()
            )
        return ref


def backfill_evidence(database: Any, *, batch_size: int = 200) -> None:
    """Bounded, restartable legacy capture. Cursor and rows commit together."""
    for kind in ("account", "post", "metric_definition", "comment", "metric_snapshot", "evidence"):
        while True:
            with database.transaction() as connection:
                ledger = metadata.tables["evidence_backfill"]
                state = (
                    connection.execute(select(ledger).where(ledger.c.kind == kind))
                    .mappings()
                    .first()
                )
                if state and state["status"] == "complete":
                    break
                name, key = ("evidence_items", "id") if kind == "evidence" else LEGACY_KINDS[kind]
                table = metadata.tables[name]
                ids = list(
                    connection.scalars(
                        select(table.c[key])
                        .where(table.c[key] > (state["last_id"] if state else ""))
                        .order_by(table.c[key])
                        .limit(batch_size)
                    )
                )
                repository = EvidenceRepository(connection)
                for identity in ids:
                    if kind == "comment":
                        from socialdna.storage.audience_retention import is_redacted

                        if is_redacted(connection, "comment", identity):
                            continue
                    if kind == "evidence":
                        repository.media_evidence(identity)
                    elif not repository.latest(kind, identity):
                        repository.capture(kind, identity)
                    if kind == "metric_snapshot":
                        repository.metric_evidence(identity)
                statement = insert(ledger).values(
                    kind=kind,
                    last_id=ids[-1] if ids else (state["last_id"] if state else ""),
                    status="pending" if len(ids) == batch_size else "complete",
                )
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ledger.c.kind],
                        set_={
                            "last_id": statement.excluded.last_id,
                            "status": statement.excluded.status,
                        },
                    )
                )
