"""Readable, escaped rendering of frozen account/comparison reports."""

import json
from typing import Any


def _safe(value: Any) -> str:
    from socialdna.reporting.markdown import escape

    return escape(str(value))


def render_performance(report: dict[str, Any]) -> str:
    results = report["results"]
    lines = [
        "# SocialDNA performance report",
        "",
        f"Run: `{report['run_id']}`",
        "",
        f"Target: `{report['target_id']}`",
        "",
        f"Claim level: {results['claim_level']} (not causal)",
        "",
        f"Usable posts: {results['available_n']} / {results['population_n']}; "
        f"missing: {results['missing_n']}",
        "",
        "## Outcome definitions",
        "",
    ]
    for definition in report["metric_definitions"]:
        lines.append(
            f"- {_safe(definition['key'])}: {_safe(definition['definition'])} "
            f"({definition['unit']}, {definition['measurement']})"
        )
    lines.extend(
        [
            "",
            "## Summary and uncertainty",
            "",
            "```json",
            json.dumps(
                {
                    key: results[key]
                    for key in (
                        "outcome",
                        "outcome_interval",
                        "missingness",
                        "feature_missingness",
                        "observation_age_seconds",
                    )
                },
                indent=2,
            ),
            "```",
            "",
            "## Effects and diagnostics",
            "",
            "```json",
            json.dumps(
                {
                    key: results[key]
                    for key in ("correlations", "regression", "comparison", "validation")
                },
                indent=2,
            ).replace("<", "\\u003c"),
            "```",
            "",
            "## Snapshot and media citations",
            "",
        ]
    )
    for post in report["posts"]:
        lines.extend(
            [
                f"- Post `{post['post_id']}`: {post['availability']}; "
                + ", ".join(
                    f"[metric:{item}](socialdna:metric/{item})" for item in post["snapshot_ids"]
                )
            ]
        )
        for item in post["feature_evidence_ids"]:
            lines.append(f"  - [evidence:{item}](socialdna:evidence/{item})")
        for snapshot in post["snapshots"]:
            lines.append(
                f"  - Snapshot `{snapshot['id']}` — provenance `{snapshot['provenance_id']}`"
            )
            lines.append(
                f"  - Source `{snapshot['source_id']}`: {_safe(snapshot['source_uri'])}; "
                f"{_safe(snapshot['permission_basis'])}; "
                f"raw artifact `{snapshot['raw_artifact_id']}`"
            )
    lines.extend(["", "## Limitations", ""])
    if report["schema_version"] == "2.0":
        lines.extend(
            [
                "",
                "## Baseline references and test ledger",
                "",
                "```json",
                json.dumps(
                    {
                        "baselines": results["creator_baselines"],
                        "test_ledger": report["test_ledger"],
                    },
                    indent=2,
                ).replace("<", "\\u003c"),
                "```",
                "",
                "## Statistical citations",
                "",
            ]
        )
        for citation in report["statistical_evidence"]:
            ref = citation["ref"]
            lines.append(
                f"- {_safe(citation['term'] or citation['diagnostic'])}: "
                f"`{ref['id']}` revision `{ref['revision_id']}`"
            )
        lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {_safe(item)}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "## Frozen analysis specification",
            "",
            "```json",
            json.dumps(report["analysis_configuration"], indent=2).replace("<", "\\u003c"),
            "```",
            "",
        ]
    )
    return "\n".join(lines)
