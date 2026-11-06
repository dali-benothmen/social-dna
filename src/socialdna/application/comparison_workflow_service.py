"""Finite URL scopes over eligible library evidence and the real registered R2 pipeline."""

import json
import sqlite3
from typing import Any, Literal

from sqlalchemy import Connection

from socialdna.application import account_workflow_service, performance_service
from socialdna.application.bootstrap import Application
from socialdna.application.context_service import provenance
from socialdna.application.workflow_sources import qualified_summary
from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.time import utc_now
from socialdna.domain.comparison_workflow import ComparisonSubject, SynthesisSource, URLComparison
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.workflows import WorkflowPlan, WorkflowRequest
from socialdna.ingestion.urls import parse_url
from socialdna.memory.documents import entity_active
from socialdna.reporting.markdown import escape
from socialdna.storage import content_repository as records
from socialdna.storage import workflow_repository as workflows
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.readonly import immutable_snapshot


def pin(settings: Settings, request: WorkflowRequest) -> dict[str, Any]:
    try:
        return _pin(settings, request)
    except sqlite3.Error:
        raise ConfigurationError("Cannot inspect comparison inputs in this library") from None


def _pin(settings: Settings, request: WorkflowRequest) -> dict[str, Any]:
    urls: list[tuple[str | None, Literal["left", "right"]]] = [
        (request.url, "left"),
        *((url, "left") for url in request.left_urls),
        *((url, "right") for url in request.against),
    ]
    targets = [(parse_url(url or ""), role) for url, role in urls]
    if len({t.canonical_url for t, _ in targets}) != len(targets):
        raise ConfigurationError("Comparison subjects must be distinct canonical URLs")
    if len({t.kind for t, _ in targets}) != 1:
        raise ConfigurationError("Declare either account or post subjects, not mixed scopes")
    cutoff = request.comparison.design.knowledge_cutoff if request.comparison.design else utc_now()
    if cutoff > utc_now():
        raise ConfigurationError("Comparison knowledge cutoff cannot be in the future")
    path = DataPaths(settings.data_dir).database
    subjects = []
    for target, role in targets:
        subject: EntityRef | None = None
        posts: tuple[EntityRef, ...] = ()
        inputs: tuple[EntityRef, ...] = ()
        count = 0
        if path.is_file():
            if target.kind == "account":
                data = account_workflow_service.pin(
                    settings,
                    WorkflowRequest(
                        mode="account", url=target.canonical_url, max_posts=request.max_posts
                    ),
                    target,
                )
                subject, inputs = data.get("account"), data.get("source_inputs", ())
            with immutable_snapshot(path) as connection:
                if target.kind == "post":
                    row = connection.execute(
                        "SELECT * FROM entity_revisions WHERE kind='post' "
                        "AND json_extract(payload_json,'$.platform')=? "
                        "AND json_extract(payload_json,'$.external_id')=? AND available_at<=? "
                        "ORDER BY revision_no DESC LIMIT 1",
                        (target.platform, target.external_id, cutoff),
                    ).fetchone()
                    if row:
                        subject = EntityRef(kind="post", id=row["entity_id"], revision_id=row["id"])
                        posts, count = (subject,), 1
                elif subject:
                    query = (
                        " FROM entity_revisions e WHERE e.kind='post' "
                        "AND json_extract(e.payload_json,'$.account_id')=? AND e.available_at<=? "
                        "AND NOT EXISTS (SELECT 1 FROM entity_revisions n WHERE n.kind=e.kind "
                        "AND n.entity_id=e.entity_id AND n.revision_no>e.revision_no "
                        "AND n.available_at<=?)"
                    )
                    args = (subject.id, cutoff, cutoff)
                    count = connection.execute("SELECT count(*)" + query, args).fetchone()[0]
                    rows = connection.execute(
                        "SELECT e.*"
                        + query
                        + " ORDER BY json_extract(e.payload_json,'$.published_at') DESC,"
                        "e.entity_id LIMIT ?",
                        (*args, request.max_posts),
                    ).fetchall()
                    posts = tuple(
                        EntityRef(kind="post", id=row["entity_id"], revision_id=row["id"])
                        for row in rows
                    )
        subjects.append(
            ComparisonSubject(
                url=target.canonical_url,
                platform=target.platform,
                kind=target.kind,
                role=role,
                subject=subject,
                posts=posts,
                identity_inputs=inputs,
                known_posts_count=count,
                reason=None
                if subject
                else "No permitted library observation resolved; "
                "native URL acquisition is not delivered.",
            )
        )
    identifiers = [s.subject.id for s in subjects if s.subject]
    if len(identifiers) != len(set(identifiers)):
        raise ConfigurationError(
            "Aliases resolve to duplicate subjects; comparisons must be disjoint"
        )
    prepared = []
    if request.comparison.support_revisions or request.comparison.contrary_revisions:
        if not path.is_file():
            raise ConfigurationError("Prepared synthesis inputs need an existing library")
        with immutable_snapshot(path) as connection:
            for revision in (
                *request.comparison.support_revisions,
                *request.comparison.contrary_revisions,
            ):
                row = connection.execute(
                    "SELECT kind,entity_id,id FROM entity_revisions WHERE id=?", (revision,)
                ).fetchone()
                if not row:
                    raise ConfigurationError("Unknown prepared source revision")
                prepared.append(EntityRef(kind=row[0], id=row[1], revision_id=row[2]))
    return {
        "request": request.model_copy(
            update={
                "url": targets[0][0].canonical_url,
                "left_urls": tuple(t.canonical_url for t, role in targets[1:] if role == "left"),
                "against": tuple(t.canonical_url for t, role in targets if role == "right"),
            }
        ),
        "comparison_subjects": tuple(subjects),
        "prepared_inputs": tuple(prepared),
        "supported": True,
    }


def _quantitative_lines(result: URLComparison) -> list[str]:
    output = result.quantitative
    if output is None:
        return ["No quantitative comparison was authorized/eligible; see required actions."]
    comparison = output.get("comparison") or {}
    design = result.compatibility.get("design") or {}
    lines = [
        f"Actual registered run: `{result.comparison_run_id}`",
        f"Metric: {escape(design.get('metric_key'))}; "
        f"denominator: {escape(design.get('denominator_key'))}",
        f"Knowledge cutoff: {escape(design.get('knowledge_cutoff'))}; "
        f"target age: {design.get('age_days')} days",
        f"Usable observations: {output.get('available_n')} / {output.get('population_n')}; "
        f"missing: {output.get('missing_n')}",
        f"Design support: {escape(comparison.get('status'))}; "
        f"retained creators: {comparison.get('effective_creator_count')}",
        f"Left observed median: {(comparison.get('left') or {}).get('median')}; "
        f"right observed median: {(comparison.get('right') or {}).get('median')}",
        "Matched descriptive estimate: "
        f"{(comparison.get('matched_effect') or {}).get('estimate')}; "
        f"inference qualification: {result.numeric_inference}",
        "Full frozen diagnostics, balance, missingness and test ledger are retained in JSON.",
    ]
    lines += [f"- Statistical citation `{ref.revision_id}`" for ref in result.statistical_evidence]
    lines += ["- " + escape(v) for v in output.get("limitations", [])]
    return lines


def run(app: Application, identity: str, plan: WorkflowPlan) -> dict[str, Any]:
    with app.database.transaction() as connection:
        saved = records.records(connection, identity, "url_comparison")
    if saved:
        from socialdna.application.workflow_report_service import generate

        return generate(app, identity)
    accepted: list[ComparisonSubject] = []
    inventory: list[dict[str, Any]] = []
    inputs: list[EntityRef] = []
    actions: list[dict[str, str]] = []
    with app.database.transaction() as connection:
        repo = EvidenceRepository(connection)
        _, producer = provenance(
            connection,
            {"workflow_id": identity},
            f"urn:socialdna:comparison:{identity}",
            "locally_authored; all source permissions remain transitive",
        )
        for subject in plan.comparison_subjects:
            try:
                if not subject.subject:
                    raise ConfigurationError(subject.reason or "Missing source")
                refs = (subject.subject, *subject.posts, *subject.identity_inputs)
                for ref in refs:
                    entity_active(connection, ref)
                rows = [json.loads(repo.entity(ref)["payload_json"]) for ref in subject.posts]
                inventory.append(
                    {
                        "url": subject.url,
                        "role": subject.role,
                        "selected_posts": len(rows),
                        "known_library_posts": subject.known_posts_count,
                        "omitted_by_limit": max(0, subject.known_posts_count - len(rows)),
                        "platform_inventory_complete": False,
                        "posts": [
                            {
                                "ref": ref.model_dump(),
                                "published_at": row.get("published_at"),
                                "format": row.get("content_type"),
                                "title": row.get("title"),
                                "caption_length": len(row["caption"])
                                if row.get("caption") is not None
                                else None,
                            }
                            for ref, row in zip(subject.posts, rows, strict=True)
                        ],
                    }
                )
                inputs.extend(refs)
                accepted.append(subject)
            except ConfigurationError:
                accepted.append(
                    subject.model_copy(
                        update={
                            "subject": None,
                            "posts": (),
                            "identity_inputs": (),
                            "known_posts_count": 0,
                            "reason": "Source missing or ineligible; "
                            "no protected source fields are disclosed.",
                        }
                    )
                )
                actions.append(
                    {
                        "code": "comparison_source_required",
                        "message": f"Provide eligible independent observations for {subject.url}.",
                    }
                )
        selected = {ref.id for subject in accepted for ref in subject.posts}
        left = {ref.id for s in accepted if s.role == "left" for ref in s.posts}
        right = {ref.id for s in accepted if s.role == "right" for ref in s.posts}
        if left & right:
            raise ConfigurationError("Selected post groups overlap")
        manifest = records.save(
            connection,
            "comparison_manifest",
            identity,
            "manifest",
            {
                "workflow_id": identity,
                "subjects": [s.model_dump(mode="json") for s in accepted],
                "entity_inputs": [r.model_dump() for r in inputs],
                "evidence_inputs": [],
            },
            producer,
        )
        manifest_citation = records.cite(connection, manifest)
        for item in inventory:
            item["evidence"] = manifest_citation.model_dump()
        workflows.bind(connection, identity, "capture", manifest, None)
    quantitative, run_id, numeric_ref = None, None, None
    stat_refs: tuple[EvidenceRef, ...] = ()
    numerical_support = False
    platforms = {s.platform for s in accepted}
    compatible = len(platforms) == 1 and all(s.subject for s in accepted) and bool(left and right)
    design = plan.request.comparison.design
    if design and compatible:
        with app.database.transaction() as connection:
            checkpoints = records.records(connection, identity, "comparison_run")
            checkpoint = records.active(connection, checkpoints[0]) if checkpoints else None

        def on_saved(connection: Connection, report: dict[str, Any]) -> None:
            refs = [
                EvidenceRef.model_validate(item["ref"]) for item in report["statistical_evidence"]
            ]
            records.save(
                connection,
                "comparison_run",
                identity,
                "analysis",
                {
                    "workflow_id": identity,
                    "run_id": report["run_id"],
                    "target_id": report["target_id"],
                    "entity_inputs": [manifest.model_dump()],
                    "evidence_inputs": [r.model_dump() for r in refs],
                },
                producer,
            )

        try:
            report = (
                performance_service.load_performance_report(app, run_id=checkpoint["run_id"])
                if checkpoint
                else performance_service.compare(
                    app, "posts", sorted(left), sorted(right), design, on_saved=on_saved
                )
            )
            if set(row["post_id"] for row in report["posts"]) - selected:
                raise StorageIntegrityError("Comparison pipeline returned unselected target units")
            stat_refs = tuple(
                EvidenceRef.model_validate(item["ref"]) for item in report["statistical_evidence"]
            )
            with app.database.transaction() as connection:
                from socialdna.application.evidence_service import EvidenceResolver

                for statistic in stat_refs:
                    EvidenceResolver(connection).resolve(statistic, purpose="new_claim")
                checkpoint_ref = records.records(connection, identity, "comparison_run")[0]
                numeric_ref = checkpoint_ref
            quantitative, run_id = report["results"], report["run_id"]
        except ConfigurationError as exc:
            actions.append({"code": "quantitative_comparison_withheld", "message": str(exc)})
    else:
        actions.append(
            {
                "code": "quantitative_comparison_withheld",
                "message": "An explicit compatible R2 v2 design, eligible same-platform groups "
                "and mature source-defined outcomes are required.",
            }
        )
    counterexamples = []
    if quantitative is not None:
        by_id = {row["post_id"]: row for row in report["posts"]}
        for a, b in (quantitative.get("comparison") or {}).get("pairs", []):
            if by_id[a]["outcome"] <= by_id[b]["outcome"]:
                counterexamples.append(
                    {
                        "left_post": a,
                        "right_post": b,
                        "qualification": "Comparable pair contrary to a universal left-is-better "
                        "claim; not a causal test",
                        "evidence": [ref.model_dump() for ref in stat_refs],
                    }
                )
                if len(counterexamples) == 10:
                    break
        numerical_support = (quantitative.get("comparison") or {}).get("status") in (
            "supported_descriptive",
            "descriptive",
        ) and quantitative.get("available_n", 0) >= 2
        if (
            design
            and design.design == "cross_creator"
            and (quantitative.get("comparison") or {}).get("effective_creator_count", 0) < 20
        ):
            numerical_support = False
            actions.append(
                {
                    "code": "creator_generalization_withheld",
                    "message": "Fewer than 20 retained creator clusters: "
                    "keep the actual output descriptive; "
                    "cross-creator inference is withheld under the existing R2 engineering gate, "
                    "which is not a power guarantee.",
                }
            )
        if not numerical_support:
            actions.append(
                {
                    "code": "comparison_support_limited",
                    "message": "Actual pipeline found insufficient comparable data; "
                    "numeric inference is withheld.",
                }
            )
    sources = []
    prepared_dependencies = []
    with app.database.transaction() as connection:
        for ref in plan.prepared_inputs:
            try:
                lane, summary, citations = qualified_summary(connection, ref)
                sources.append(
                    SynthesisSource(
                        subject=ref,
                        role="counterevidence"
                        if ref.revision_id in plan.request.comparison.contrary_revisions
                        else "support",
                        lane=lane,
                        evidence=citations,
                        summary=summary,
                    )
                )
                prepared_dependencies.append(ref)
            except ConfigurationError:
                actions.append(
                    {
                        "code": "prepared_source_withheld",
                        "message": "A supplied source is unavailable, unreviewed for this use, "
                        "or has an unsupported producer; no promotion occurred.",
                    }
                )
    if plan.request.comparison.recommendation:
        from socialdna.application.recommendation_service import create

        try:
            proposed = create(app, plan.request.comparison.recommendation)
            ref = EntityRef.model_validate(proposed["ref"])
            with app.database.transaction() as connection:
                lane, summary, citations = qualified_summary(connection, ref)
            sources.append(
                SynthesisSource(
                    subject=ref, role="proposal", lane=lane, evidence=citations, summary=summary
                )
            )
            prepared_dependencies.append(ref)
        except ConfigurationError as exc:
            actions.append({"code": "recommendation_withheld", "message": str(exc)})
    fulfilled = (
        plan.request.question_scope == "comparison_descriptive"
        and quantitative is not None
        and not actions
    )
    if not fulfilled and not actions:
        actions.append(
            {
                "code": "goal_requires_review",
                "message": "Finite descriptive comparison does not certify the arbitrary goal, "
                "mechanism or causal growth strategy.",
            }
        )
    result = URLComparison(
        workflow_id=identity,
        goal=plan.request.goal,
        status="success" if fulfilled else "partial",
        request_fulfilled=fulfilled,
        subjects=tuple(accepted),
        manifest=manifest,
        inventory=tuple(inventory),
        comparison_run_id=run_id,
        statistical_evidence=stat_refs,
        quantitative=quantitative,
        numeric_inference="descriptive_only" if numerical_support else "withheld",
        compatibility={
            "same_platform": len(platforms) == 1,
            "design": design.model_dump(mode="json") if design else None,
            "actual_inputs": {
                "configuration": report["analysis_configuration"],
                "metric_definitions": report["metric_definitions"],
                "target_post_refs": [row.get("post_ref") for row in report["posts"]],
                "test_ledger": report.get("test_ledger"),
            }
            if quantitative is not None
            else None,
            "sample": "exact bounded library post revisions; ordinary posts included, "
            "no ranking by outcomes",
            "boundary": "Descriptive summaries are not significance, independent replication "
            "or causation; actual pipeline diagnostics govern every estimate.",
        },
        counterexamples=tuple(counterexamples),
        sources=tuple(sources),
        limitations=(
            "Assisted eligible library sources; no new URL acquisition or media processing.",
            "Pinned finite samples are not complete platform inventories "
            "or complete publishing histories.",
            "No cross-platform metric pooling or proprietary recommendation-weight recovery.",
            "Literature, official guidance, measured associations, interpretations "
            "and proposed tests are distinct lanes.",
            "Sparse creator counts, unknown confounders and actual R2 limitations "
            "are retained; no virality guarantee.",
        ),
        required_actions=tuple(actions),
    )
    with app.database.transaction() as connection:
        dependencies = [manifest, *prepared_dependencies, *((numeric_ref,) if numeric_ref else ())]
        saved_ref = records.save(
            connection,
            "url_comparison",
            identity,
            "report",
            {
                "workflow_id": identity,
                "entity_inputs": [ref.model_dump() for ref in dependencies],
                "evidence_inputs": [
                    manifest_citation.model_dump(),
                    *[r.model_dump() for r in stat_refs],
                ],
                "result": result.model_dump(mode="json"),
            },
            producer,
        )
        records.cite(connection, saved_ref)
        lines = [
            "# Source-qualified comparison",
            "",
            escape(result.goal),
            "",
            "## Exact subjects and observations",
            "",
        ]
        for item in result.inventory:
            lines += [
                f"- {escape(item['url'])}: {item['selected_posts']} selected / "
                f"{item['known_library_posts']} known library posts; "
                f"evidence `{manifest_citation.revision_id}`"
            ]
            lines += [
                f"  - {escape(p['published_at'])}: {escape(p['title'])}; "
                f"caption length {p['caption_length']}"
                for p in item["posts"]
            ]
        lines += [
            "",
            "## Registered quantitative output",
            "",
            *_quantitative_lines(result),
            "",
            "## Counterexamples",
            "",
            escape(json.dumps(counterexamples)),
            "",
            "## Separately qualified synthesis sources",
            "",
        ]
        lines += [
            f"- {source.lane} / {source.role}: "
            f"{escape(json.dumps(source.summary, ensure_ascii=False))} "
            f"(revision `{source.subject.revision_id}`; "
            f"citations {', '.join(c.revision_id for c in source.evidence)})"
            for source in sources
        ]
        lines += [
            "",
            "## Limitations and required actions",
            "",
            *("- " + escape(v) for v in result.limitations),
            *("- " + escape(a["message"]) for a in actions),
        ]
        records.freeze(
            app, connection, saved_ref, result.model_dump(mode="json"), "\n".join(lines) + "\n"
        )
        workflows.bind(connection, identity, "report", saved_ref, None)
        workflows.state(connection, identity, "completed" if fulfilled else "partial")
    return records.load(app, saved_ref, "json")
