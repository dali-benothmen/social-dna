"""Typed citation resolution, eligibility and terminal withdrawal for R1."""

import json
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Connection, or_, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.evidence import (
    AudienceLocator,
    BehavioralLocator,
    CommentLocator,
    ContextLocator,
    CreativeEventLocator,
    EntityRef,
    EvidenceLocator,
    EvidenceRef,
    MediaLocator,
    MetricLocator,
    PostTextLocator,
    ResearchLocator,
    ResolvedEvidence,
    StatisticalLocator,
    StudyLocator,
)
from socialdna.ingestion.tabular import timestamp
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

LOCATOR_ADAPTER: TypeAdapter[EvidenceLocator] = TypeAdapter(EvidenceLocator)  # type: ignore[arg-type]


class EvidenceResolver:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.repository = EvidenceRepository(connection)

    def resolve(
        self,
        ref: EvidenceRef | str,
        *,
        revision_id: str | None = None,
        purpose: Literal["inspect", "new_claim"] = "inspect",
        as_of: str | None = None,
        expected_subject: EntityRef | None = None,
        media_id: str | None = None,
        post_id: str | None = None,
        run_id: str | None = None,
        _ancestors: frozenset[str] = frozenset(),
        _memo: dict[str, ResolvedEvidence] | None = None,
    ) -> ResolvedEvidence:
        if purpose not in ("inspect", "new_claim"):
            raise ConfigurationError("Unknown evidence resolution purpose")
        if isinstance(ref, EvidenceRef):
            if revision_id and revision_id != ref.revision_id:
                raise ConfigurationError("Conflicting evidence revision arguments")
            identity, revision_id = ref.id, ref.revision_id
        else:
            identity = ref
        evidence = metadata.tables["evidence_revisions"]
        aliases = metadata.tables["evidence_aliases"]
        alias = self.connection.scalar(
            select(aliases.c.evidence_revision_id).where(aliases.c.alias == identity)
        )
        if alias:
            if revision_id and revision_id != alias:
                raise ConfigurationError("Alias does not refer to the requested revision")
            revision_id = str(alias)
            identity = self.repository.get("evidence_revisions", revision_id)["evidence_id"]
        rows = list(
            self.connection.execute(
                select(evidence).where(evidence.c.evidence_id == identity)
            ).mappings()
        )
        if revision_id is None:
            if len(rows) != 1:
                raise ConfigurationError(
                    "Unknown or ambiguous evidence ID; supply an exact revision"
                )
            row = dict(rows[0])
        else:
            row = self.repository.get("evidence_revisions", revision_id)
            if row["evidence_id"] != identity:
                raise ConfigurationError("Evidence identity does not match its revision")
        from socialdna.storage.audience_retention import is_redacted

        if is_redacted(self.connection, "evidence_revision", row["id"]):
            if purpose == "new_claim":
                raise ConfigurationError(
                    "Evidence was erased; new use and reproduction are unavailable"
                )
            subject = self.repository.get("entity_revisions", row["subject_revision_id"])
            return ResolvedEvidence(
                ref=EvidenceRef(id=identity, revision_id=row["id"]),
                locator_kind=row["locator_kind"],
                subject=self.repository.ref(subject),
                locator=None,
                source={"id": row["source_id"], "uri": None, "permission_basis": None},
                provenance_id=row["provenance_id"],
                producer_run_id=row["producer_run_id"],
                producer_task_id=row["producer_task_id"],
                captured_at=row["captured_at"],
                available_at=row["available_at"],
                eligible=False,
                limitations=(
                    "Audience evidence was erased; only permitted tombstone metadata remains.",
                ),
            )
        memo = _memo if _memo is not None else {}
        payload = json.loads(row["locator_json"])
        if row["id"] in _ancestors or len(_ancestors) >= 32:
            raise StorageIntegrityError("Cyclic or excessively deep evidence dependency chain")
        if _ancestors and row["id"] in memo:
            return memo[row["id"]]
        if hash_config(payload) != row["content_hash"]:
            raise StorageIntegrityError("Evidence locator hash mismatch")
        try:
            locator = LOCATOR_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise StorageIntegrityError("Stored evidence locator is invalid") from exc
        if (
            locator.kind != row["locator_kind"]
            or locator.subject.revision_id != row["subject_revision_id"]
        ):
            raise StorageIntegrityError("Evidence locator and registry subject disagree")
        related = [locator.subject]
        if isinstance(locator, StudyLocator):
            related.append(locator.source_document)
        if isinstance(locator, AudienceLocator):
            related.append(locator.collection)
        if isinstance(locator, (MediaLocator, CreativeEventLocator)):
            related.append(locator.media)
            if isinstance(locator, CreativeEventLocator) and locator.kind == "creative_event":
                event = json.loads(self.repository.entity(locator.subject)["payload_json"])
                related.append(EntityRef.model_validate(event["technique"]))
        elif isinstance(locator, CommentLocator):
            related.append(locator.post)
        elif isinstance(locator, MetricLocator):
            related.extend((locator.measured_subject, locator.definition))
        entities = [self.repository.entity(item) for item in related]
        if row["provenance_id"] != entities[0]["provenance_id"]:
            raise StorageIntegrityError("Citation provenance does not match its captured subject")
        self._validate_binding(row, locator)
        if expected_subject and locator.subject != expected_subject:
            raise ConfigurationError("Evidence does not cite the expected entity revision")
        if media_id and (
            not isinstance(locator, (MediaLocator, CreativeEventLocator))
            or locator.media.id != media_id
        ):
            raise ConfigurationError("Evidence belongs to different media")
        if post_id:
            actual_post: str | None
            if isinstance(locator, BehavioralLocator):
                data = json.loads(entities[0]["payload_json"])
                if locator.subject.kind == "metric_bin":
                    parent_row = self.repository.entity(EntityRef.model_validate(data["series"]))
                    data = json.loads(parent_row["payload_json"])
                measured = data.get("spec", {}).get("subject")
                actual_post = measured["id"] if measured and measured["kind"] == "post" else None
            elif isinstance(locator, CommentLocator):
                actual_post = locator.post.id
            elif isinstance(locator, PostTextLocator):
                actual_post = locator.subject.id
            elif isinstance(locator, ContextLocator):
                data = json.loads(entities[0]["payload_json"])
                actual_post = data["post"]["id"] if data.get("post") else None
            elif isinstance(locator, AudienceLocator):
                collection = json.loads(self.repository.entity(locator.collection)["payload_json"])
                if locator.subject.kind == "reaction_annotation":
                    reaction = json.loads(self.repository.entity(locator.subject)["payload_json"])
                    comment = self.repository.entity(
                        EntityRef.model_validate(reaction["annotation"]["comment"])
                    )
                    actual_post = json.loads(comment["payload_json"])["post_id"]
                else:
                    actual_post = (
                        post_id
                        if post_id in {p["id"] for p in collection["spec"]["posts"]}
                        else None
                    )
            elif isinstance(locator, MetricLocator):
                actual_post = (
                    locator.measured_subject.id if locator.measured_subject.kind == "post" else None
                )
            elif isinstance(locator, MediaLocator):
                links = metadata.tables["post_media"]
                actual_post = self.connection.scalar(
                    select(links.c.post_id).where(
                        links.c.post_id == post_id, links.c.media_asset_id == locator.media.id
                    )
                )
            else:
                actual_post = None
            if actual_post != post_id:
                raise ConfigurationError("Evidence does not belong to the expected post")
        if run_id:
            tasks = metadata.tables["analysis_tasks"]
            allowed = self.connection.scalar(
                select(tasks.c.id).where(
                    tasks.c.run_id == run_id,
                    or_(
                        tasks.c.id == row["producer_task_id"],
                        tasks.c.reused_from_task_id == row["producer_task_id"],
                    ),
                )
            )
            if row["producer_run_id"] != run_id and not allowed:
                raise ConfigurationError("Evidence was not produced or reused by the requested run")
        limitations: list[str] = []
        sources = {item["source_id"] for item in entities if item["source_id"]}
        if row["source_id"]:
            sources.add(row["source_id"])
        if any(is_redacted(self.connection, "source", source_id) for source_id in sources):
            limitations.append("Source was erased; new use is unavailable")
        withdrawals = metadata.tables["evidence_withdrawals"]
        reasons: list[str] = list(
            self.connection.scalars(
                select(withdrawals.c.reason).where(
                    or_(withdrawals.c.evidence_id == identity, withdrawals.c.source_id.in_(sources))
                )
            )
        )
        if reasons:
            limitations.extend("withdrawn: " + reason for reason in reasons)
        if row["producer_task_id"]:
            inputs = metadata.tables["inference_inputs"]
            dependency_ids: list[str] = list(
                self.connection.scalars(
                    select(inputs.c.evidence_id).where(inputs.c.task_id == row["producer_task_id"])
                )
            )
            for dependency_id in dependency_ids:
                dependency = self.resolve(
                    dependency_id, as_of=as_of, _ancestors=_ancestors | {row["id"]}, _memo=memo
                )
                if not dependency.eligible:
                    limitations.append(f"Derived input {dependency_id} is ineligible")
        if not row["source_id"]:
            limitations.append(
                "Source authority is unknown; citation is ineligible for a new claim"
            )
        source = self.repository.get("source_records", row["source_id"]) if row["source_id"] else {}
        if row["source_id"] and not str(source.get("permission_basis", "")).strip():
            limitations.append("Source permission basis is absent")
        if isinstance(locator, CommentLocator) and source.get("source_kind") == "tabular_export":
            if not json.loads(source["terms_json"]).get("comments_permitted"):
                limitations.append("Source does not permit comment reuse")
        if isinstance(locator, MetricLocator) and locator.availability != "available":
            limitations.append(f"Metric is {locator.availability}: {locator.reason}")
        if isinstance(locator, (StudyLocator, ResearchLocator)):
            from socialdna.storage.research_repository import active as research_active

            try:
                research_dependencies = research_active(self.connection, locator.subject, as_of)
                for dependency_ref in research_dependencies:
                    dependency = self.resolve(
                        dependency_ref,
                        as_of=as_of,
                        _ancestors=_ancestors | {row["id"]},
                        _memo=memo,
                    )
                    if not dependency.eligible:
                        limitations.append("Research input is ineligible: " + dependency.ref.id)
            except ConfigurationError as exc:
                limitations.append("Research input is ineligible: " + str(exc))
        if isinstance(locator, StatisticalLocator):
            from socialdna.application.statistical_service import assert_design_inputs

            analysis = self.repository.get("statistical_analyses", locator.analysis_id)
            report = json.loads(analysis["result_json"])

            def resolve_feature(identity: str) -> None:
                dependency = self.resolve(
                    identity,
                    as_of=as_of,
                    _ancestors=_ancestors | {row["id"]},
                    _memo=memo,
                )
                if not dependency.eligible:
                    raise ConfigurationError("Ineligible feature evidence: " + identity)

            try:
                assert_design_inputs(
                    self.connection,
                    report["posts"] + report["reference_population"],
                    resolve_feature=resolve_feature,
                )
            except ConfigurationError as exc:
                limitations.append("Derived analysis input is ineligible: " + str(exc))
        if isinstance(locator, ContextLocator):
            document = json.loads(entities[0]["payload_json"])
            from socialdna.memory.documents import entity_active as memory_entity_active

            if locator.subject.kind == "platform_document":
                from socialdna.application.platform_service import active_document

                try:
                    active_document(self.connection, locator.subject)
                except ConfigurationError as exc:
                    limitations.append(str(exc))

            if locator.artifact_id and is_redacted(
                self.connection, "artifact", locator.artifact_id
            ):
                limitations.append("Context asset was erased; visual evidence is unavailable")

            for raw in document["entity_inputs"]:
                try:
                    memory_entity_active(
                        self.connection, EntityRef.model_validate(raw), as_of=as_of
                    )
                except ConfigurationError as exc:
                    limitations.append("Context entity is ineligible: " + str(exc))
            for raw in document["evidence_inputs"]:
                dependency = self.resolve(
                    EvidenceRef.model_validate(raw),
                    as_of=as_of,
                    _ancestors=_ancestors | {row["id"]},
                    _memo=memo,
                )
                if not dependency.eligible:
                    limitations.append("Context input is ineligible: " + dependency.ref.id)
        if isinstance(locator, CreativeEventLocator):
            subject = json.loads(entities[0]["payload_json"])
            dependencies = (
                [item["ref"] for item in subject["inputs"]]
                if locator.kind == "creative_event"
                else [subject["input"]]
            )
            for dependency in dependencies:
                resolved = self.resolve(
                    EvidenceRef.model_validate(dependency),
                    as_of=as_of,
                    _ancestors=_ancestors | {row["id"]},
                    _memo=memo,
                )
                if not resolved.eligible:
                    limitations.append("Creative input is ineligible: " + resolved.ref.id)
        if isinstance(locator, BehavioralLocator):
            from socialdna.storage import behavioral_repository as behavioral

            document = json.loads(entities[0]["payload_json"])
            try:
                behavioral.active(self.connection, locator.subject, as_of)
                if locator.subject.kind == "metric_bin":
                    parent = EntityRef.model_validate(document["series"])
                    if parent.revision_id not in _ancestors:
                        behavioral.active(self.connection, parent, as_of)
                    assert_active_inputs(
                        self.connection,
                        evidence_ids=(behavioral.evidence_ref(self.connection, parent).id,),
                    )
            except ConfigurationError as exc:
                limitations.append("Behavioral input is ineligible: " + str(exc))
            dependency_refs = list(document["evidence_inputs"])
            if locator.subject.kind == "metric_series":
                table = metadata.tables["metric_bins"]
                bin_revisions: list[str] = list(
                    self.connection.scalars(
                        select(table.c.revision_id).where(
                            table.c.series_revision_id == locator.subject.revision_id
                        )
                    )
                )
                for revision in bin_revisions:
                    child = self.repository.ref(self.repository.get("entity_revisions", revision))
                    dependency_refs.append(
                        behavioral.evidence_ref(self.connection, child).model_dump()
                    )
            for item in dependency_refs:
                dependency = self.resolve(
                    EvidenceRef.model_validate(item),
                    as_of=as_of,
                    _ancestors=_ancestors | {row["id"]},
                    _memo=memo,
                )
                if not dependency.eligible:
                    limitations.append(
                        "Behavioral input citation is ineligible: " + dependency.ref.id
                    )
        if isinstance(locator, AudienceLocator):
            from socialdna.storage.audience_repository import entity_active

            document = json.loads(entities[0]["payload_json"])
            collection = json.loads(self.repository.entity(locator.collection)["payload_json"])
            expires = collection["spec"]["expires_at"]
            if expires and expires <= utc_now():
                limitations.append("Audience collection retention permission has expired")
            for item in document["entity_inputs"]:
                try:
                    entity_active(self.connection, EntityRef.model_validate(item), as_of)
                except ConfigurationError as exc:
                    limitations.append("Audience input is ineligible: " + str(exc))
            for item in document["evidence_inputs"]:
                dependency = self.resolve(
                    EvidenceRef.model_validate(item),
                    as_of=as_of,
                    _ancestors=_ancestors | {row["id"]},
                    _memo=memo,
                )
                if not dependency.eligible:
                    limitations.append(
                        "Audience input citation is ineligible: " + dependency.ref.id
                    )
        if as_of:
            try:
                cutoff = timestamp(as_of)
            except ValueError as exc:
                raise ConfigurationError(str(exc)) from exc
            if row["available_at"] is None or row["available_at"] > cutoff:
                limitations.append(
                    "Evidence availability is unknown or later than the as-of cutoff"
                )
        eligible = not limitations
        if purpose == "new_claim" and not eligible:
            raise ConfigurationError("Ineligible evidence: " + "; ".join(limitations))
        result = ResolvedEvidence(
            ref=EvidenceRef(id=identity, revision_id=row["id"]),
            locator_kind=row["locator_kind"],
            subject=locator.subject,
            locator=locator if eligible else None,
            source={
                "id": row["source_id"],
                "uri": source.get("source_uri"),
                "permission_basis": source.get("permission_basis"),
            },
            provenance_id=row["provenance_id"],
            producer_run_id=row["producer_run_id"],
            producer_task_id=row["producer_task_id"],
            captured_at=row["captured_at"],
            available_at=row["available_at"],
            eligible=eligible,
            limitations=tuple(limitations),
        )
        memo[row["id"]] = result
        return result

    def _validate_binding(
        self,
        row: dict[str, Any],
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
    ) -> None:
        counts = {}
        for name in (
            "legacy_media_evidence_bindings",
            "comment_evidence_bindings",
            "metric_evidence_bindings",
            "statistical_evidence_bindings",
            "direct_media_evidence_bindings",
            "audience_evidence_bindings",
            "behavioral_evidence_bindings",
            "post_text_evidence_bindings",
            "creative_evidence_bindings",
            "study_evidence_bindings",
            "research_evidence_bindings",
            "context_evidence_bindings",
        ):
            table = metadata.tables[name]
            counts[name] = (
                self.connection.execute(
                    select(table).where(table.c.evidence_revision_id == row["id"])
                )
                .mappings()
                .first()
            )
        if sum(value is not None for value in counts.values()) != 1:
            raise StorageIntegrityError("Evidence requires exactly one typed locator binding")
        subject = json.loads(self.repository.entity(locator.subject)["payload_json"])
        if isinstance(locator, ContextLocator):
            from socialdna.storage.context_repository import validate_locator

            binding = counts["context_evidence_bindings"]
            if not binding or binding["subject_revision_id"] != locator.subject.revision_id:
                raise StorageIntegrityError("Context citation has a mismatched typed binding")
            validate_locator(self.repository, locator)
        elif isinstance(locator, StudyLocator):
            binding = counts["study_evidence_bindings"]
            source = json.loads(self.repository.entity(locator.source_document)["payload_json"])
            spec = subject.get("spec", {})
            if (
                not binding
                or locator.subject.kind != "study_finding"
                or locator.source_document.kind != "literature_source"
                or binding["finding_revision_id"] != locator.subject.revision_id
                or binding["source_revision_id"] != locator.source_document.revision_id
                or subject["source_document"] != locator.source_document.model_dump()
                or any(
                    spec.get(k) != getattr(locator, k)
                    for k in ("start_char", "end_char", "quote", "location")
                )
                or not 0
                <= locator.start_char
                < locator.end_char
                <= len(source["spec"]["source_text"])
                or source["spec"]["source_text"][locator.start_char : locator.end_char]
                != locator.quote
            ):
                raise StorageIntegrityError("Study excerpt has a mismatched source/span binding")
        elif isinstance(locator, ResearchLocator):
            binding = counts["research_evidence_bindings"]
            if (
                not binding
                or locator.subject.kind
                not in (
                    "research_assessment",
                    "research_finding",
                    "experiment_brief",
                    "discovery_search",
                    "creative_pattern",
                )
                or binding["subject_revision_id"] != locator.subject.revision_id
            ):
                raise StorageIntegrityError("Research citation has a mismatched typed binding")
        elif isinstance(locator, BehavioralLocator):
            from socialdna.storage.behavioral_repository import KINDS

            binding = counts["behavioral_evidence_bindings"]
            if (
                not binding
                or locator.subject.kind not in KINDS
                or binding["subject_revision_id"] != locator.subject.revision_id
            ):
                raise StorageIntegrityError(
                    "Behavioral citation has a wrong-kind or mismatched binding"
                )
        elif isinstance(locator, AudienceLocator):
            from socialdna.storage.audience_repository import KINDS

            binding = counts["audience_evidence_bindings"]
            if (
                not binding
                or locator.subject.kind not in KINDS
                or locator.collection.kind != "audience_collection"
                or binding["subject_revision_id"] != locator.subject.revision_id
                or binding["collection_revision_id"] != locator.collection.revision_id
            ):
                raise StorageIntegrityError(
                    "Audience citation has a wrong-kind or mismatched binding"
                )
            expected = (
                locator.subject
                if locator.subject.kind == "audience_collection"
                else EntityRef.model_validate(subject["collection"])
            )
            if expected != locator.collection:
                raise StorageIntegrityError(
                    "Audience citation refers to the wrong collection revision"
                )
        elif isinstance(locator, CreativeEventLocator):
            binding = counts["creative_evidence_bindings"]
            key = (
                "event_revision_id" if locator.kind == "creative_event" else "coverage_revision_id"
            )
            if (
                not binding
                or binding[key] != locator.subject.revision_id
                or locator.subject.kind != locator.kind
                or (subject["media"] != locator.media.model_dump() or locator.media.kind != "media")
            ):
                raise StorageIntegrityError(
                    "Creative evidence does not match its captured event/coverage"
                )
            self.repository.entity(locator.media)
        elif isinstance(locator, PostTextLocator):
            from socialdna.storage.creative_repository import post_text

            binding = counts["post_text_evidence_bindings"]
            text = post_text(self.repository, locator.subject, locator.field, locator.tag_index)
            if (
                not binding
                or binding["post_revision_id"] != locator.subject.revision_id
                or any(
                    binding[key] != getattr(locator, key)
                    for key in ("field", "tag_index", "start_char", "end_char")
                )
                or locator.end_char > len(text)
                or text[locator.start_char : locator.end_char] != locator.quote
            ):
                raise StorageIntegrityError("Post text locator does not match captured text")
        elif isinstance(locator, StatisticalLocator):
            binding = counts["statistical_evidence_bindings"]
            analysis = self.repository.get("statistical_analyses", locator.analysis_id)
            report = json.loads(analysis["result_json"])
            if (
                not binding
                or locator.subject.kind != "statistical_analysis"
                or (
                    locator.subject.id != locator.analysis_id
                    or binding["analysis_id"] != locator.analysis_id
                    or binding["result_id"] != locator.result_id
                    or binding["diagnostic"] != locator.diagnostic
                    or row["producer_run_id"] != analysis["run_id"]
                )
            ):
                raise StorageIntegrityError("Statistical locator has a mismatched analysis binding")
            if locator.result_id:
                result = self.repository.get("statistical_results", locator.result_id)
                term = next(
                    (
                        item
                        for item in report["results"]["regression"]["terms"]
                        if item["term"] == locator.term
                    ),
                    None,
                )
                if (
                    result["analysis_id"] != locator.analysis_id
                    or result["term"] != locator.term
                    or not term
                    or any(
                        result[key] != term.get(key)
                        for key in (
                            "estimate",
                            "standard_error",
                            "ci_low",
                            "ci_high",
                            "p_value",
                            "adjusted_p_value",
                        )
                    )
                ):
                    raise StorageIntegrityError("Statistical term does not match its frozen result")
            elif (
                locator.diagnostic not in report["results"]
                or report["results"][locator.diagnostic] is None
            ):
                raise StorageIntegrityError("Statistical diagnostic does not exist")
        elif isinstance(locator, CommentLocator):
            binding = counts["comment_evidence_bindings"]
            if (
                not binding
                or locator.subject.kind != "comment"
                or locator.post.kind != "post"
                or binding["comment_revision_id"] != locator.subject.revision_id
                or binding["comment_id"] != locator.subject.id
                or binding["start_char"] != locator.start_char
                or binding["end_char"] != locator.end_char
                or subject["post_id"] != locator.post.id
                or subject["body"][locator.start_char : locator.end_char] != locator.quote
                or locator.end_char > len(subject["body"])
            ):
                raise StorageIntegrityError("Comment locator does not match its captured source")
        elif isinstance(locator, MetricLocator):
            binding = counts["metric_evidence_bindings"]
            definition = json.loads(self.repository.entity(locator.definition)["payload_json"])
            measured = json.loads(self.repository.entity(locator.measured_subject)["payload_json"])
            if (
                not binding
                or locator.subject.kind != "metric_snapshot"
                or binding["metric_observation_id"] != locator.subject.id
                or binding["definition_revision_id"] != locator.definition.revision_id
                or locator.definition.kind != "metric_definition"
                or subject["metric_key"] != locator.definition.id
                or subject["subject_type"] != locator.measured_subject.kind
                or subject["subject_id"] != locator.measured_subject.id
                or definition["subject_type"] != locator.measured_subject.kind
                or definition["platform"] != measured["platform"]
                or any(
                    subject[key] != getattr(locator, key)
                    for key in (
                        "value",
                        "availability",
                        "reason",
                        "observed_at",
                        "window_start",
                        "window_end",
                    )
                )
            ):
                raise StorageIntegrityError(
                    "Metric locator does not match its captured snapshot/definition"
                )
        else:
            direct = counts["direct_media_evidence_bindings"]
            if direct:
                provenance = self.repository.get("provenance_records", row["provenance_id"])
                if (
                    locator.subject != locator.media
                    or locator.subject.kind != "media"
                    or direct["media_id"] != locator.media.id
                    or direct["media_revision_id"] != locator.media.revision_id
                    or locator.interval.end_ms > subject["duration_ms"]
                    or locator.artifact_id != subject["artifact_id"]
                    or locator.excerpt is not None
                    or provenance["source_record_id"] != row["source_id"]
                ):
                    raise StorageIntegrityError(
                        "Direct media locator does not match its captured original"
                    )
                return
            binding = counts["legacy_media_evidence_bindings"]
            if (
                not binding
                or locator.media.kind != "media"
                or binding["media_revision_id"] != locator.media.revision_id
            ):
                raise StorageIntegrityError("Media locator binding disagrees with its media")
            legacy = self.repository.get("evidence_items", binding["legacy_evidence_id"])
            task = self.repository.get("analysis_tasks", row["producer_task_id"])
            run = self.repository.get("analysis_runs", task["run_id"])
            if (
                legacy["id"] != row["evidence_id"]
                or legacy["subject_id"] != locator.subject.id
                or legacy["subject_type"] != locator.subject.kind
                or legacy["media_asset_id"] != locator.media.id
                or legacy["task_id"] != row["producer_task_id"]
                or legacy["provenance_id"] != row["provenance_id"]
                or legacy["artifact_id"] != locator.artifact_id
                or legacy["excerpt"] != locator.excerpt
                or task["run_id"] != row["producer_run_id"]
                or run["target_type"] != "media"
                or run["target_id"] != locator.media.id
                or (legacy["start_ms"], legacy["end_ms"])
                != (locator.interval.start_ms, locator.interval.end_ms)
            ):
                raise StorageIntegrityError("Media locator does not match its original evidence")
        provenance = self.repository.get("provenance_records", row["provenance_id"])
        if provenance["source_record_id"] != row["source_id"]:
            raise StorageIntegrityError("Evidence provenance/source mismatch")


class ClaimValidator:
    """R1 research gates; legacy analytics retain their original method contract."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.resolver = EvidenceResolver(connection)

    def validate_research(
        self, claim_level: str, evidence: tuple[EvidenceRef, ...]
    ) -> tuple[ResolvedEvidence, ...]:
        if claim_level not in ("hypothesis", "association") or not evidence:
            raise ConfigurationError("R7 requires evidence and cannot validate causal findings")
        resolved = tuple(self.resolver.resolve(r, purpose="new_claim") for r in evidence)
        if claim_level == "association":
            supported = False
            for item in resolved:
                if not isinstance(item.locator, StatisticalLocator) or not item.locator.result_id:
                    continue
                analysis = EvidenceRepository(self.connection).get(
                    "statistical_analyses", item.locator.analysis_id
                )
                model = json.loads(analysis["result_json"])["results"]["regression"]
                term = next((t for t in model["terms"] if t["term"] == item.locator.term), None)
                supported |= bool(
                    model["status"] == "fitted"
                    and term
                    and term.get("adjusted_p_value") is not None
                    and term["adjusted_p_value"] <= 0.05
                    and term.get("ci_low") is not None
                    and term.get("ci_high") is not None
                    and (term["ci_low"] > 0 or term["ci_high"] < 0)
                )
            if not supported:
                raise ConfigurationError("An association needs an eligible fitted statistical term")
        return resolved

    def validate(
        self,
        claim_level: str,
        evidence: tuple[EvidenceRef, ...],
        *,
        draft: bool = False,
    ) -> tuple[ResolvedEvidence, ...]:
        if claim_level not in ("observation", "hypothesis"):
            raise ConfigurationError("R1 cannot validate associations or causal research findings")
        if claim_level == "hypothesis" and not draft:
            raise ConfigurationError(
                "R1 hypotheses are registered drafts, not evaluation-ready claims"
            )
        if claim_level == "observation" and not evidence:
            raise ConfigurationError("An observation requires eligible source evidence")
        return tuple(self.resolver.resolve(ref, purpose="new_claim") for ref in evidence)


def assert_active_inputs(
    connection: Connection,
    *,
    source_ids: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = (),
) -> None:
    """Privacy gate for legacy producers; does not reinterpret their statistics."""
    from socialdna.storage.audience_retention import guard

    for identity in source_ids:
        guard(connection, "source", identity)
    if evidence_ids:
        evidence = metadata.tables["evidence_revisions"]
        for identity in connection.scalars(
            select(evidence.c.id).where(evidence.c.evidence_id.in_(evidence_ids))
        ):
            guard(connection, "evidence_revision", identity)
    table = metadata.tables["evidence_withdrawals"]
    reason = connection.scalar(
        select(table.c.reason).where(
            or_(table.c.source_id.in_(source_ids), table.c.evidence_id.in_(evidence_ids))
        )
    )
    if reason:
        raise ConfigurationError("Withdrawn input cannot support a new analysis/report: " + reason)


def assert_media_active(connection: Connection, media_id: str) -> None:
    locations = metadata.tables["media_locations"]
    sources: tuple[str, ...] = tuple(
        connection.scalars(
            select(locations.c.source_record_id).where(locations.c.media_asset_id == media_id)
        )
    )
    evidence = metadata.tables["evidence_items"]
    ids: tuple[str, ...] = tuple(
        connection.scalars(select(evidence.c.id).where(evidence.c.media_asset_id == media_id))
    )
    assert_active_inputs(connection, source_ids=sources, evidence_ids=ids)


def assert_context_active(connection: Connection, subject_ids: tuple[str, ...]) -> None:
    """Fail closed for merged legacy metadata without per-field source lineage."""
    links, provenance = (
        metadata.tables[name] for name in ("provenance_links", "provenance_records")
    )
    sources: tuple[str, ...] = tuple(
        connection.scalars(
            select(provenance.c.source_record_id)
            .join(links, links.c.provenance_id == provenance.c.id)
            .where(
                links.c.entity_type.in_(("post", "account")),
                links.c.entity_id.in_(subject_ids),
                provenance.c.source_record_id.is_not(None),
            )
        )
    )
    assert_active_inputs(connection, source_ids=sources)


def withdraw(
    connection: Connection,
    *,
    source_id: str | None = None,
    evidence_id: str | None = None,
    reason: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    """Revoke new use, without claiming to erase retained historical bytes."""
    if bool(source_id) == bool(evidence_id) or not reason.strip() or not actor.strip():
        raise ConfigurationError(
            "Specify exactly one source/evidence identity and a nonempty reason/actor"
        )
    repository = EvidenceRepository(connection)
    repository.get(
        "source_records" if source_id else "evidence_records", source_id or evidence_id or ""
    )
    identity = stable_id(
        "withdrawal", "source" if source_id else "evidence", source_id or evidence_id or ""
    )
    table = metadata.tables["evidence_withdrawals"]
    connection.execute(
        insert(table)
        .values(
            id=identity,
            source_id=source_id,
            evidence_id=evidence_id,
            reason=reason.strip(),
            actor=actor.strip(),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    return {
        **repository.get("evidence_withdrawals", identity),
        "retained_bytes_erased": False,
        "limitations": ["Withdrawal blocks new citation use; it is not a full erasure operation."],
    }
