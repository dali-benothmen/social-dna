import json
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from socialdna.application.bootstrap import Application
from socialdna.application.evidence_service import (
    EvidenceResolver,
    assert_active_inputs,
    assert_context_active,
    assert_media_active,
)
from socialdna.core.exceptions import InvalidMedia
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.media.timeline import timeline
from socialdna.reporting.markdown import render_markdown
from socialdna.reporting.models import VideoReport
from socialdna.storage.schema import metadata


def build_report(application: Application, run_id: str) -> VideoReport:
    with application.database.transaction() as connection:
        runs = metadata.tables["analysis_runs"]
        run = connection.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        if run is None:
            raise InvalidMedia("Unknown analysis run.")
        assert_media_active(connection, run["target_id"])
        tasks = [
            dict(row)
            for row in connection.execute(
                select(metadata.tables["analysis_tasks"])
                .where(metadata.tables["analysis_tasks"].c.run_id == run_id)
                .order_by(metadata.tables["analysis_tasks"].c.task_key)
            ).mappings()
        ]
        probes = metadata.tables["media_probes"]
        probe = json.loads(
            connection.execute(
                select(probes.c.probe_json).where(probes.c.media_asset_id == run["target_id"])
            ).scalar_one()
        )
        title = connection.scalar(
            select(metadata.tables["posts"].c.title)
            .join(metadata.tables["post_media"])
            .where(metadata.tables["post_media"].c.media_asset_id == run["target_id"])
        )
        result_rows: list[str] = list(
            connection.execute(
                select(metadata.tables["analysis_task_results"].c.result_json)
                .join(metadata.tables["analysis_tasks"])
                .where(
                    metadata.tables["analysis_tasks"].c.id.in_(
                        [task["reused_from_task_id"] or task["id"] for task in tasks]
                    )
                )
            ).scalars()
        )
        provenance_table = metadata.tables["provenance_records"]
        task_results = metadata.tables["analysis_task_results"]
        provenance = [
            dict(row)
            for row in connection.execute(
                select(provenance_table)
                .where(
                    provenance_table.c.id.in_(
                        select(task_results.c.provenance_id).where(
                            task_results.c.task_id.in_(
                                [task["reused_from_task_id"] or task["id"] for task in tasks]
                            )
                        )
                    )
                )
                .order_by(provenance_table.c.id)
            ).mappings()
        ]
    creative_enabled = bool(json.loads(run["config_json"]).get("creative"))
    data = timeline(application, run["target_id"], run_id=run_id, include_creative=creative_enabled)
    if creative_enabled and not data["creative"]["eligible"]:
        from socialdna.core.exceptions import ConfigurationError

        raise ConfigurationError("Creative report inputs are withdrawn or ineligible")
    with application.database.transaction() as connection:
        for frame in data["frames"]:
            row = application.artifacts.get(connection, frame["artifact_id"])
            frame["artifact_uri"] = application.artifacts.path_for(row["relative_path"]).as_uri()
        definitions = metadata.tables["feature_definitions"]
        feature_definitions = [
            dict(row)
            for row in connection.execute(
                select(definitions)
                .where(definitions.c.key.in_({row["feature_key"] for row in data["observations"]}))
                .order_by(definitions.c.key)
            ).mappings()
        ]
        artifact_ids = sorted(
            {
                artifact_id
                for raw in result_rows
                for artifact_id in json.loads(raw).get("artifacts", [])
            }
        )
        artifact_ids = sorted(
            set(artifact_ids)
            | {
                call[field]
                for call in data["provider_calls"]
                for field in ("request_artifact_id", "response_artifact_id")
                if call[field]
            }
        )
        artifacts: list[dict[str, Any]] = []
        for artifact_id in artifact_ids:
            artifact = dict(application.artifacts.get(connection, artifact_id))
            artifact["uri"] = application.artifacts.path_for(artifact["relative_path"]).as_uri()
            artifacts.append(artifact)
    limitations = [
        "Local enrichment runs only with prepared models and optional runtimes. "
        "Psychological discovery and semantic/graph memory are not implemented; "
        "performance analytics requires a separate imported-account analysis.",
        "No publishing or performance data was supplied; "
        "performance relationships cannot be assessed.",
        "Frame measurements use downscaled scene-aware samples; "
        "they do not represent every source pixel or prove camera intent.",
    ]
    if run["status"] != "succeeded":
        limitations.append(
            f"Run execution status is {run['status']}; "
            "this report includes only committed successful task outputs."
        )
    if creative_enabled:
        limitations.extend(data["creative"].get("limitations", []))
        limitations.append(
            "Creative labels are reviewed assertions or literal-text proposals, not "
            "validated visual recognition or psychological explanations. Sparse samples "
            "cannot establish absence; caption/hashtag evidence has no playback offset."
        )
    for raw in result_rows:
        result = json.loads(raw)
        limitations.extend(result.get("limitations", []))
        if result.get("reason"):
            limitations.append(result["reason"])
    for task in tasks:
        if task["status"] == "failed":
            limitations.append(
                f"{task['task_key']} failed: {json.loads(task['error_json']).get('message', '')}"
            )
    return VideoReport(
        schema_version="2.0" if creative_enabled else "1.0",
        run_id=run_id,
        media_id=run["target_id"],
        status="partial" if run["status"] != "succeeded" else "success",
        title=title or run["target_id"],
        metadata=probe,
        analysis_configuration=json.loads(run["config_json"]),
        feature_definitions=feature_definitions,
        provenance=provenance,
        artifacts=artifacts,
        tasks=tasks,
        timeline=data,
        limitations=list(dict.fromkeys(limitations)),
    )


def generate_report(
    application: Application,
    run_id: str | None,
    report_format: Literal["json", "markdown"] = "json",
    *,
    account_id: str | None = None,
) -> dict[str, Any]:
    from socialdna.application.performance_service import load_performance_report
    from socialdna.reporting.performance import render_performance

    performance: dict[str, Any] | None
    if account_id:
        performance = load_performance_report(application, account_id=account_id)
    elif run_id:
        with application.database.transaction() as connection:
            runs = metadata.tables["analysis_runs"]
            target = connection.scalar(select(runs.c.target_type).where(runs.c.id == run_id))
        if target in ("image", "carousel"):
            from socialdna.application.image_service import load_analysis as load_static
            from socialdna.reporting.images import render_static

            static = load_static(application, run_id)
            content = (
                json.dumps(static, indent=2, ensure_ascii=False, allow_nan=False)
                if report_format == "json"
                else render_static(static)
            )
            return _save_performance_report(application, static, content, report_format)
        if target == "behavioral":
            from socialdna.application.behavioral_service import load_analysis as load_behavioral
            from socialdna.reporting.behavioral import render_behavioral

            behavioral = load_behavioral(application, run_id)
            content = (
                json.dumps(behavioral, indent=2, ensure_ascii=False, allow_nan=False)
                if report_format == "json"
                else render_behavioral(behavioral)
            )
            return _save_performance_report(application, behavioral, content, report_format)
        if target == "audience":
            from socialdna.application.audience_service import load_analysis
            from socialdna.reporting.audience import render_audience

            audience = load_analysis(application, run_id)
            content = (
                json.dumps(audience, indent=2, ensure_ascii=False, allow_nan=False)
                if report_format == "json"
                else render_audience(audience)
            )
            return _save_performance_report(
                application, {**audience, "status": "success"}, content, report_format
            )
        performance = (
            load_performance_report(application, run_id=run_id)
            if target in ("account", "comparison")
            else None
        )
    else:
        raise InvalidMedia("Supply an analysis run or account ID.")
    if performance is not None:
        # Never replace archived bytes with a new current claim using revoked inputs.
        with application.database.transaction() as connection:
            if performance["schema_version"] == "2.0":
                from socialdna.application.statistical_service import assert_design_inputs

                assert_design_inputs(
                    connection, performance["posts"] + performance["reference_population"]
                )
            else:
                assert_context_active(
                    connection,
                    tuple(
                        {post["post_id"] for post in performance["posts"]}
                        | {
                            post["account_id"]
                            for post in performance["posts"]
                            if post["account_id"]
                        }
                    ),
                )
            for post in performance["posts"]:
                assert_active_inputs(
                    connection,
                    source_ids=tuple(item["source_id"] for item in post["snapshots"]),
                    evidence_ids=tuple(
                        stable_id("metric-evidence", item) for item in post["snapshot_ids"]
                    ),
                )
                for evidence_id in post["feature_evidence_ids"]:
                    EvidenceResolver(connection).resolve(evidence_id, purpose="new_claim")
        run_id = performance["run_id"]
        content = (
            json.dumps(performance, indent=2, ensure_ascii=False, allow_nan=False)
            if report_format == "json"
            else render_performance(performance)
        )
        return _save_performance_report(application, performance, content, report_format)
    assert run_id is not None
    report = build_report(application, run_id)
    content = (
        report.model_dump_json(indent=2) if report_format == "json" else render_markdown(report)
    )
    report_id = stable_id("report", run_id, report_format)
    with application.database.transaction() as connection:
        artifact_id = application.artifacts.put_bytes(
            connection,
            content.encode("utf-8"),
            kind="report",
            mime_type="application/json" if report_format == "json" else "text/markdown",
        )
        application.artifacts.add_reference(
            connection, artifact_id, owner_type="report", owner_id=report_id, role="content"
        )
        reports = metadata.tables["reports"]
        connection.execute(
            insert(reports)
            .values(
                id=report_id,
                run_id=run_id,
                format=report_format,
                artifact_id=artifact_id,
                schema_version=report.schema_version,
                created_at=utc_now(),
            )
            .on_conflict_do_update(
                index_elements=[reports.c.run_id, reports.c.format],
                set_={"artifact_id": artifact_id, "created_at": utc_now()},
            )
        )
        row = application.artifacts.get(connection, artifact_id)
    return {
        "status": report.status,
        "report_id": report_id,
        "artifact_id": artifact_id,
        "path": str(application.artifacts.path_for(row["relative_path"])),
        "format": report_format,
        "content": report.model_dump() if report_format == "json" else content,
    }


def _save_performance_report(
    application: Application,
    report: dict[str, Any],
    content: str,
    report_format: Literal["json", "markdown"],
) -> dict[str, Any]:
    report_id = stable_id("report", report["run_id"], report_format)
    with application.database.transaction() as connection:
        artifact_id = application.artifacts.put_bytes(
            connection,
            content.encode("utf-8"),
            kind="report",
            mime_type="application/json" if report_format == "json" else "text/markdown",
        )
        application.artifacts.add_reference(
            connection, artifact_id, owner_type="report", owner_id=report_id, role="content"
        )
        table = metadata.tables["reports"]
        statement = insert(table).values(
            id=report_id,
            run_id=report["run_id"],
            format=report_format,
            artifact_id=artifact_id,
            schema_version=report["schema_version"],
            created_at=utc_now(),
        )
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[table.c.run_id, table.c.format],
                set_={"artifact_id": artifact_id, "created_at": utc_now()},
            )
        )
        row = application.artifacts.get(connection, artifact_id)
    return {
        "run_id": report["run_id"],
        "status": report["status"],
        "report_id": report_id,
        "artifact_id": artifact_id,
        "path": str(application.artifacts.path_for(row["relative_path"])),
        "format": report_format,
        "content": report if report_format == "json" else content,
        "limitations": report["limitations"],
    }
