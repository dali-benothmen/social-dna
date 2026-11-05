"""Bounded journal-driven watches and immutable predecessor/successor relationships.

R6 indexing work is drained; its events are mirrored into a separate append-only
research journal. A stale watch is the pending work queue; no analysis runs
during an import or a freshness check.
"""

import json
from typing import Any

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.exceptions import ConfigurationError, StorageIntegrityError
from socialdna.core.hashing import canonical_json
from socialdna.core.time import utc_now
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.memory.documents import references
from socialdna.storage.evidence_repository import EvidenceRepository
from socialdna.storage.schema import metadata


def tokens(value: Any, key: str = "") -> set[str]:
    """Only structural identifiers, never arbitrary text/quotes as change keys."""
    if isinstance(value, dict):
        return set().union(*(tokens(v, k) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return set().union(*(tokens(v, key) for v in value))
    if isinstance(value, str) and (key == "id" or key.endswith(("_id", "_ids"))):
        return {value}
    return set()


def selector(report: dict[str, Any]) -> dict[str, Any]:
    if report["target_type"] == "account":
        return {"account_ids": [report["target_id"]], "post_ids": None, "roles": None}
    # Older comparisons did not retain their pre-query groups. Do not invent
    # account-wide membership from a possibly filtered list of selected posts.
    return report.get("population_selector") or {
        "account_ids": None,
        "post_ids": sorted({r["post_id"] for r in report["posts"]}),
        "roles": {r["post_id"]: r["role"] for r in report["posts"]},
        "legacy_scope": "frozen_post_membership_only",
    }


def track(
    connection: Connection, ref: EntityRef, payload: dict[str, Any], reports: list[dict[str, Any]]
) -> None:
    table = metadata.tables["assessment_watches"]
    if connection.scalar(
        select(table.c.assessment_revision_id).where(
            table.c.assessment_revision_id == ref.revision_id
        )
    ):
        return
    repo = EvidenceRepository(connection)
    identifiers = tokens(payload)
    pending = list(references(payload))
    seen: set[str] = set()
    # Include transitive literature, constructs, recipes, sources and citations,
    # not only the R7 projection's direct statistical-analysis dependencies.
    while pending:
        _, dependency = pending.pop()
        if dependency.revision_id in seen:
            continue
        seen.add(dependency.revision_id)
        if len(seen) > 20000:
            raise ConfigurationError("Assessment dependency budget exceeds 20,000 revisions")
        if isinstance(dependency, EvidenceRef):
            row = repo.get("evidence_revisions", dependency.revision_id)
            document = json.loads(row["locator_json"])
            identifiers.add(row["evidence_id"])
        else:
            row = repo.entity(dependency)
            document = json.loads(row["payload_json"])
            identifiers.add(row["entity_id"])
        identifiers.update(tokens(dict(row)))
        identifiers.update(tokens(document))
        pending.extend(references(document))
    manifests = []
    for report in reports:
        identifiers.update(tokens(report["posts"]))
        identifiers.update(tokens(report["reference_population"]))
        identifiers.update(d["key"] for d in report["metric_definitions"])
        versions = metadata.tables["post_media_versions"]
        associations = {
            row["post_id"]: dict(row)
            for row in connection.execute(
                select(versions)
                .where(
                    versions.c.post_id.in_(
                        {r["post_id"] for r in report["posts"] + report["reference_population"]}
                    ),
                    versions.c.position == 0,
                    versions.c.available_at
                    <= report["analysis_configuration"]["spec"]["knowledge_cutoff"],
                )
                .order_by(versions.c.available_at, versions.c.id)
            ).mappings()
        }
        for association in associations.values():
            identifiers.update(tokens(association))
        selection = selector(report)
        identifiers.update(tokens(selection))
        manifests.append(
            {
                "run_id": report["run_id"],
                "selector": selection,
                "spec": report["analysis_configuration"]["spec"],
                "reference_account_ids": sorted(
                    {r["account_id"] for r in report["reference_population"]}
                ),
                "reference_creator_ids": sorted(
                    {r["creator_id"] for r in report["reference_population"]}
                ),
            }
        )
    journal = metadata.tables["research_changes"]
    # An analysis may be older than its assessment, and a request may resume
    # after another import. Start at the earliest frozen knowledge cutoff, not
    # assessment publication time; otherwise arrivals in that gap disappear.
    cutoff = min(item["spec"]["knowledge_cutoff"] for item in manifests)
    baseline = (
        connection.scalar(select(func.max(journal.c.seq)).where(journal.c.captured_at <= cutoff))
        or 0
    )
    connection.execute(
        insert(table)
        .values(
            assessment_revision_id=ref.revision_id,
            manifest_json=canonical_json(manifests),
            baseline_seq=baseline,
            cursor=baseline,
            tokens_json=canonical_json(sorted(identifiers)),
            state="current",
            reasons_json="[]",
        )
        .on_conflict_do_nothing()
    )


def _change(
    connection: Connection,
    event: dict[str, Any],
    identifiers: set[str],
    manifests: list[dict[str, Any]],
) -> tuple[str | None, set[str]]:
    repo = EvidenceRepository(connection)
    identity, kind = event["target_id"], event["kind"]
    if kind == "entity":
        if identity in identifiers:
            return None, set()  # Already frozen, including protocol/literature inputs.
        row = repo.get("entity_revisions", identity)
        entity_kind = row["kind"]
        if entity_kind in (
            "research_assessment",
            "research_finding",
            "experiment_brief",
            "statistical_analysis",
            "citation_report",
        ):
            return None, set()
        document = json.loads(row["payload_json"])
        if entity_kind == "metric_snapshot" and row["entity_id"] not in identifiers:
            metric_keys = {
                key
                for manifest in manifests
                for key in (
                    manifest["spec"]["metric_key"],
                    *manifest["spec"].get("numerator_keys", []),
                    manifest["spec"].get("denominator_key"),
                )
                if key
            }
            if (
                document.get("subject_id") not in identifiers
                or document.get("metric_key") not in metric_keys
            ):
                return None, set()
        related = tokens(document) - {document.get("provenance_id"), document.get("source_id")}
        if row["entity_id"] not in identifiers and not related.intersection(identifiers):
            return None, set()
        if entity_kind == "post" and row["entity_id"] not in identifiers:
            # A newly captured post must fit at least one dynamic selector. This
            # detects rows which could never be found by reverse dependencies.
            fits = False
            for manifest in manifests:
                selection, spec = manifest["selector"], manifest["spec"]
                reference_account = document["account_id"] in manifest.get(
                    "reference_account_ids", []
                )
                if not reference_account:
                    account = repo.latest("account", document["account_id"])
                    if account:
                        creator_id = json.loads(repo.entity(account)["payload_json"]).get(
                            "creator_id"
                        )
                        reference_account = creator_id in manifest.get("reference_creator_ids", [])
                selected_account = not selection["post_ids"] and (
                    not selection["account_ids"]
                    or document["account_id"] in selection["account_ids"]
                )
                if not selected_account and not reference_account:
                    continue
                if (
                    document.get("published_at")
                    and document["published_at"] > spec["publication_cutoff"]
                ):
                    continue
                population = spec["population"]
                if any(
                    population.get(k) and document.get(field) not in population[k]
                    for k, field in (("platforms", "platform"), ("content_types", "content_type"))
                ):
                    continue
                if population.get("topics") and not set(population["topics"]).intersection(
                    document.get("topics") or []
                ):
                    continue
                fits = True
            if not fits:
                return None, set()
        reason = (
            "literature_changed"
            if entity_kind in ("literature_source", "study_finding")
            else "annotation_or_recipe_changed"
            if entity_kind.startswith(("creative_", "reaction_", "operationalization"))
            else "metric_changed"
            if entity_kind.startswith(("metric_", "behavioral_"))
            else "specification_changed"
            if entity_kind in ("research_protocol", "hypothesis", "psychological_construct")
            else "audience_changed"
            if entity_kind.startswith(("comment", "audience_", "content_reaction"))
            else "population_or_context_changed"
        )
        return reason, related | {row["entity_id"], identity} | (
            {row["source_id"]} if row["source_id"] else set()
        )
    if kind == "evidence":
        # Creating another locator for the same data does not change a result.
        return None, set()
    if kind == "association":
        row = repo.get("post_media_versions", identity)
        if row["post_id"] in identifiers:
            return "media_association_changed", tokens(row)
    if kind == "model_run":
        row = repo.get("analysis_runs", identity)
        if row["target_id"] in identifiers:
            return "model_changed", tokens(row)
    if kind == "eligibility":
        withdrawals = metadata.tables["evidence_withdrawals"]
        withdrawal = (
            connection.execute(select(withdrawals).where(withdrawals.c.id == identity))
            .mappings()
            .first()
        )
        sources = metadata.tables["source_records"]
        imported_source = connection.scalar(select(sources.c.id).where(sources.c.id == identity))
        if (identity in identifiers and not imported_source) or (
            withdrawal and tokens(dict(withdrawal)) & identifiers
        ):
            return "eligibility_changed", set()
    return None, set()


def refresh(connection: Connection, revision_id: str, *, limit: int = 10000) -> dict[str, Any]:
    if not 1 <= limit <= 10000:
        raise ConfigurationError("Freshness checks allow 1–10,000 journal entries")
    watches, changes = (metadata.tables[n] for n in ("assessment_watches", "research_changes"))
    watch = (
        connection.execute(select(watches).where(watches.c.assessment_revision_id == revision_id))
        .mappings()
        .first()
    )
    if not watch:
        repo = EvidenceRepository(connection)
        row = repo.get("entity_revisions", revision_id)
        try:
            ref = repo.ref(row)
            payload = json.loads(repo.entity(ref)["payload_json"])
            analyses = metadata.tables["statistical_analyses"]
            reports = [
                json.loads(
                    connection.execute(
                        select(analyses.c.result_json).where(analyses.c.run_id == item["run_id"])
                    ).scalar_one()
                )
                for item in payload["population_manifests"]
            ]
            track(connection, ref, payload, reports)
        except ConfigurationError:
            return {"state": "ineligible", "reasons": [], "pending_changes": False}
        watch = (
            connection.execute(
                select(watches).where(watches.c.assessment_revision_id == revision_id)
            )
            .mappings()
            .one()
        )
    if watch["state"] == "superseded":
        return {
            "state": "superseded",
            "reasons": json.loads(watch["reasons_json"]),
            "pending_changes": False,
        }
    entries = list(
        connection.execute(
            select(changes)
            .where(changes.c.seq > watch["cursor"])
            .order_by(changes.c.seq)
            .limit(limit + 1)
        ).mappings()
    )
    more = len(entries) > limit
    identifiers = set(json.loads(watch["tokens_json"]))
    reasons = json.loads(watch["reasons_json"])
    manifests = json.loads(watch["manifest_json"])
    for entry in entries[:limit]:
        reason, extra = _change(connection, dict(entry), identifiers, manifests)
        if reason:
            identifiers.update(extra)
            if len(reasons) < 200:
                reasons.append(
                    {"kind": reason, "journal_seq": entry["seq"], "target_id": entry["target_id"]}
                )
    state = "stale" if reasons else "current"
    connection.execute(
        watches.update()
        .where(watches.c.assessment_revision_id == revision_id)
        .values(
            cursor=entries[min(len(entries), limit) - 1]["seq"] if entries else watch["cursor"],
            tokens_json=canonical_json(sorted(identifiers)),
            state=state,
            reasons_json=canonical_json(reasons),
        )
    )
    return {
        "state": "stale" if more else state,
        "reasons": reasons,
        "pending_changes": more,
        "reason_limit_reached": len(reasons) >= 200,
    }


def complete(
    connection: Connection, request_id: str, previous: EntityRef, successor: EntityRef
) -> None:
    request = EvidenceRepository(connection).get("reevaluation_requests", request_id)
    if request["previous_revision_id"] != previous.revision_id or request["status"] != "running":
        raise StorageIntegrityError("Reevaluation request/lineage mismatch")
    connection.execute(
        metadata.tables["assessment_transitions"]
        .insert()
        .values(
            request_id=request_id,
            previous_revision_id=previous.revision_id,
            next_revision_id=successor.revision_id,
            created_at=utc_now(),
        )
    )
    connection.execute(
        metadata.tables["assessment_watches"]
        .update()
        .where(
            metadata.tables["assessment_watches"].c.assessment_revision_id == previous.revision_id
        )
        .values(state="superseded")
    )
    connection.execute(
        metadata.tables["reevaluation_requests"]
        .update()
        .where(metadata.tables["reevaluation_requests"].c.id == request_id)
        .values(status="completed", result_revision_id=successor.revision_id, error_type=None)
    )
    # Derived projections are notified; their existing hydration gates also
    # reject a late index job for a superseded assessment/finding.
    connection.execute(
        metadata.tables["memory_changes"]
        .insert()
        .values(kind="supersession", target_id=previous.revision_id)
    )


def current(connection: Connection, ref: EntityRef, as_of: str | None = None) -> bool:
    row = EvidenceRepository(connection).entity(ref)
    if ref.kind == "research_assessment":
        revision_id = ref.revision_id
    elif ref.kind in ("research_finding", "experiment_brief"):
        revision_id = json.loads(row["payload_json"])["assessment"]["revision_id"]
    else:
        return True
    if as_of:
        transitions = metadata.tables["assessment_transitions"]
        return not bool(
            connection.scalar(
                select(transitions.c.request_id).where(
                    transitions.c.previous_revision_id == revision_id,
                    transitions.c.created_at <= as_of,
                )
            )
        )
    return refresh(connection, revision_id)["state"] in ("current", "untracked")


def head(connection: Connection, ref: EntityRef) -> EntityRef:
    transitions = metadata.tables["assessment_transitions"]
    for _ in range(1000):
        successor = connection.scalar(
            select(transitions.c.next_revision_id).where(
                transitions.c.previous_revision_id == ref.revision_id
            )
        )
        if not successor:
            return ref
        repo = EvidenceRepository(connection)
        ref = repo.ref(repo.get("entity_revisions", successor))
    raise StorageIntegrityError("Assessment history exceeds its 1,000-revision budget")
