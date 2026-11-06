"""Readable source observations, not an invented content or performance analysis."""

from socialdna.domain.workflows import WorkflowReport
from socialdna.reporting.markdown import escape


def render(report: WorkflowReport) -> str:
    lines = [
        "# YouTube source-qualified post report",
        "",
        "Coverage: **source-only native metadata**. No video, audio or comments were analyzed.",
        "",
        f"Source: {report.canonical_url}",
        f"Workflow: {report.workflow_id}",
        f"Captured: {report.captured_at}",
        f"Retention deadline: {report.expires_at}",
        "",
        "Goal: " + escape(report.goal).replace("\n", " "),
        "",
        "## Native API fields",
        "",
    ]
    for field in report.fields:
        value = field.value if field.value is not None else "Unknown — not returned by the API"
        lines.extend(
            [
                f"- {escape(field.path)}: {escape(value).replace(chr(10), ' ')}",
                f"  Evidence: {field.evidence.id} / revision {field.evidence.revision_id}",
            ]
        )
    lines.extend(["", "## Coverage and limitations", ""])
    lines.extend("- " + escape(item) for item in report.limitations)
    if not report.request_fulfilled:
        lines.extend(
            ["", "The requested natural-language analysis is not established by this capture."]
        )
        lines.extend("Next action: " + escape(item.message) for item in report.required_actions)
    lines.extend(
        [
            "",
            "Native counts are not engagement rates or evidence of why this post succeeded.",
            "Exports/backups require separate retention and eligibility checks before reuse.",
            "",
        ]
    )
    return "\n".join(lines)
