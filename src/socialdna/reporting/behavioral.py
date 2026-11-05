"""Human-readable, source-qualified behavioral reports with escaped input text."""

from typing import Any

from socialdna.reporting.markdown import escape


def render_behavioral(report: dict[str, Any]) -> str:
    lines = [
        "# Source-qualified behavioral measurements",
        "",
        "Run: " + escape(report["run_id"]),
        "",
        "These are source-defined aggregate observations, "
        "not independent viewers or causal effects.",
        "",
    ]
    if report["analysis_kind"] == "retention":
        lines += ["## Retention on the original source grid", ""]
        curve = report["series"]
        if curve is None:
            lines.append("Retention was not supplied; scalar views are not a substitute.")
        else:
            lines += [
                escape(report["definition"]["spec"]),
                "",
                escape(curve["spec"]["clock"]),
                "",
                "Source resolution: " + escape(curve["spec"]["resolution"]),
                "",
            ]
            for item in curve["bins"]:
                spec = item["spec"]
                lines.append(
                    "- "
                    + escape(
                        {
                            "ordinal": spec["ordinal"],
                            "source_start": spec["start"],
                            "source_end": spec["end"],
                            "source_point": spec["point"],
                            "result": item["result"],
                            "media_mapping": item["media_mapping"],
                            "evidence": item["evidence"],
                        }
                    )
                )
            if report.get("comparison"):
                lines += [
                    "",
                    "## Exact-grid descriptive comparison",
                    "",
                    escape(report["comparison"]),
                ]
            lines += [
                "",
                "## Collection coverage and creative context",
                "",
                escape(curve["coverage"]),
                "",
                escape(report.get("creative_context")),
            ]
    else:
        lines += [
            "## Account-period change",
            "",
            escape(report["spec"]),
            "",
            "Signed change: " + escape(report["net_change"]),
            "",
            "Start size: " + escape(report["account_size_start"]),
            "",
            "End size: " + escape(report["account_size_end"]),
            "",
            "Account change is not assigned to the nearest post.",
            "",
            "## Supplied conversion attribution",
            "",
            escape(report["attribution"]),
            "",
            "## Genuinely known account context",
            "",
            escape(report["post_context"]),
        ]
    lines += ["", "## Limitations", ""]
    lines.extend("- " + escape(value) for value in report["limitations"])
    return "\n".join(lines) + "\n"
