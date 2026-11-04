import html
import re
from typing import Any

from socialdna.reporting.models import VideoReport


def escape(value: Any) -> str:
    return re.sub(r"([\\`*_{}\[\]()#!|>])", r"\\\1", html.escape(str(value), quote=True))


def timestamp(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    return f"{minutes:02}:{remainder / 1000:06.3f}"


def render_markdown(report: VideoReport) -> str:
    lines = [
        f"# Video analysis: {escape(report.title)}",
        "",
        f"Run: `{report.run_id}`",
        f"Media: `{report.media_id}`",
        f"Status: {report.status}",
        "",
        report.interpretation,
        "",
        "## Execution",
        "",
    ]
    for task in report.tasks:
        state = "cached" if task.get("reused_from_task_id") else task["status"]
        lines.append(f"- {escape(task['task_key'])}: {state}")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {escape(item)}" for item in report.limitations)
    lines += ["", "## Evidence frames", ""]
    for artifact in report.artifacts:
        if artifact["kind"] == "contact-sheet":
            lines.extend([f"[Contact sheet preview]({artifact['uri']})", ""])
    frame_evidence = {
        item["subject_id"]: item["id"]
        for item in report.timeline["evidence_items"]
        if item["subject_type"] == "frame"
    }
    for frame in report.timeline["frames"]:
        lines.append(
            f"- {timestamp(frame['timestamp_ms'])}: `{frame_evidence[frame['id']]}` "
            f"[frame]({frame['artifact_uri']})"
        )
    lines += ["", "## Supplied subtitles", ""]
    text_evidence = {
        item["subject_id"]: item["id"]
        for item in report.timeline["evidence_items"]
        if item["subject_type"] == "text_segment"
    }
    for segment in report.timeline["text_segments"]:
        lines.append(
            f"- {timestamp(segment['start_ms'])}–{timestamp(segment['end_ms'])}: "
            + escape(segment["text"])
            + f" (evidence `{text_evidence[segment['id']]}`)"
        )
    lines += [
        "",
        "## Measurements",
        "",
        "Values are algorithm-defined measurements, not interpretations.",
        "",
    ]
    evidence = {
        item["subject_id"]: item["id"]
        for item in report.timeline["evidence_items"]
        if item["subject_type"] == "observation"
    }
    units = {definition["key"]: definition["unit"] for definition in report.feature_definitions}
    for observation in report.timeline["observations"][:250]:
        lines.append(
            f"- {timestamp(observation['start_ms'])}–{timestamp(observation['end_ms'])} "
            f"{escape(observation['feature_key'])}: {escape(observation['value'])} "
            f"{escape(units[observation['feature_key']])} "
            f"(evidence `{evidence[observation['id']]}`)"
        )
    if len(report.timeline["observations"]) > 250:
        lines.append("Additional measurements are included in the complete JSON report.")
    return "\n".join(lines) + "\n"
