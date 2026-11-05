"""Offline publication snapshots, qualified cadence and frozen context reports."""

import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.application.bootstrap import Application, open_application
from socialdna.application.evidence_service import EvidenceResolver, assert_active_inputs
from socialdna.application.performance_service import load_performance_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.domain.context import (
    ContextExport,
    PublicationContext,
    PublicationReportSpec,
    PublishingWindow,
)
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.ingestion.tabular import timestamp
from socialdna.storage import context_repository as repository
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata

T = TypeVar("T", bound=BaseModel)


def capture_image(
    app: Application,
    connection: Any,
    path: Path,
    sha256: str,
    *,
    variant: str,
    placement: str,
    kind: str = "thumbnail",
    base: Path | None = None,
) -> dict[str, str]:
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    try:
        with path.open("rb") as stream:
            content = stream.read(10_000_001)
    except OSError as exc:
        raise ConfigurationError("Cannot read explicitly supplied image") from exc
    if len(content) > 10_000_000 or hashlib.sha256(content).hexdigest() != sha256:
        raise ConfigurationError("Image byte limit/hash mismatch")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ("PNG", "JPEG", "WEBP"):
                raise ConfigurationError("Only PNG/JPEG/WebP assets are supported")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ConfigurationError("Invalid or oversized supplied image") from exc
    artifact = app.artifacts.put_bytes(
        connection, content, kind=kind, mime_type="application/octet-stream"
    )
    return {"variant": variant, "placement": placement, "sha256": sha256, "artifact_id": artifact}


PUBLICATION_RECIPES = {
    "publication.local_clock.v1": {
        "version": "1.0",
        "operation": "supplied_IANA_zone_hour_weekday_fold",
        "offset": "original_supplied_seconds",
        "missing_zone": "preserve_unknown",
    },
    "publication.cadence.v1": {
        "version": "1.0",
        "operation": "unique_inventory_posts_per_elapsed_UTC_day",
        "window": "half_open",
        "requires": "complete_including_deleted_and_omitted",
        "incomplete": "preserve_unknown",
    },
}


def register_recipes(connection: Any) -> dict[str, str]:
    table = metadata.tables["feature_recipes"]
    result = {}
    for key, definition in PUBLICATION_RECIPES.items():
        connection.execute(
            insert(table)
            .values(
                id=key, version="1.0", spec_json=canonical_json(definition), available_at=utc_now()
            )
            .on_conflict_do_nothing()
        )
        row = connection.execute(select(table).where(table.c.id == key)).mappings().one()
        if row["spec_json"] != canonical_json(definition):
            raise StorageIntegrityError("Publication recipe changed without a new pin")
        result[key] = row["available_at"]
    return result


def read_spec(path: Path, model: type[T]) -> T:
    try:
        with path.open("rb") as stream:
            raw = stream.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("Context document exceeds 4 MB")
        return model.model_validate_json(raw)
    except (ValueError, OSError) as exc:
        raise ConfigurationError(f"Invalid context document: {exc}") from exc


def provenance(
    connection: Any, payload: dict[str, Any], uri: str, permission: str
) -> tuple[str, str]:
    if not permission.strip():
        raise ConfigurationError("Context permission cannot be blank")
    digest = hash_config(payload)
    source, identity = stable_id("context-source", digest), stable_id("context-provenance", digest)
    assert_active_inputs(connection, source_ids=(source,))
    connection.execute(
        insert(metadata.tables["source_records"])
        .values(
            id=source,
            source_kind="context_import",
            source_uri=uri,
            permission_basis=permission,
            terms_json="{}",
            retrieved_at=utc_now(),
            content_hash=digest,
        )
        .on_conflict_do_nothing()
    )
    connection.execute(
        insert(metadata.tables["provenance_records"])
        .values(
            id=identity,
            source_record_id=source,
            method="versioned-context-1",
            tool_name="socialdna",
            tool_version=__version__,
            config_json=canonical_json({"input_hash": digest}),
            created_at=utc_now(),
        )
        .on_conflict_do_nothing()
    )
    return source, identity


def import_document(settings: Settings, path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    spec = read_spec(path, ContextExport)
    if dry_run:
        return {
            "valid": True,
            "written": False,
            "record_count": len(spec.records),
            "limitations": [
                "Schema only; ownership, bytes and source completeness checked on import."
            ],
        }
    with open_application(settings) as app:
        return import_into_application(app, spec, base=path.parent)


def import_into_application(
    app: Application, spec: ContextExport, *, base: Path | None = None
) -> dict[str, Any]:
    raw = spec.model_dump(mode="json")
    with app.database.transaction() as connection:
        register_recipes(connection)
        source, producer = provenance(connection, raw, spec.source_uri, spec.permission_basis)
        repo = EvidenceRepository(connection)
        results = []
        for record in spec.records:
            data = record.model_dump(mode="json")
            entities: tuple[EntityRef, ...] = ()
            artifacts = []
            if isinstance(record, PublicationContext):
                post = json.loads(repo.entity(record.post)["payload_json"])
                if post["published_at"] != timestamp(record.published_original):
                    raise ConfigurationError("Publication timestamp differs from captured post")
                thumbnails = []
                for item in record.thumbnails:
                    asset = capture_image(
                        app,
                        connection,
                        Path(item.path),
                        item.sha256,
                        variant=item.variant,
                        placement=item.placement,
                        base=base,
                    )
                    artifacts.append(asset["artifact_id"])
                    thumbnails.append(asset)
                data["thumbnails"] = thumbnails
            elif isinstance(record, PublishingWindow):
                for ref in record.posts:
                    post = json.loads(repo.entity(ref)["payload_json"])
                    if (
                        post["account_id"] != record.account.id
                        or not (
                            post["published_at"]
                            and record.window_start <= post["published_at"] < record.window_end
                        )
                        or post["content_type"] not in record.formats
                    ):
                        raise ConfigurationError(
                            "Window member has wrong ownership, format or date"
                        )
                entities = record.posts
                posts = metadata.tables["posts"]
                known: set[str] = set(
                    connection.scalars(
                        select(posts.c.id).where(
                            posts.c.account_id == record.account.id,
                            posts.c.published_at >= record.window_start,
                            posts.c.published_at < record.window_end,
                            posts.c.content_type.in_(record.formats),
                        )
                    )
                )
                if record.complete and known - {r.id for r in record.posts}:
                    raise ConfigurationError("Complete publishing window omits known posts")
            else:
                account = json.loads(repo.entity(record.account)["payload_json"])
                if account["platform"] != record.platform:
                    raise ConfigurationError("Trend platform differs from scoped account")
            ref = repository.save(
                connection,
                record.record_type,
                spec.dataset_id + ":" + record.key,
                data,
                producer,
                account=record.account,
                post=record.post if isinstance(record, PublicationContext) else None,
                entities=entities,
            )
            citation = repository.cite(connection, ref)
            EvidenceResolver(connection).resolve(citation, purpose="new_claim")
            for artifact in artifacts:
                app.artifacts.add_reference(
                    connection,
                    artifact,
                    owner_type="context",
                    owner_id=ref.revision_id,
                    role="thumbnail",
                )
            results.append({"ref": ref.model_dump(), "evidence": citation.model_dump()})
        artifact = app.artifacts.put_bytes(
            connection,
            canonical_json(raw).encode(),
            kind="context-source",
            mime_type="application/json",
        )
        app.artifacts.add_reference(
            connection, artifact, owner_type="context_source", owner_id=source, role="raw"
        )
        connection.execute(
            metadata.tables["source_records"]
            .update()
            .where(metadata.tables["source_records"].c.id == source)
            .values(raw_artifact_id=artifact)
        )
        return {"valid": True, "written": True, "source_id": source, "records": results}


def show(app: Application, identity: str, *, revision: str | None = None) -> dict[str, Any]:
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        table = metadata.tables["entity_revisions"]
        query = select(table).where(
            table.c.entity_id == identity, table.c.kind.in_(repository.KINDS)
        )
        if revision:
            query = query.where(table.c.id == revision)
        captures = metadata.tables["context_records"]
        query = query.join(captures, captures.c.revision_id == table.c.id)
        row = (
            connection.execute(
                query.order_by(
                    case(
                        (table.c.kind == "profile_snapshot", captures.c.captured_at), else_=""
                    ).desc(),
                    table.c.revision_no.desc(),
                ).limit(1)
            )
            .mappings()
            .first()
        )
        if not row:
            raise ConfigurationError("Unknown context identity/revision")
        ref = repo.ref(dict(row))
        return {
            "ref": ref.model_dump(),
            "content": repository.read(connection, ref),
            "evidence": repository.cite(connection, ref).model_dump(),
        }


def publication_report(app: Application, spec: PublicationReportSpec) -> dict[str, Any]:
    if spec.as_of > utc_now():
        raise ConfigurationError("Context cutoff cannot be in the future")
    analysis = (
        load_performance_report(app, run_id=spec.analysis_run_id) if spec.analysis_run_id else None
    )
    with app.database.transaction() as connection:
        rows, inputs, citations = [], [], []
        recipe_times = register_recipes(connection)
        if any(value > spec.as_of for value in recipe_times.values()):
            raise ConfigurationError("Publication recipe was unavailable at the cutoff")
        account = None
        platforms: set[str] = set()
        for ref in spec.publications:
            if ref.kind != "publication_context":
                raise ConfigurationError("Publication report needs actual publication contexts")
            payload = repository.read(connection, ref, spec.as_of)
            data = payload["spec"]
            current = EntityRef.model_validate(payload["account"])
            if account and account.id != current.id:
                raise ConfigurationError("Publishing reports use one explicit account scope")
            account = current
            post = json.loads(
                EvidenceRepository(connection).entity(EntityRef.model_validate(payload["post"]))[
                    "payload_json"
                ]
            )
            platforms.add(post["platform"])
            pub = datetime.fromisoformat(data["published_original"].replace("Z", "+00:00"))
            local = pub.astimezone(ZoneInfo(data["timezone"])) if data["timezone"] else None
            offset = pub.utcoffset()
            assert offset is not None
            available = EvidenceRepository(connection).entity(ref)["available_at"]
            if spec.policy == "historical_prediction" and available > timestamp(
                data["published_original"]
            ):
                raise ConfigurationError("Metadata was not known at the publication decision")
            rows.append(
                {
                    "post": payload["post"],
                    "context": ref.model_dump(),
                    "recipe": "publication.local_clock.v1",
                    "local_hour": local.hour if local else None,
                    "local_weekday": local.weekday() if local else None,
                    "utc_offset_seconds": offset.total_seconds(),
                    "dst_fold": local.fold if local else None,
                    "available_at": available,
                    "historical_packaging_validity": data["clock"]["validity_basis"],
                }
            )
            inputs.append(ref)
            citations.append(repository.cite(connection, ref))
        assert account is not None
        cadence: dict[str, Any] = {
            "recipe": "publication.cadence.v1",
            "value": None,
            "reason": "no_complete_window",
        }
        if spec.window:
            if spec.window.kind != "publishing_window":
                raise ConfigurationError("Cadence needs a publishing-window revision")
            window = repository.read(connection, spec.window, spec.as_of)
            if window["account"]["id"] != account.id:
                raise ConfigurationError("Publishing window belongs to a different account")
            data = window["spec"]
            if data["complete"] and data["includes_deleted_and_omitted"]:
                days = (
                    datetime.fromisoformat(data["window_end"])
                    - datetime.fromisoformat(data["window_start"])
                ).total_seconds() / 86400
                cadence.update(
                    value=len(data["posts"]) / days,
                    unit="posts_per_elapsed_day",
                    reason="source_attested_complete_inventory",
                )
            inputs.append(spec.window)
            citations.append(repository.cite(connection, spec.window))
        trends = []
        for ref in spec.trends:
            if ref.kind != "trend_context":
                raise ConfigurationError("Expected a dated trend context")
            trend = repository.read(connection, ref, spec.as_of)
            data = trend["spec"]
            if (
                trend["account"]["id"] != account.id
                or data["platform"] not in platforms
                or data["objective"] != spec.objective
                or data["surface"] != spec.surface
            ):
                raise ConfigurationError("Trend account/platform/objective/surface mismatch")
            if any(
                data["observation_end"] > timestamp(r["spec"]["published_original"])
                for r in [repository.read(connection, item) for item in spec.publications]
            ):
                raise ConfigurationError("Future trend evidence cannot explain a past decision")
            trends.append(
                {
                    "ref": ref.model_dump(),
                    "basis": data["basis"],
                    "query": data["query"],
                    "observation": data["observation"],
                }
            )
            inputs.append(ref)
            citations.append(repository.cite(connection, ref))
        comparison = None
        if analysis:
            if analysis["analysis_configuration"].get("method_version") != "performance-2":
                raise ConfigurationError("Context comparison requires a frozen version-2 analysis")
            by_post = {row["post_id"]: row for row in analysis["posts"]}
            if set(by_post) != {r["post"]["id"] for r in rows}:
                raise ConfigurationError("Context and outcome populations must match exactly")
            if analysis["analysis_configuration"]["spec"]["knowledge_cutoff"] > spec.as_of:
                raise ConfigurationError("Analysis was not available at the context cutoff")
            for raw in analysis["statistical_evidence"]:
                citation = EvidenceRef.model_validate(raw["ref"])
                EvidenceResolver(connection).resolve(
                    citation, purpose="new_claim", as_of=spec.as_of
                )
                citations.append(citation)
            for row in rows:
                outcome = by_post[row["post"]["id"]]
                row["outcome"] = outcome["outcome"]
                row["outcome_availability"] = outcome["availability"]
            comparison = {
                "run_id": analysis["run_id"],
                "declared_outcome_mapping": spec.outcome_mapping_basis,
                "results": analysis["results"]["comparison"],
                "new_context_effect_estimated": False,
            }
        result = {
            "objective": spec.objective,
            "channel_status": "declared_objective_not_verified_traffic",
            "recipes": {key: dict(value) for key, value in PUBLICATION_RECIPES.items()},
            "recipe_available_at": recipe_times,
            "surface": spec.surface,
            "rows": rows,
            "cadence": cadence,
            "trends": trends,
            "comparison": comparison,
            "limitations": [
                "Context/outcome alignment is descriptive; no optimal posting time, search rank "
                "or causal growth effect is estimated.",
                "Field capture does not establish historical exposure. "
                "Static visual interpretation requires U1.",
            ],
        }
        return freeze_report(
            app,
            connection,
            account,
            spec.model_dump(mode="json"),
            result,
            tuple(inputs),
            tuple(citations),
            uri="urn:socialdna:publication-report",
        )


def freeze_report(
    app: Application,
    connection: Any,
    account: EntityRef,
    spec: dict[str, Any],
    result: dict[str, Any],
    entities: tuple[EntityRef, ...],
    evidence: tuple[EvidenceRef, ...],
    *,
    uri: str,
) -> dict[str, Any]:
    source, producer = provenance(
        connection,
        {"spec": spec, "result": result},
        uri,
        "user_authorized_context_analysis",
    )
    ref = repository.save(
        connection,
        "context_report",
        hash_config(result),
        spec,
        producer,
        account=account,
        entities=entities,
        evidence=evidence,
        result=result,
    )
    citation = repository.cite(connection, ref)
    artifact = app.artifacts.put_bytes(
        connection,
        canonical_json(result).encode(),
        kind="context-report",
        mime_type="application/json",
    )
    app.artifacts.add_reference(
        connection, artifact, owner_type="context", owner_id=ref.revision_id, role="report"
    )
    return {
        "ref": ref.model_dump(),
        "source_id": source,
        "evidence": citation.model_dump(),
        "artifact_id": artifact,
        "result": result,
    }
