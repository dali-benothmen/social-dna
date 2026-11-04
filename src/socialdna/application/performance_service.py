"""Canonical account cohorts, bounded local-media batches, and frozen research runs."""

import importlib.metadata
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import url2pathname

import numpy as np
from sqlalchemy import Connection, select
from sqlalchemy.dialects.sqlite import insert

from socialdna import __version__
from socialdna.analytics.cohorts import in_population, match_pairs
from socialdna.analytics.metrics import outcome, select_snapshot
from socialdna.analytics.statistics import analyze_rows
from socialdna.application.bootstrap import Application
from socialdna.core.exceptions import ConfigurationError, SocialDNAError, StorageIntegrityError
from socialdna.core.hashing import canonical_json, hash_config
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import PerformanceSpec
from socialdna.storage.schema import metadata

FEATURE_REGISTRY = {
    "duration_seconds": "Primary local media duration (seconds)",
    "caption_length": "Supplied caption Unicode code-point count; missing caption stays missing",
    "publishing_hour_utc": "UTC publication hour (0-23; not a circular encoding)",
    "visual.motion": "Median visual.optical_flow in sampled intervals starting before 3000 ms",
    "visual.appearance": "Median visual.brightness in sampled intervals starting before 3000 ms",
    "audio.loudness": "Median audio.rms_dbfs in sampled intervals starting before 3000 ms",
}
OBSERVATION_KEYS = {
    "visual.motion": "visual.optical_flow",
    "visual.appearance": "visual.brightness",
    "audio.loudness": "audio.rms_dbfs",
}


def _rows(connection: Connection, name: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(select(metadata.tables[name])).mappings()]


def _validate_definitions(connection: Connection, spec: PerformanceSpec) -> list[dict[str, Any]]:
    definitions = metadata.tables["metric_definitions"]
    required = {spec.metric_key, *spec.numerator_keys}
    if spec.denominator_key:
        required.add(spec.denominator_key)
    result = [
        dict(metric_row)
        for metric_row in connection.execute(
            select(definitions).where(definitions.c.key.in_(required))
        ).mappings()
    ]
    if len(result) != len(required) or any(row["subject_type"] != "post" for row in result):
        raise ConfigurationError("Every requested outcome component needs a post metric definition")
    if len({row["platform"] for row in result}) != 1:
        raise ConfigurationError("A single analysis cannot equate metrics across platforms")
    if len({row["measurement"] for row in result}) != 1:
        raise ConfigurationError("Rate components must have the same measurement semantics")
    if any(row["measurement"] == "period" for row in result) and spec.window_seconds is None:
        raise ConfigurationError("Period outcome analyses require explicit window_seconds")
    if (
        spec.numerator_keys
        and len({row["unit"] for row in result if row["key"] != spec.denominator_key}) != 1
    ):
        raise ConfigurationError("Summed numerator components must have the same unit")
    if (
        spec.model == "poisson"
        and next(row for row in result if row["key"] == spec.metric_key)["unit"] != "count"
    ):
        raise ConfigurationError("Poisson requires an outcome defined in counts")
    return sorted(result, key=lambda row: row["key"])


def build_population(
    application: Application,
    spec: PerformanceSpec,
    *,
    account_ids: list[str] | None = None,
    post_ids: list[str] | None = None,
    roles: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with application.database.transaction() as connection:
        definitions = _validate_definitions(connection, spec)
        accounts = {row["id"]: row for row in _rows(connection, "accounts")}
        if account_ids and set(account_ids) - accounts.keys():
            raise ConfigurationError("Unknown account ID")
        posts_table = metadata.tables["posts"]
        query = select(posts_table)
        if account_ids:
            query = query.where(posts_table.c.account_id.in_(account_ids))
        if post_ids:
            query = query.where(posts_table.c.id.in_(post_ids))
        posts = [dict(row) for row in connection.execute(query.limit(5001)).mappings()]
        if len(posts) > 5000:
            raise ConfigurationError(
                "Local performance runs are bounded to 5000 posts; narrow the ID groups"
            )
        if post_ids and set(post_ids) - {row["id"] for row in posts}:
            raise ConfigurationError("Unknown post ID")
        # Keep platform definitions distinct even if a creator has cross-platform accounts.
        posts = [row for row in posts if row["platform"] == definitions[0]["platform"]]
        selected_ids = {row["id"] for row in posts}
        primary = {
            row["post_id"]: row["media_asset_id"]
            for row in _rows(connection, "post_media")
            if row["position"] == 0 and row["post_id"] in selected_ids
        }
        assets = {
            row["id"]: row
            for row in _rows(connection, "media_assets")
            if row["id"] in primary.values()
        }
        tags = {row["id"]: row for row in _rows(connection, "tags")}
        topics: dict[str, list[str]] = defaultdict(list)
        for row in _rows(connection, "post_tags"):
            if row["post_id"] in selected_ids and tags[row["tag_id"]]["kind"] == "topic":
                topics[row["post_id"]].append(tags[row["tag_id"]]["normalized_value"])
        snapshots: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        metrics_table = metadata.tables["metric_observations"]
        provenance, sources = (
            metadata.tables[name] for name in ("provenance_records", "source_records")
        )
        for metric_row in connection.execute(
            select(
                metrics_table,
                sources.c.id.label("source_id"),
                sources.c.source_uri,
                sources.c.permission_basis,
                sources.c.raw_artifact_id,
            )
            .join(provenance, provenance.c.id == metrics_table.c.provenance_id)
            .join(sources, sources.c.id == provenance.c.source_record_id)
            .where(
                metrics_table.c.post_id.in_(selected_ids),
                metrics_table.c.metric_key.in_([r["key"] for r in definitions]),
            )
        ).mappings():
            snapshots[(metric_row["subject_id"], metric_row["metric_key"])].append(dict(metric_row))
        feature_data = _media_features(connection, set(primary.values()))
    result = []
    for post in posts:
        account = accounts.get(post["account_id"], {})
        media_id = primary.get(post["id"])
        asset = assets.get(media_id or "", {})
        features: dict[str, float | None] = {
            "duration_seconds": asset["duration_ms"] / 1000
            if asset.get("duration_ms") is not None
            else None,
            "caption_length": float(len(post["caption"])) if post["caption"] is not None else None,
            "publishing_hour_utc": float(datetime.fromisoformat(post["published_at"]).hour)
            if post["published_at"]
            else None,
        }
        content = feature_data.get(media_id or "", {})
        features.update(content.get("features", {}))
        selected: dict[str, dict[str, Any] | None] = {}
        states: dict[str, str] = {}
        for definition in definitions:
            selected[definition["key"]], states[definition["key"]] = select_snapshot(
                snapshots.get((post["id"], definition["key"]), []), spec
            )
        value, state = outcome(selected, spec)
        main = selected[spec.metric_key]
        if value is None and states[spec.metric_key] != "available":
            state = states[spec.metric_key]
        row = {
            "post_id": post["id"],
            "account_id": post["account_id"],
            "creator_id": account.get("creator_id") or post["account_id"] or post["id"],
            "creator_identity": "supplied" if account.get("creator_id") else "account_proxy",
            "platform": post["platform"],
            "niche": account.get("niche"),
            "content_type": post["content_type"],
            "published_at": post["published_at"],
            "topics": sorted(topics[post["id"]]),
            "features": features,
            "outcome": value,
            "outcome_available_at": max(
                (r["observed_at"] for r in selected.values() if r), default=post["published_at"]
            ),
            "availability": state,
            "metric_states": states,
            "age_seconds": main["post_age_seconds"] if main else None,
            "window_seconds": spec.window_seconds,
            "snapshot_ids": sorted(r["id"] for r in selected.values() if r),
            "snapshots": sorted([r for r in selected.values() if r], key=lambda r: r["metric_key"]),
            "media_run_id": content.get("run_id"),
            "feature_evidence_ids": content.get("evidence_ids", []),
            "role": (roles or {}).get(
                post["id"], (roles or {}).get(post["account_id"], "population")
            ),
        }
        if in_population(row, spec.population):
            result.append(row)
    return sorted(result, key=lambda row: row["post_id"]), definitions


def _media_features(connection: Connection, media_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Use the latest successful media run, resolving cached producer task IDs."""
    runs, tasks, observations, evidence = (
        metadata.tables[name]
        for name in ("analysis_runs", "analysis_tasks", "observations", "evidence_items")
    )
    result = {}
    for media_id in sorted(media_ids):
        run_id = connection.scalar(
            select(runs.c.id)
            .where(runs.c.target_id == media_id, runs.c.status == "succeeded")
            .order_by(runs.c.created_at.desc(), runs.c.id.desc())
            .limit(1)
        )
        if not run_id:
            continue
        producers = [
            row["reused_from_task_id"] or row["id"]
            for row in connection.execute(
                select(tasks).where(tasks.c.run_id == run_id, tasks.c.status == "succeeded")
            ).mappings()
        ]
        data = [
            dict(row)
            for row in connection.execute(
                select(observations).where(
                    observations.c.task_id.in_(producers),
                    observations.c.feature_key.in_(OBSERVATION_KEYS.values()),
                    observations.c.start_ms < 3000,
                    observations.c.numeric_value.is_not(None),
                )
            ).mappings()
        ]
        values = {
            feature: float(
                np.median([row["numeric_value"] for row in data if row["feature_key"] == key])
            )
            for feature, key in OBSERVATION_KEYS.items()
            if any(row["feature_key"] == key for row in data)
        }
        evidence_ids: list[str] = list(
            connection.scalars(
                select(evidence.c.id)
                .where(
                    evidence.c.subject_type == "observation",
                    evidence.c.subject_id.in_([row["id"] for row in data]),
                )
                .order_by(evidence.c.id)
            )
        )
        result[media_id] = {"run_id": run_id, "features": values, "evidence_ids": evidence_ids}
    return result


def analyze_account(
    application: Application,
    account_id: str,
    spec: PerformanceSpec | None,
    *,
    analyze_media: bool = False,
    media_options: AnalysisOptions | None = None,
    max_posts: int = 100,
    reproduce_run: str | None = None,
) -> dict[str, Any]:
    if max_posts < 1 or max_posts > 1000:
        raise ConfigurationError("max-posts must be between 1 and 1000")
    if reproduce_run:
        return reproduce(application, reproduce_run, account_id)
    if spec is None:
        raise ConfigurationError("An explicit performance specification is required")
    with application.database.transaction() as connection:
        _validate_definitions(connection, spec)
    batch = (
        _batch_media(
            application, account_id, media_options or AnalysisOptions(no_ai=True), max_posts
        )
        if analyze_media
        else []
    )
    rows, definitions = build_population(application, spec, account_ids=[account_id])
    return _persist_analysis(
        application, rows, definitions, spec, "account", account_id, batch=batch
    )


def compare(
    application: Application,
    kind: Literal["posts", "accounts"],
    left: list[str],
    right: list[str],
    spec: PerformanceSpec,
) -> dict[str, Any]:
    if not left or not right or set(left).intersection(right):
        raise ConfigurationError("Comparison requires two nonempty, disjoint ID groups")
    roles = {**{item: "left" for item in left}, **{item: "right" for item in right}}
    rows, definitions = build_population(
        application,
        spec,
        roles=roles,
        account_ids=left + right if kind == "accounts" else None,
        post_ids=left + right if kind == "posts" else None,
    )
    if not any(row["role"] == "left" for row in rows) or not any(
        row["role"] == "right" for row in rows
    ):
        raise ConfigurationError(
            "Both comparison groups must contain posts with the requested platform definition"
        )
    return _persist_analysis(
        application,
        rows,
        definitions,
        spec,
        "comparison",
        stable_id("comparison", kind, canonical_json(roles)),
        comparing=True,
    )


def _batch_media(
    application: Application, account_id: str, options: AnalysisOptions, max_posts: int
) -> list[dict[str, Any]]:
    from socialdna.application.analysis_service import analyze_video
    from socialdna.application.import_service import import_local

    with application.database.transaction() as connection:
        accounts, posts, references, links = (
            metadata.tables[name]
            for name in ("accounts", "posts", "media_references", "post_media")
        )
        if not connection.scalar(select(accounts.c.id).where(accounts.c.id == account_id)):
            raise ConfigurationError("Unknown account ID")
        post_ids: list[str] = list(
            connection.scalars(
                select(posts.c.id)
                .where(posts.c.account_id == account_id)
                .order_by(posts.c.published_at, posts.c.id)
            )
        )
        selected_ids = post_ids[:max_posts]
        refs = [
            dict(row)
            for row in connection.execute(
                select(references)
                .where(references.c.post_id.in_(selected_ids))
                .order_by(references.c.post_id, references.c.position)
            ).mappings()
        ]
        linked = {
            (row["post_id"], row["position"]): row["media_asset_id"]
            for row in connection.execute(
                select(links).where(links.c.post_id.in_(selected_ids))
            ).mappings()
        }
    batch = [
        {"post_id": item, "position": 0, "status": "skipped", "message": "Batch max-posts limit"}
        for item in post_ids[max_posts:]
    ]
    refs_by_key = {(row["post_id"], row["position"]): row for row in refs}
    for key, media_id in linked.items():
        refs_by_key.setdefault(key, {"post_id": key[0], "position": key[1], "media_id": media_id})
    referenced_posts = {key[0] for key in refs_by_key}
    batch.extend(
        {
            "post_id": post_id,
            "position": 0,
            "status": "skipped",
            "message": "No media reference or linked local video",
        }
        for post_id in selected_ids
        if post_id not in referenced_posts
    )
    for row in sorted(refs_by_key.values(), key=lambda item: (item["post_id"], item["position"])):
        entry: dict[str, Any] = {"post_id": row["post_id"], "position": row["position"]}
        try:
            if "uri" in row:
                uri = urlparse(row["uri"])
                if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
                    raise ConfigurationError(
                        "Remote media is reference-only; no download is attempted"
                    )
                # url2pathname handles Windows drive letters without shell execution.
                path = Path(url2pathname(uri.path))
                imported = import_local(application, path)
                media_id = imported["media_id"]
                with application.database.transaction() as connection:
                    statement = insert(links).values(
                        post_id=row["post_id"],
                        position=row["position"],
                        media_asset_id=media_id,
                        role="primary" if row["position"] == 0 else "additional",
                    )
                    connection.execute(
                        statement.on_conflict_do_update(
                            index_elements=[links.c.post_id, links.c.position],
                            set_={"media_asset_id": media_id},
                        )
                    )
            else:
                media_id = row["media_id"]
            result = analyze_video(application, media_id, options=options)
            entry.update(media_run_id=result["run_id"], status=result["status"])
        except SocialDNAError as exc:
            entry.update(status="failed", message=str(exc))
        batch.append(entry)
    return batch


def _persist_analysis(
    application: Application,
    rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    spec: PerformanceSpec,
    target_type: str,
    target_id: str,
    *,
    comparing: bool = False,
    batch: list[dict[str, Any]] | None = None,
    reproduced_from: str | None = None,
) -> dict[str, Any]:
    run_id, now = new_id(), utc_now()
    version_info = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "scipy", "pandas", "statsmodels", "scikit-learn")
    }
    configuration = {
        "spec": spec.model_dump(mode="json"),
        "input_hash": hash_config({"rows": rows, "definitions": definitions}),
        "engine_version": __version__,
        "libraries": version_info,
        "feature_registry": FEATURE_REGISTRY,
        "reproduced_from": reproduced_from,
    }
    # Commit the whole analysis atomically; interruption cannot create phantom success.
    results = analyze_rows(rows, spec, comparing=comparing)
    if any(row["creator_identity"] == "account_proxy" for row in rows):
        results["limitations"].append(
            "Some creators are unknown: account proxy clusters may overcount independent creators."
        )
    if batch and any(row["status"] != "success" for row in batch):
        results["limitations"].append(
            "Media batch has failed/skipped entries; missing content features remain missing."
        )
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "report_type": "performance",
        "run_id": run_id,
        "target_type": target_type,
        "target_id": target_id,
        "status": "partial"
        if batch and any(row["status"] != "success" for row in batch)
        else "success",
        "analysis_configuration": configuration,
        "metric_definitions": definitions,
        "results": results,
        "posts": rows,
        "batch": batch or [],
        "limitations": results["limitations"],
    }
    cohort_id, analysis_id = stable_id("cohort", run_id), stable_id("statistics", run_id)
    pairs = match_pairs(rows, spec) if comparing and spec.matched else []
    match_ids = {post_id: str(index) for index, pair in enumerate(pairs) for post_id in pair}
    with application.database.transaction() as connection:
        connection.execute(
            metadata.tables["analysis_runs"]
            .insert()
            .values(
                id=run_id,
                target_type=target_type,
                target_id=target_id,
                depth="standard",
                profile_version="performance-1",
                config_json=canonical_json(configuration),
                config_hash=hash_config(configuration),
                status="failed" if report["status"] == "partial" else "succeeded",
                created_at=now,
                started_at=now,
                finished_at=utc_now(),
            )
        )
        connection.execute(
            metadata.tables["cohorts"]
            .insert()
            .values(
                id=cohort_id,
                name=f"{target_type}:{target_id}",
                population_spec_json=canonical_json(configuration),
                created_by_run_id=run_id,
            )
        )
        for row in rows:
            connection.execute(
                metadata.tables["cohort_members"]
                .insert()
                .values(
                    cohort_id=cohort_id,
                    post_id=row["post_id"],
                    role=row["role"],
                    match_set_id=match_ids.get(row["post_id"]),
                    input_json=canonical_json(row),
                )
            )
            connection.execute(
                metadata.tables["derived_metrics"]
                .insert()
                .values(
                    id=stable_id("derived-metric", run_id, row["post_id"]),
                    post_id=row["post_id"],
                    metric_key=spec.metric_key,
                    value=row["outcome"],
                    formula_version="aligned-rate-or-value-1",
                    input_ids_json=canonical_json(row["snapshot_ids"]),
                    run_id=run_id,
                )
            )
        connection.execute(
            metadata.tables["statistical_analyses"]
            .insert()
            .values(
                id=analysis_id,
                method=spec.model,
                spec_json=canonical_json(configuration),
                outcome_key=spec.metric_key,
                status=results["regression"]["status"],
                result_json=canonical_json(report),
                run_id=run_id,
            )
        )
        for index, term in enumerate(results["correlations"] + results["regression"]["terms"]):
            connection.execute(
                metadata.tables["statistical_results"]
                .insert()
                .values(
                    id=stable_id("statistical-result", run_id, str(index)),
                    analysis_id=analysis_id,
                    term=term["term"],
                    **{
                        key: term.get(key)
                        for key in (
                            "estimate",
                            "standard_error",
                            "ci_low",
                            "ci_high",
                            "p_value",
                            "adjusted_p_value",
                        )
                    },
                    sample_count=term["sample_count"],
                    cluster_count=term["cluster_count"],
                    diagnostics_json=canonical_json(term.get("diagnostics", {})),
                )
            )
        for entry in batch or []:
            connection.execute(
                metadata.tables["account_media_runs"]
                .insert()
                .values(account_run_id=run_id, **entry)
            )
    return report


def reproduce(
    application: Application, run_id: str, account_id: str | None = None
) -> dict[str, Any]:
    report = load_performance_report(application, run_id=run_id)
    if account_id is not None and (
        report["target_type"] != "account" or report["target_id"] != account_id
    ):
        raise ConfigurationError("Reproduction target does not match account")
    if (
        hash_config({"rows": report["posts"], "definitions": report["metric_definitions"]})
        != report["analysis_configuration"]["input_hash"]
    ):
        raise StorageIntegrityError("Frozen performance inputs do not match their stored hash")
    versions = report["analysis_configuration"]["libraries"]
    if report["analysis_configuration"]["engine_version"] != __version__ or any(
        importlib.metadata.version(name) != version for name, version in versions.items()
    ):
        raise ConfigurationError("Exact reproduction requires the original engine/library versions")
    return _persist_analysis(
        application,
        report["posts"],
        report["metric_definitions"],
        PerformanceSpec.model_validate(report["analysis_configuration"]["spec"]),
        report["target_type"],
        report["target_id"],
        comparing=report["target_type"] == "comparison",
        batch=report["batch"],
        reproduced_from=run_id,
    )


def load_performance_report(
    application: Application, *, run_id: str | None = None, account_id: str | None = None
) -> dict[str, Any]:
    with application.database.transaction() as connection:
        analyses, runs = (
            metadata.tables[name] for name in ("statistical_analyses", "analysis_runs")
        )
        query = select(analyses.c.result_json).join(runs, analyses.c.run_id == runs.c.id)
        query = (
            query.where(runs.c.id == run_id)
            if run_id
            else query.where(runs.c.target_type == "account", runs.c.target_id == account_id)
        )
        raw = connection.scalar(query.order_by(runs.c.created_at.desc(), runs.c.id.desc()).limit(1))
        if raw is None:
            raise ConfigurationError("No saved performance analysis; run analyze account first")
        return dict(json.loads(raw))
