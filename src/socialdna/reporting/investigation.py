"""Deterministic escaped assessment reports; claims are structured, not free model prose."""

from typing import Any

from socialdna.reporting.research import _safe


def render_assessment(report: dict[str, Any]) -> str:
    lines = [
        "# Evidence-constrained research assessment",
        "",
        _safe(report["question_text"]),
        "",
        "Claim level: " + _safe(report["claim_level"]),
        "",
        "No psychological mediator or causal effect is identified.",
        "",
    ]
    for item in report["judgments"]:
        lines.extend(
            [
                "## Rival: " + _safe(item["hypothesis_statement"]),
                "",
                "Prediction: " + _safe(item["prediction"]["contrast"]),
                "",
                "Local association: " + _safe(item["local_association"]["status"]),
                "",
                "Scoped supporting/contradicting/context evidence: "
                + _safe(item["evidence_roles"]),
                "",
                "Literature: " + _safe(item["literature"]),
                "",
                "Mechanism: " + _safe(item["mechanism_status"]),
                "",
                "Extraction reliability: " + _safe(item["extraction_reliability"]),
                "",
                "Generalization: " + _safe(item["generalization"]),
                "",
                "Statistical evidence: " + _safe(item["local_association"]["observations"]),
                "",
                "Counterexamples: " + _safe(item["counterexamples"]),
                "",
                "Confounders: " + _safe(item["confounders"]),
                "",
                "What would change this conclusion: " + _safe(item["what_would_change_conclusion"]),
                "",
            ]
        )
    for title, key in (
        ("Frozen populations and test history", "population_manifests"),
        ("Audience and behavioral observations", "supplementary_evidence"),
        ("Proposed discriminating experiment — not executed", "experiment_proposal"),
        ("Reviewed source bibliography", "bibliography"),
        ("Production, distribution, publishing and profile context", "context"),
    ):
        lines.extend(["## " + title, "", _safe(report[key]), ""])
    lines.extend(["## Exact citations", ""])
    for citation in report["citations"]:
        lines.extend(["- " + _safe(citation["ref"]) + ": " + _safe(citation["locator"]), ""])
    lines.extend(["## Limitations", "", *("- " + _safe(x) for x in report["limitations"])])
    return "\n".join(lines) + "\n"
