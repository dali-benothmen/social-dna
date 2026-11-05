import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialdna.domain.investigation import EvaluationSpec, LiteratureCorpus, StudySpec

CORPUS = Path(__file__).parents[2] / "examples/research/literature.json"


@pytest.mark.parametrize("change", ["quote", "end", "source", "construct", "blank", "doi"])
def test_corpus_rejects_invalid_or_fabricated_bindings(change: str) -> None:
    doc = json.loads(CORPUS.read_text())
    if change == "quote":
        doc["studies"][0]["findings"][0]["quote"] = "Fabricated excerpt"
    elif change == "end":
        doc["studies"][0]["findings"][0]["end_char"] = 1000000
    elif change == "source":
        doc["constructs"][0]["finding_keys"] = ["nonexistent.paper"]
    elif change == "construct":
        doc["operationalizations"][0]["construct_key"] = "invented"
    elif change == "blank":
        doc["studies"][0]["reviewer"] = " "
    else:
        doc["studies"][0]["doi"] = "invented-paper"
    with pytest.raises(ValidationError):
        LiteratureCorpus.model_validate(doc)
    if change == "doi":
        clean = json.loads(CORPUS.read_text())
        original = clean["studies"][0]["doi"]
        clean["studies"][0]["doi"] = original.upper()
        assert LiteratureCorpus.model_validate(clean).studies[0].doi == original
        clean["studies"].append({**clean["studies"][0], "key": "duplicate-edition"})
        with pytest.raises(ValidationError, match="one edition per DOI"):
            LiteratureCorpus.model_validate(clean)
        assert StudySpec.model_validate({**clean["studies"][0], "doi": "10.1234/Ä"}).doi != (
            StudySpec.model_validate({**clean["studies"][0], "doi": "10.1234/ä"}).doi
        )


def test_no_claim_upgrade_or_similarity_sampling_escape_hatch() -> None:
    doc = {
        "protocol": {"kind": "research_protocol", "id": "p", "revision_id": "r"},
        "analysis_run_ids": ["run"],
        "expected_claim_level": "causal",
    }
    with pytest.raises(ValidationError):
        EvaluationSpec.model_validate(doc)
    doc["expected_claim_level"] = "hypothesis"
    doc["retrieved_top_k"] = 5
    with pytest.raises(ValidationError):
        EvaluationSpec.model_validate(doc)
