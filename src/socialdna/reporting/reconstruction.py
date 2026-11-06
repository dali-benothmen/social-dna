"""Escaped, human-readable finished-video evidence, not a new inferred screenplay."""

from socialdna.domain.reconstruction import VideoReconstruction
from socialdna.reporting.markdown import escape, timestamp


def render(document: VideoReconstruction) -> str:
    lines = [
        "# Finished-video reconstruction",
        "",
        "Source: " + document.canonical_url,
        "",
        "Goal: " + escape(document.goal),
        "",
        "Coverage: " + document.coverage,
        "",
        f"Run: `{document.run_id}`; media revision: `{document.media.revision_id}`.",
        "",
        "This describes the finished clip, not the original writing document.",
        "",
        "## Modality coverage",
        "",
    ]
    lines += [
        "- " + escape(key) + ": " + escape(value)
        for key, value in document.modality_coverage.items()
    ]
    rows = {row.id: row for row in document.rows}
    sections = []
    if document.options.output in ("transcript", "combined"):
        sections.append(("Transcript lanes", document.transcript_row_ids))
    if document.options.output in ("audiovisual-script", "combined"):
        sections.append(("Audiovisual script", document.audiovisual_row_ids))
    for title, identities in sections:
        lines += ["", "## " + title, ""]
        if not identities:
            lines += ["No selected source cues; see coverage and required actions.", ""]
        for identity in identities:
            row = rows[identity]
            when = "unknown timing" if row.start_ms is None else timestamp(row.start_ms)
            if row.end_ms is not None:
                when += "–" + timestamp(row.end_ms)
            if row.lane == "reviewed_creative":
                when += " (declared anchor; uncertainty retained in JSON)"
            text = "[source text withheld]" if row.text_withheld else row.text
            if text is None:
                key = (
                    row.values.get("feature_key")
                    or row.values.get("meaning")
                    or row.values.get("selection_reason")
                    or row.values.get("technique")
                    or row.lane
                )
                text = str(key)
                if "value" in row.values:
                    text += ": " + str(row.values["value"])
            lines += [
                f"- {when} — {escape(row.lane)} ({escape(row.qualification)}): " + escape(text),
                "  Evidence: " + ", ".join(f"`{ref.id}@{ref.revision_id}`" for ref in row.evidence),
            ]
            if row.track_id:
                lines.append("  Track: `" + row.track_id + "`.")
            if any(word.start_ms is None for word in row.words):
                lines.append("  Some word timings are unknown; no times were invented.")
    lines += ["", "## Candidate track disagreements", ""]
    lines += [
        f"- `{d.left}` vs `{d.right}`: overlapping text differs; not word-aligned or adjudicated."
        for d in document.disagreements
    ] or ["None identified in selected tracks; this is not proof of agreement."]
    lines += ["", "## Required actions", ""]
    lines += ["- " + escape(action.message) for action in document.required_actions] or ["None."]
    lines += ["", "## Limitations", ""]
    lines += ["- " + escape(limitation) for limitation in document.limitations]
    return "\n".join(lines) + "\n"
