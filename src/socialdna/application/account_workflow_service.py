"""Pinned, resumable account studies over independently permitted library observations.

No platform pagination is implied by local enumeration. Native collection is a
separate unimplemented access route; ordinary posts and unsupported media remain
visible in the bounded study instead of being filtered by performance.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import url2pathname

from sqlalchemy import select

from socialdna.application.bootstrap import Application
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, SocialDNAError, StorageIntegrityError
from socialdna.core.hashing import hash_config
from socialdna.domain.account_study import AccountStudy, AccountStudyPost
from socialdna.domain.evidence import EntityRef
from socialdna.domain.research import ResearchRegistration
from socialdna.domain.workflows import AccountPostInput, MediaInput, WorkflowPlan, WorkflowRequest
from socialdna.ingestion.urls import URLTarget, parse_url
from socialdna.memory.documents import entity_active
from socialdna.reporting.markdown import escape
from socialdna.storage import content_repository as records
from socialdna.storage import context_repository as contexts
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot
from socialdna.storage.schema import metadata

CONTEXT_KINDS = {
    "profile_snapshot",
    "profile_review",
    "funnel_context",
    "publication_context",
    "publishing_window",
    "trend_context",
    "platform_document",
    "platform_statement",
    "platform_capabilities",
    "distribution_observation",
    "context_report",
}


def _ref(row: sqlite3.Row) -> EntityRef:
    return EntityRef(kind=row["kind"], id=row["entity_id"], revision_id=row["id"])


def pin(settings: Settings, request: WorkflowRequest, target: URLTarget) -> dict[str, Any]:
    try:
        return _pin(settings, request, target)
    except sqlite3.Error:
        raise ConfigurationError("Cannot inspect an initialized account library") from None


def _pin(settings: Settings, request: WorkflowRequest, target: URLTarget) -> dict[str, Any]:
    """Immutable snapshot reads, including --dry-run. Never initializes the library."""
    from socialdna.application.content_workflow_service import inputs

    database = DataPaths(settings.data_dir).database
    if target.kind != "account" or not database.is_file():
        return {"supported": False}
    with immutable_snapshot(database) as connection:
        connection.row_factory = sqlite3.Row
        if request.account_external_id:
            candidates = connection.execute(
                "SELECT id FROM accounts WHERE platform=? AND external_id=?",
                (target.platform, request.account_external_id),
            ).fetchall()
            alias = None
        else:
            alias = target.external_id.removeprefix("channel/").removeprefix("@")
            # Historic aliases come from actual immutable independent captures, not
            # guessing IDs from URL handles. Reassigned aliases are ambiguous.
            candidates = connection.execute(
                "SELECT DISTINCT a.id FROM accounts a LEFT JOIN entity_revisions e "
                "ON e.kind='account' AND e.entity_id=a.id WHERE a.platform=? AND "
                "(a.external_id=? OR "
                "lower(ltrim(json_extract(e.payload_json,'$.handle'),'@'))=lower(?))",
                (target.platform, alias, alias),
            ).fetchall()
        if not candidates:
            return {"supported": False}
        if len(candidates) != 1:
            raise ConfigurationError(
                "Ambiguous account alias; supply the observed stable --account-external-id"
            )
        account_id = candidates[0][0]
        account_row = connection.execute(
            "SELECT * FROM entity_revisions WHERE kind='account' AND entity_id=? "
            "ORDER BY revision_no DESC LIMIT 1",
            (account_id,),
        ).fetchone()
        if account_row is None:
            raise ConfigurationError("Account has no canonical source capture")
        identity_inputs: tuple[EntityRef, ...] = ()
        if alias is not None:
            alias_row = connection.execute(
                "SELECT * FROM entity_revisions WHERE kind='account' AND entity_id=? "
                "AND (json_extract(payload_json,'$.external_id')=? OR "
                "lower(ltrim(json_extract(payload_json,'$.handle'),'@'))=lower(?)) "
                "ORDER BY revision_no DESC LIMIT 1",
                (account_id, alias, alias),
            ).fetchone()
            if alias_row is None:
                raise ConfigurationError("No exact account identity observation")
            identity_inputs = (_ref(alias_row),)
        if (
            target.platform == "youtube"
            and target.external_id.startswith("channel/")
            and json.loads(account_row["payload_json"])["external_id"]
            != target.external_id.removeprefix("channel/")
        ):
            raise ConfigurationError("Stable account identity differs from its channel URL")
        # One current canonical revision per post, sorted by publication, never by views.
        query = (
            " FROM entity_revisions e WHERE e.kind='post' AND "
            "json_extract(e.payload_json,'$.account_id')=? AND NOT EXISTS "
            "(SELECT 1 FROM entity_revisions n WHERE n.kind=e.kind "
            "AND n.entity_id=e.entity_id AND n.revision_no>e.revision_no)"
        )
        count = connection.execute("SELECT count(*)" + query, (account_id,)).fetchone()[0]
        rows = connection.execute(
            "SELECT e.*"
            + query
            + " ORDER BY json_extract(e.payload_json,'$.published_at') DESC,e.entity_id LIMIT ?",
            (account_id, request.max_posts),
        ).fetchall()
        posts = []
        total_bytes = 0
        for row in rows:
            media: tuple[MediaInput, ...] = ()
            sources: tuple[EntityRef, ...] = ()
            reason: str | None = "Media analysis not requested"
            if request.analyze_media:
                refs = connection.execute(
                    "SELECT e.* FROM entity_revisions e WHERE e.kind='post_media_input' "
                    "AND json_extract(e.payload_json,'$.post.id')=? AND NOT EXISTS "
                    "(SELECT 1 FROM entity_revisions n WHERE n.kind=e.kind "
                    "AND n.entity_id=e.entity_id AND n.revision_no>e.revision_no) "
                    "ORDER BY json_extract(e.payload_json,'$.position') LIMIT 21",
                    (row["entity_id"],),
                ).fetchall()
                payload = json.loads(row["payload_json"])
                try:
                    if not refs:
                        raise ConfigurationError("No supplied local media references")
                    if len(refs) > 20:
                        raise ConfigurationError(
                            "More than twenty media items; explicit narrower input required"
                        )
                    positions = [json.loads(r["payload_json"])["position"] for r in refs]
                    if positions != list(range(len(refs))):
                        raise ConfigurationError(
                            "Media positions are incomplete; no silent carousel compaction"
                        )
                    paths = []
                    for item in refs:
                        uri = urlparse(json.loads(item["payload_json"])["uri"])
                        if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
                            raise ConfigurationError("Remote media reference only; no downloader")
                        paths.append(str(Path(url2pathname(uri.path))))
                    url = parse_url(payload.get("url") or "")
                    if (
                        url.platform != target.platform
                        or url.kind != "post"
                        or url.external_id != payload["external_id"]
                    ):
                        raise ConfigurationError(
                            "Stored post URL does not match its source identity"
                        )
                    media, _ = inputs(
                        settings,
                        WorkflowRequest(
                            mode="analyze",
                            url=url.canonical_url,
                            media=tuple(paths),
                            permission_basis=request.permission_basis,
                            analysis_options=request.analysis_options,
                        ),
                    )
                    total_bytes += sum(Path(item.path).stat().st_size for item in media)
                    if total_bytes > settings.max_media_bytes:
                        raise ConfigurationError(
                            "Selected account originals exceed the combined byte budget"
                        )
                    sources, reason = tuple(_ref(item) for item in refs), None
                except SocialDNAError as exc:
                    media, sources, reason = (), (), str(exc)
            posts.append(
                AccountPostInput(
                    post=_ref(row), media=media, media_sources=sources, media_reason=reason
                )
            )
        context_inputs = []
        for revision in request.context_revisions:
            row = connection.execute(
                "SELECT * FROM entity_revisions WHERE id=?", (revision,)
            ).fetchone()
            if row is None or row["kind"] not in CONTEXT_KINDS:
                raise ConfigurationError("Select actual supported C1 context revisions")
            raw = json.loads(row["payload_json"])
            if raw["account"]["id"] != account_id:
                raise ConfigurationError("C1 context belongs to another account")
            context_inputs.append(_ref(row))
    return {
        "supported": True,
        "account": _ref(account_row),
        "account_posts": tuple(posts),
        "known_posts_count": count,
        "context_inputs": tuple(context_inputs),
        "source_inputs": identity_inputs,
    }


def previous_report(settings: Settings, identity: str) -> EntityRef:
    if not DataPaths(settings.data_dir).database.is_file():
        raise ConfigurationError("Refresh requires an existing account study library")
    with immutable_snapshot(DataPaths(settings.data_dir).database) as connection:
        row = connection.execute(
            "SELECT e.kind,e.entity_id,e.id FROM workflow_bindings b JOIN entity_revisions e "
            "ON e.id=b.revision_id WHERE b.workflow_id=? "
            "AND b.role='report' AND e.kind='account_study'",
            (identity,),
        ).fetchone()
        if row is None:
            raise ConfigurationError("Refresh requires a saved account study")
        return EntityRef(kind=row[0], id=row[1], revision_id=row[2])


def _dispatch(
    app: Application,
    identity: str,
    plan: WorkflowPlan,
    item: AccountPostInput,
    post: dict[str, Any],
    manifest: EntityRef,
    reused: dict[str, Any] | None,
) -> tuple[
    Literal["inspected", "media_analyzed", "media_reused", "failed"], EntityRef | None, str | None
]:
    """Commit each child before executing it, so interruptions resume the same run."""
    from socialdna.application.content_workflow_service import run as analyze

    if not item.media:
        return "inspected", None, item.media_reason
    signature = _signature(plan, item)
    if reused and reused.get("signature") == signature and reused.get("report"):
        ref = EntityRef.model_validate(reused["report"])
        with app.database.transaction() as connection:
            records.active(connection, ref)
        return "media_reused", ref, None
    with app.database.transaction() as connection:
        steps = records.records(connection, identity, "account_dispatch")
        saved = next(
            (
                records.active(connection, ref)
                for ref in steps
                if json.loads(EvidenceRepository(connection).entity(ref)["payload_json"])["post_id"]
                == item.post.id
            ),
            None,
        )
        if saved:
            child = saved["child_workflow"]
            _, child_plan = workflows.get(connection, child)
        else:
            target = parse_url(post["url"])
            child_request = WorkflowRequest(
                mode="analyze",
                url=target.canonical_url,
                goal="Analyze the supplied content with measured evidence.",
                question_scope="content_measurements",
                media=tuple(m.path for m in item.media),
                permission_basis=plan.request.permission_basis,
                analysis_options=plan.request.analysis_options,
                copy_media=plan.request.copy_media,
                replace_media=plan.request.replace_media,
            )
            child_plan = WorkflowPlan(
                request=child_request,
                platform=target.platform,
                target_kind="post",
                canonical_url=target.canonical_url,
                external_id=target.external_id,
                operations=(
                    "bind_supplied_originals",
                    "analyze_content",
                    "compose_assisted_report",
                ),
                supported=True,
                policy_version="supplied-original-association-v1",
                response_byte_limit=plan.response_byte_limit,
                request_timeout_seconds=plan.request_timeout_seconds,
                retention_days=None,
                limitations=("Assisted local originals only",),
                media_inputs=item.media,
                source_inputs=item.media_sources,
            )
            child = workflows.create(connection, child_plan)
            records.save(
                connection,
                "account_dispatch",
                identity,
                item.post.id,
                {
                    "workflow_id": identity,
                    "post_id": item.post.id,
                    "child_workflow": child,
                    "signature": signature,
                    "entity_inputs": [
                        manifest.model_dump(),
                        *[r.model_dump() for r in item.media_sources],
                    ],
                    "evidence_inputs": [],
                },
                EvidenceRepository(connection).entity(manifest)["provenance_id"],
            )
    try:
        result = analyze(app, child, child_plan)
        return "media_analyzed", EntityRef.model_validate(result["report"]), None
    except StorageIntegrityError:
        raise
    except SocialDNAError as exc:
        return "failed", None, str(exc)


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    assert plan.account is not None
    with app.database.transaction() as connection:
        old = records.records(connection, identity, "account_study")
        if old:
            ref = old[0]
        else:
            ref = None
    if ref:
        return records.load(app, ref, "json")
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        entity_active(connection, plan.account)
        for identity_source in plan.source_inputs:
            entity_active(connection, identity_source)
        posts = []
        for item in plan.account_posts:
            row = entity_active(connection, item.post)
            raw = json.loads(row["payload_json"])
            if (
                item.post.kind != "post"
                or raw["account_id"] != plan.account.id
                or raw["platform"] != plan.platform
            ):
                raise StorageIntegrityError("Pinned post has incompatible ownership/platform")
            for media_source in item.media_sources:
                entity_active(connection, media_source)
            posts.append(raw)
        context_data = []
        for context in plan.context_inputs:
            data = contexts.read(connection, context)
            if data["account"]["id"] != plan.account.id:
                raise ConfigurationError("C1 scope differs from account")
            context_data.append(
                {
                    "ref": context.model_dump(),
                    "evidence": contexts.cite(connection, context).model_dump(),
                    "spec": data["spec"],
                    "result": data["result"],
                }
            )
        previous = records.active(connection, plan.parent_report) if plan.parent_report else None
        if previous and previous["result"]["account"]["id"] != plan.account.id:
            raise ConfigurationError("Refresh must refer to the same stable account")
        prior = {p["post"]["id"]: p for p in previous["result"]["posts"]} if previous else {}
        all_inputs = (
            plan.account,
            *plan.source_inputs,
            *(p.post for p in plan.account_posts),
            *plan.context_inputs,
            *(source for p in plan.account_posts for source in p.media_sources),
        )
        manifest = records.save(
            connection,
            "account_manifest",
            identity,
            "manifest",
            {
                "workflow_id": identity,
                "account": plan.account.model_dump(),
                "posts": [item.model_dump(mode="json") for item in plan.account_posts],
                "entity_inputs": [r.model_dump() for r in all_inputs],
                "evidence_inputs": [],
            },
            repo.entity(plan.account)["provenance_id"],
        )
        citation = records.cite(connection, manifest)
        records.active(connection, manifest)
        workflows.bind(connection, identity, "capture", manifest, None)
    inspected = []
    reuse = previous.get("dispatch", {}) if previous else {}
    dispatch = {}
    for item, post in zip(plan.account_posts, posts, strict=True):
        status, media_ref, reason = _dispatch(
            app, identity, plan, item, post, manifest, reuse.get(item.post.id)
        )
        signature = _signature(plan, item)
        dispatch[item.post.id] = {
            "signature": signature,
            "report": media_ref.model_dump() if media_ref else None,
        }
        inspected.append(
            AccountStudyPost(
                post=item.post,
                published_at=post.get("published_at"),
                fields={
                    name: post.get(name) for name in ("title", "caption", "url", "content_type")
                },
                evidence=citation,
                status=status,
                media_report=media_ref,
                reason=reason,
            )
        )
    question = None
    if plan.request.mode == "research":
        from socialdna.application.research_service import register_into_application

        question = EntityRef.model_validate(
            register_into_application(
                app,
                ResearchRegistration(
                    key="workflow-" + identity,
                    question=plan.request.goal,
                    population=f"Pinned recent library sample: {len(inspected)} posts "
                    f"for account {plan.account.id}",
                    data_needs=(
                        "Reviewed literature/protocols and appropriate outcome evidence "
                        "before evaluating mechanisms",
                    ),
                    evidence=(citation,),
                ),
            )["question"]
        )
    current = {p.post.id: p.post.revision_id for p in inspected}
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        changed_content = {
            key
            for key in current.keys() & prior.keys()
            if repo.get("entity_revisions", current[key])["content_hash"]
            != repo.entity(EntityRef.model_validate(prior[key]["post"]))["content_hash"]
        }
    changes = {
        "new": sorted(current.keys() - prior.keys()),
        "removed_from_sample": sorted(prior.keys() - current.keys()),
        "changed": sorted(changed_content),
        "reobserved": sorted(
            key
            for key in current.keys() & prior.keys()
            if key not in changed_content and current[key] != prior[key]["post"]["revision_id"]
        ),
        "unchanged": sorted((current.keys() & prior.keys()) - changed_content),
        "baseline_workflow": plan.request.refresh_from,
        "boundary": "Sample changes are not deletion, independence or causal confirmation.",
    }
    study = AccountStudy(
        workflow_id=identity,
        canonical_url=plan.canonical_url,
        goal=plan.request.goal,
        mode="research" if plan.request.mode == "research" else "account",
        account=plan.account,
        manifest=manifest,
        known_posts_count=plan.known_posts_count,
        selected_posts_count=len(inspected),
        omitted_by_limit=max(0, plan.known_posts_count - len(inspected)),
        posts=tuple(inspected),
        contexts=tuple(context_data),
        changes=changes,
        research_question=question,
        research_state="draft" if question else "not_requested",
        limitations=(
            "Assisted library sample, not native pagination or complete platform history.",
            "Ordinary posts are not ranked by performance; remote deletions are unknown.",
            "No complete cadence, compatible performance comparison or causal recipe established.",
            "Unprovided private outcomes stay unknown; appearance is not measured conversion.",
            "Official guidance, observations and inferred patterns remain separate C1 records.",
            "Draft research only. No model training or automatic reevaluation occurs.",
        ),
        required_actions=(
            {
                "code": "account_coverage_incomplete",
                "message": "Provide permitted missing inventory/outcomes and reviewed evidence; "
                "native account collection is not delivered.",
            },
        ),
    )
    with app.database.transaction() as connection:
        inputs = [
            manifest,
            *plan.context_inputs,
            *(p.media_report for p in inspected if p.media_report),
            *((question,) if question else ()),
            *((plan.parent_report,) if plan.parent_report else ()),
        ]
        ref = records.save(
            connection,
            "account_study",
            identity,
            "study",
            {
                "workflow_id": identity,
                "entity_inputs": [r.model_dump() for r in inputs],
                "evidence_inputs": [citation.model_dump()],
                "dispatch": dispatch,
                "result": study.model_dump(mode="json"),
            },
            EvidenceRepository(connection).entity(manifest)["provenance_id"],
        )
        records.cite(connection, ref)
        lines = [
            "# Bounded account study",
            "",
            "URL: " + escape(plan.canonical_url),
            "",
            "Question: " + escape(study.goal),
            "",
            f"Selected {len(inspected)} of {plan.known_posts_count} known library posts. "
            "Platform inventory is incomplete.",
            "",
        ]
        for post_result in inspected:
            lines += [
                f"- {escape(post_result.published_at)}: "
                f"{escape(post_result.fields.get('title'))} — {post_result.status}; "
                f"evidence `{citation.revision_id}`",
                "  " + escape(post_result.reason or "Actual saved media analysis attached."),
            ]
        lines += [
            "",
            "## Changes",
            "",
            escape(json.dumps(changes)),
            "",
            "## Limitations",
            "",
            *("- " + escape(v) for v in study.limitations),
        ]
        records.freeze(app, connection, ref, study.model_dump(mode="json"), "\n".join(lines) + "\n")
        workflows.bind(connection, identity, "report", ref, None)
        workflows.state(connection, identity, "partial", "account_coverage_incomplete")
    return records.load(app, ref, "json")


def freshness(app: Application, ref: EntityRef) -> dict[str, Any]:
    with app.database.transaction() as connection:
        data = records.active(connection, ref)["result"]
        table = metadata.tables["entity_revisions"]
        rows = connection.execute(
            select(table.c.entity_id, table.c.id, table.c.payload_json)
            .where(table.c.kind == "post")
            .order_by(table.c.revision_no)
        ).all()
        heads = {row.entity_id: row for row in rows}
        selected = {p["post"]["id"]: p["post"]["revision_id"] for p in data["posts"]}
        eligible = {}
        for post_id, row in heads.items():
            if json.loads(row.payload_json).get("account_id") != data["account"]["id"]:
                continue
            candidate = EntityRef(kind="post", id=post_id, revision_id=row.id)
            try:
                entity_active(connection, candidate)
            except ConfigurationError:
                continue
            eligible[post_id] = row.id
        changed = [key for key in selected if eligible.get(key) != selected[key]]
        # Posts outside the original truncated sample already existed; only new
        # library units change known inventory, rather than every omitted post.
        new_count = len(eligible) > data["known_posts_count"]
    return {
        "stale": bool(changed or new_count),
        "changed_or_unavailable_selected_posts": sorted(changed),
        "known_inventory_grew": new_count,
        "refreshed": False,
    }


def _signature(plan: WorkflowPlan, item: AccountPostInput) -> str:
    return hash_config(
        {
            "media": [m.model_dump() for m in item.media],
            "options": plan.request.analysis_options.model_dump(),
            "copy_media": plan.request.copy_media,
        }
    )
