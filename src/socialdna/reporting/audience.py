from typing import Any

from socialdna.reporting.markdown import escape


def render_audience(report: dict[str, Any]) -> str:
    lines = [
        "# Collected audience reactions",
        "",
        "Run: " + escape(report["run_id"]),
        "",
        "Counts describe collected comments, not viewers or verified behavior.",
        "",
        "## Collection and coverage",
        "",
        escape(report["collection_ref"]),
        "",
        escape(
            {
                key: report["collection"][key]
                for key in (
                    "sampling_method",
                    "ordering",
                    "declared_frame",
                    "completeness",
                    "pagination_complete",
                    "truncated",
                    "known_total",
                    "deleted_moderated_coverage",
                )
            }
        ),
        "",
        "## Population and annotation coverage",
        "",
        escape(report["counts"]),
        "",
        "## Qualified observed annotations",
        "",
    ]
    for label, values in report["rates"].items():
        lines.append(
            f"- {escape(label)}: {values['confirmed_reviewed_annotation_count']} confirmed "
            f"of {values['denominator']} eligible collected comment groups; "
            f"{values['uncertain_or_proposed_count']} uncertain/proposed. "
            "Population prevalence is not estimated."
        )
    reactions = {item["ref"]["revision_id"]: item for item in report["reactions"]}
    lines += ["", "## Preserved reaction evidence", ""]
    for item in report["reactions"]:
        annotation = item["annotation"]
        lines.append(
            f"- {escape(annotation['labels'])} / {escape(annotation['state'])}: "
            f"{escape(annotation['quote'])}; evidence {escape(item['evidence'])}; "
            "negation/irony/ambiguity: "
            + escape([annotation[k] for k in ("negated", "ironic", "ambiguous")])
        )
    lines += ["", "## Clusters, representatives and counterexamples", ""]
    for item in report["clusters"]:
        lines.append(
            f"- {escape(item['cluster']['title'])}: {escape(item['cluster']['summary'])}; "
            f"{escape(item['cluster']['state'])}; evidence {escape(item['evidence'])}"
        )
        for member in item["members"]:
            reaction = reactions[member["reaction"]["revision_id"]]
            lines.append(f"  - {escape(member['role'])}: {escape(reaction['annotation']['quote'])}")
        if not any(m["role"] == "counterexample" for m in item["members"]):
            lines.append("  - No counterexample was supplied; this is not evidence none exists.")
    lines += ["", "## Qualified content links", ""]
    for item in report["links"]:
        link = item["link"]
        lines.append(
            f"- {escape(link['origin'])} / {escape(link['state'])}: "
            f"{escape(link['description'])}; target {escape(link['target'])}; "
            f"uncertainty {escape(link['uncertainty'])}; "
            f"alternatives {escape(link['alternatives'])}; "
            "literal playback reference (not reaction time): "
            + escape(item["playback_reference_ms"])
            + "; actual target context: "
            + escape(item["target_context"])
        )
    lines += ["", "## Limitations", ""]
    lines.extend("- " + escape(value) for value in report["limitations"])
    return "\n".join(lines) + "\n"
