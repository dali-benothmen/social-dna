"""Escaped static-media reports, never a fabricated video timeline."""

import html
from typing import Any


def escaped(value: Any) -> str:
    result = html.escape(str(value), quote=True).replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "|", "#", ">"):
        result = result.replace(character, "\\" + character)
    return result.replace("\r", "").replace("\n", " ")


def render_static(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['report_type'].title()} analysis",
        "",
        f"Run: {escaped(report['run_id'])}",
        "",
        f"Status: {escaped(report['status'])}",
        "",
    ]
    if report["report_type"] == "image":
        info = report["metadata"]
        lines.extend(
            [
                f"Display orientation: {info['width']} × {info['height']} pixels",
                "",
                "## Appearance measurements",
                "",
            ]
        )
        for key in ("brightness", "contrast", "saturation", "edge_density", "aspect_ratio"):
            lines.append(f"- {key}: {report['features'][key]:.4f}")
        lines.extend(["", "## OCR estimates", "", escaped(report["ocr"]["status"]), ""])
        lines.extend(escaped(box["text"]) for box in report["ocr"]["boxes"])
    else:
        lines.extend(
            [
                "## Supplied text",
                "",
                "Caption: " + escaped(report["text"]["caption"] or "Not supplied"),
                "",
                "Hashtags: " + escaped(", ".join(report["text"]["hashtags"])),
                "",
            ]
        )
        for item in report["items"]:
            lines.extend(
                [
                    f"## Item at position {item['position']} (zero-based)",
                    "",
                    "Status: " + escaped(item["status"]),
                    "",
                ]
            )
            if item["message"]:
                lines.extend([escaped(item["message"]), ""])
            lines.extend(
                [
                    "Alternative text (source supplied): "
                    + escaped(
                        item["alternative_text"]["value"]
                        if item["alternative_text"]["value"] is not None
                        else "Not supplied"
                    ),
                    "",
                ]
            )
            if item.get("ocr"):
                lines.extend(["OCR (model estimate): " + escaped(item["ocr"]["status"]), ""])
                lines.extend(escaped(box["text"]) for box in item["ocr"]["boxes"])
            lines.extend(["Evidence: " + escaped(item["evidence"]["id"]), ""])
        lines.extend(["## Declared aggregation", "", escaped(report["aggregate"]), ""])
    lines.extend(
        [
            "## Review prompts",
            "",
            "- Review readability and crop at the intended viewing size; "
            "numeric proxies do not establish quality.",
            "- Compare variants under a separately specified performance analysis "
            "rather than assuming these measurements predict success.",
            "",
            "## Limits",
            "",
        ]
    )
    lines.extend("- " + escaped(limit) for limit in report["limitations"])
    lines.extend(["", "Evidence: " + escaped(report["evidence"]["id"]), ""])
    return "\n".join(lines)
