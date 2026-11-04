import re
from difflib import SequenceMatcher
from typing import Any

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.domain.providers import ReasoningResult


def compare_text_tracks(first: str, second: str) -> float:
    # Symmetric token agreement is not WER or transcription accuracy without a gold reference.
    a, b = re.findall(r"\w+", first.casefold()), re.findall(r"\w+", second.casefold())
    return (
        SequenceMatcher(a=a, b=b, autojunk=False).ratio()
        + SequenceMatcher(a=b, b=a, autojunk=False).ratio()
    ) / 2


def persist_interpretations(
    result: ReasoningResult, evidence: list[dict[str, Any]], context: TaskContext
) -> TaskOutput:
    by_id = {item["id"]: item for item in evidence}
    for interpretation in result.interpretations:
        cited = [by_id[key] for key in interpretation.evidence_ids]
        context.observe(
            "model." + interpretation.modality + ".interpretation",
            {
                **interpretation.model_dump(),
                "claim_level": "hypothesis",
                "confidence_method": "ordinal, uncalibrated model assessment",
            },
            min(item["start_ms"] for item in cited),
            max(item["end_ms"] for item in cited),
            modality=interpretation.modality,
            unit="interpretation",
            description="Evidence-bound model hypothesis, "
            "not a deterministic observation or causal claim.",
        )
    context.output.result = {
        "interpretations": len(result.interpretations),
        "limitations": result.limitations
        + ["Model interpretations are uncalibrated hypotheses requiring human review."],
    }
    return context.output
