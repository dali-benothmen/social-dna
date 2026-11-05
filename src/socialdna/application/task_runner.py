import json
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import InvalidMedia, ProviderFailure
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import format_utc, utc_now
from socialdna.storage.schema import metadata


class TaskRunner:
    def __init__(self, application: Application, run_id: str, media_id: str) -> None:
        self.application, self.run_id, self.media_id = application, run_id, media_id
        self.results: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}

    def run(
        self,
        key: str,
        configuration: dict[str, Any],
        dependencies: list[str],
        compute: Callable[[TaskContext], TaskOutput],
        *,
        allow_partial: bool = False,
    ) -> None:
        tasks, results = metadata.tables["analysis_tasks"], metadata.tables["analysis_task_results"]
        fingerprint = hash_config(
            {
                "analyzer": key,
                "version": "1",
                "media": self.media_id,
                "configuration": configuration,
                "dependencies": [self.tasks[name]["fingerprint"] for name in dependencies],
            }
        )
        task_id = stable_id("task", self.run_id, key)
        provenance_id = stable_id("provenance", task_id)
        with self.application.database.transaction() as connection:
            existing = (
                connection.execute(select(tasks).where(tasks.c.id == task_id)).mappings().first()
            )
            if existing and existing["fingerprint"] != fingerprint:
                raise InvalidMedia(
                    f"Task configuration or tool versions changed for {key}; "
                    "start a new run instead of resuming immutable evidence."
                )
            connection.execute(
                insert(tasks)
                .values(
                    id=task_id,
                    run_id=self.run_id,
                    task_key=key,
                    fingerprint=fingerprint,
                    analyzer=key,
                    analyzer_version="1",
                )
                .on_conflict_do_nothing()
            )
            for name in dependencies:
                connection.execute(
                    insert(metadata.tables["analysis_task_dependencies"])
                    .values(task_id=task_id, depends_on_id=self.tasks[name]["id"])
                    .on_conflict_do_nothing()
                )
            cached = (
                connection.execute(
                    select(tasks, results.c.result_json)
                    .join(results)
                    .where(tasks.c.fingerprint == fingerprint, tasks.c.status == "succeeded")
                    .order_by(tasks.c.id)
                )
                .mappings()
                .first()
            )
            if existing and existing["status"] == "skipped":
                cached = None  # skipped dependencies are cheap and are evaluated again on resume
            blocked = [
                name
                for name in dependencies
                if self.tasks[name]["status"] == "failed"
                or self.results[name].get("reason", "").startswith("Blocked by")
            ]
            if (
                cached
                and (not blocked or allow_partial)
                and self._artifacts_valid(connection, json.loads(cached["result_json"]))
            ):
                producer = cached["reused_from_task_id"] or cached["id"]
                result = json.loads(cached["result_json"])
                connection.execute(
                    tasks.update()
                    .where(tasks.c.id == task_id)
                    .values(
                        status="succeeded",
                        reused_from_task_id=producer if producer != task_id else None,
                        lease_owner=None,
                        lease_expires_at=None,
                        error_json="{}",
                    )
                )
                self.tasks[key] = {
                    "id": task_id,
                    "producer_id": producer,
                    "fingerprint": fingerprint,
                    "status": "cached",
                }
                self.results[key] = result
                return
            # Failed tasks own no committed output; successful evidence remains immutable.
            connection.execute(
                tasks.update()
                .where(tasks.c.id == task_id)
                .values(
                    status="running",
                    attempt_count=tasks.c.attempt_count + 1,
                    reused_from_task_id=None,
                    lease_owner=str(os.getpid()),
                    lease_expires_at=format_utc(datetime.now(UTC) + timedelta(hours=1)),
                )
            )
        context = TaskContext(task_id, self.media_id, provenance_id)
        try:
            output = (
                TaskOutput(skipped=f"Blocked by failed dependencies: {blocked}")
                if blocked and not allow_partial
                else compute(context)
            )
            if output.provider and not output.skipped and not output.input_evidence_ids:
                raise ProviderFailure("Model outputs require a non-empty input evidence list.")
            if (
                output.records
                and not output.skipped
                and output.provider is None
                and (configuration.get("identity") or configuration.get("profile"))
            ):
                raise ProviderFailure("Configured model outputs require provider provenance.")
            with self.application.database.transaction() as connection:
                if output.provider and not output.skipped:
                    evidence = metadata.tables["evidence_items"]
                    verified: set[str] = set(
                        connection.scalars(
                            select(evidence.c.id).where(
                                evidence.c.id.in_(output.input_evidence_ids),
                                evidence.c.media_asset_id == self.media_id,
                            )
                        )
                    )
                    if verified != set(output.input_evidence_ids):
                        raise ProviderFailure(
                            "Model input evidence must belong to the analyzed media."
                        )
                locations = metadata.tables["media_locations"]
                sources = metadata.tables["source_records"]
                source_id = connection.scalar(
                    select(sources.c.id)
                    .join(locations)
                    .where(locations.c.media_asset_id == self.media_id)
                    .order_by(sources.c.id)
                    .limit(1)
                )
                connection.execute(
                    insert(metadata.tables["provenance_records"])
                    .values(
                        id=provenance_id,
                        method=key,
                        tool_name="socialdna",
                        tool_version=__version__,
                        source_record_id=source_id,
                        provider_name=output.provider.provider if output.provider else None,
                        model_name=output.provider.model if output.provider else None,
                        model_revision=output.provider.revision if output.provider else None,
                        prompt_hash=output.prompt_hash,
                        config_json=canonical_json({**configuration, "fingerprint": fingerprint}),
                        created_at=utc_now(),
                    )
                    .on_conflict_do_nothing()
                )
                artifacts = {}
                for name, (path, kind, mime) in output.blobs.items():
                    artifact_id = self.application.artifacts.put_file(
                        connection, path, kind=kind, mime_type=mime
                    )
                    artifacts[f"@artifact:{name}"] = artifact_id
                    self.application.artifacts.add_reference(
                        connection,
                        artifact_id,
                        owner_type="analysis_task",
                        owner_id=task_id,
                        role=name,
                    )

                def substitute(value: Any) -> Any:
                    if isinstance(value, str):
                        return artifacts.get(value, value)
                    if isinstance(value, list):
                        return [substitute(item) for item in value]
                    if isinstance(value, dict):
                        return {name: substitute(item) for name, item in value.items()}
                    return value

                # Canonical rows and task completion commit together.
                for name, rows in output.records.items():
                    table = metadata.tables[name]
                    for row in rows:
                        statement = insert(table).values(**substitute(row))
                        connection.execute(statement.on_conflict_do_nothing())
                for evidence_id in sorted(set(output.input_evidence_ids)):
                    connection.execute(
                        insert(metadata.tables["inference_inputs"])
                        .values(task_id=task_id, evidence_id=evidence_id)
                        .on_conflict_do_nothing()
                    )
                from socialdna.storage.evidence_repository import EvidenceRepository

                evidence_repository = EvidenceRepository(connection)
                for evidence_row in output.records.get("evidence_items", []):
                    evidence_repository.media_evidence(evidence_row["id"], legacy=False)
                result = substitute(output.result)
                if output.creative_annotation is not None:
                    from socialdna.storage.creative_repository import persist_annotations

                    creative = persist_annotations(
                        connection,
                        self.media_id,
                        output.creative_annotation,
                        provenance_id,
                        run_id=self.run_id,
                        task_id=task_id,
                    )
                    result.update(
                        creative_annotation_ref=creative["ref"],
                        creative_event_count=len(creative["events"]),
                    )
                result["artifacts"] = list(artifacts.values())
                result["producer_task_id"] = task_id
                if output.skipped:
                    result["reason"] = output.skipped
                connection.execute(
                    insert(results)
                    .values(
                        task_id=task_id,
                        result_json=canonical_json(result),
                        provenance_id=provenance_id,
                    )
                    .on_conflict_do_update(
                        index_elements=[results.c.task_id],
                        set_={"result_json": canonical_json(result)},
                    )
                )
                status = "skipped" if output.skipped else "succeeded"
                connection.execute(
                    tasks.update()
                    .where(tasks.c.id == task_id)
                    .values(status=status, lease_owner=None, lease_expires_at=None, error_json="{}")
                )
            self.results[key] = result
            self.tasks[key] = {
                "id": task_id,
                "producer_id": task_id,
                "fingerprint": fingerprint,
                "status": status,
            }
        except Exception as exc:
            with self.application.database.transaction() as connection:
                connection.execute(
                    tasks.update()
                    .where(tasks.c.id == task_id)
                    .values(
                        status="failed",
                        lease_owner=None,
                        lease_expires_at=None,
                        error_json=canonical_json(
                            {"type": type(exc).__name__, "message": str(exc)}
                        ),
                    )
                )
            self.tasks[key] = {
                "id": task_id,
                "producer_id": task_id,
                "fingerprint": fingerprint,
                "status": "failed",
                "error": str(exc),
            }
            self.results[key] = {}

    def _artifacts_valid(self, connection: Any, result: dict[str, Any]) -> bool:
        for artifact_id in result.get("artifacts", []):
            try:
                if not self.application.artifacts.verify(
                    self.application.artifacts.get(connection, artifact_id)
                ):
                    return False
            except Exception:
                return False
        return True
