"""Escaped registration/citation reports; no automatic research conclusions."""

import html
import re
from typing import Any


def _safe(value: Any) -> str:
    return re.sub(r"([\\`*_[\]{}()#+.!|>~-])", r"\\\1", html.escape(str(value)).replace("\n", " "))


def render_research(report: dict[str, Any]) -> str:
    spec = report["question"]["specification"]
    lines = [
        "# Research registration — unevaluated",
        "",
        _safe(spec["question"]),
        "",
        "Population: " + _safe(spec["population"]),
        "",
        "## Draft hypotheses",
        "",
    ]
    for hypothesis in report["hypotheses"]:
        lines.append("- " + _safe(hypothesis["specification"]["statement"]))
    if not report["hypotheses"]:
        lines.append("No hypotheses registered.")
    lines.extend(["", "## Source citations", ""])
    for citation in report["citations"]:
        lines.append("### " + _safe(citation["ref"]["id"]))
        lines.extend(["", "Revision: " + _safe(citation["ref"]["revision_id"]), ""])
        locator = citation["locator"]
        if locator is None:
            lines.append("Withheld: " + _safe("; ".join(citation["limitations"])))
        elif locator["kind"] == "comment_span":
            lines.append("Quoted comment: “" + _safe(locator["quote"]) + "”")
            lines.append(
                f"Characters {locator['start_char']}–{locator['end_char']} (Unicode code points)."
            )
        elif locator["kind"] == "metric_snapshot":
            lines.append(
                "Metric: "
                + _safe(locator["definition"]["id"])
                + "; value: "
                + _safe(locator["value"])
            )
            lines.append("Collected: " + _safe(locator["observed_at"]))
            lines.append(
                "Reporting window: "
                + _safe(locator["window_start"])
                + " to "
                + _safe(locator["window_end"])
            )
        elif locator["kind"] == "media_span":
            interval = locator["interval"]
            lines.append(
                "Media: "
                + _safe(locator["media"]["id"])
                + f"; interval [{interval['start_ms']}, {interval['end_ms']}) ms."
            )
            if locator["excerpt"]:
                lines.append("Excerpt: " + _safe(locator["excerpt"]))
        else:
            lines.append("Typed citation: " + _safe(locator))
        lines.extend(["", "Source: " + _safe(citation["source"]["id"]), ""])
    if report.get("audience_evidence"):
        lines.extend(
            [
                "## Qualified audience evidence",
                "",
                "Collected expressions are not viewer prevalence, verified behavior "
                "or causal mechanisms.",
                "",
            ]
        )
        for item in report["audience_evidence"]:
            lines.append("- " + _safe(item))
    lines.extend(["## Limitations", ""])
    lines.extend("- " + _safe(item) for item in report["limitations"])
    return "\n".join(lines) + "\n"
