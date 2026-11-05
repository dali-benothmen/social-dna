from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.domain.evidence import EntityRef
from socialdna.research.reevaluation import (
    ReevaluationContext,
    ReevaluationSpec,
    compare,
    membership,
)


def test_membership_deduplicates_and_does_not_infer_independence() -> None:
    old = [{"post_id": "a", "creator_id": "creator", "duplicate_group": "bytes"}] * 2
    new = old + [{"post_id": "b", "creator_id": "creator", "duplicate_group": "bytes"}]
    result = membership(old, new)
    assert result["posts"] == {"reused": ["a"], "new": ["b"], "removed": []}
    assert result["creators"]["new"] == []
    assert result["new_posts_with_reused_content"] == ["b"]
    assert result["independent_confirmation"] is False


@pytest.mark.parametrize(
    ("status", "removed", "expected"),
    [
        ("inconclusive", False, "weakened"),
        ("contrary", False, "contradicted_in_scope"),
        ("consistent", True, "weakened"),
        ("consistent", False, "supported_in_scope"),
    ],
)
def test_transition_rubric_is_scoped_not_global_rejection(
    status: str, removed: bool, expected: str
) -> None:
    def assessment(local: str) -> dict[str, Any]:
        return {
            "judgments": [
                {
                    "hypothesis": {"id": "hypothesis"},
                    "prediction": {"direction": "positive"},
                    "local_association": {"status": local, "observations": []},
                }
            ]
        }

    context = ReevaluationContext(
        "request",
        EntityRef(kind="research_assessment", id="a", revision_id="r"),
        {"posts": {"removed": ["a"] if removed else []}},
        [],
        "New data",
    )
    result = compare(assessment("consistent"), assessment(status), context)
    assert result["transitions"][0]["disposition"] == expected
    assert result["independent_confirmation"] is False
    assert result["sequential_policy"] == "exploratory_cumulative_repeat_look"


@pytest.mark.parametrize(
    "payload",
    [
        {"max_analyses": 0},
        {"max_analyses": 5},
        {"reason": " "},
        {"causal_upgrade": True},
        {"designs": []},
        {"protocol": {"kind": "hypothesis", "id": "h", "revision_id": "r"}},
    ],
)
def test_invalid_requests_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ReevaluationSpec.model_validate(payload)
