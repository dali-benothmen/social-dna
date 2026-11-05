"""Source availability, public-link minimization and profile/outcome separation."""

import pytest
from pydantic import ValidationError

from socialdna.domain.profile import (
    CRITERIA,
    FunnelContext,
    ProfileLink,
    ProfileReview,
    ProfileSnapshot,
)


def test_profile_unknowns_do_not_invent_inventory_or_visual_evidence() -> None:
    empty = {"state": "not_collected"}
    data = {
        "key": "public",
        "account": {"kind": "account", "id": "a", "revision_id": "a"},
        "clock": {"captured_at": "2026-02-01T00:00:00Z"},
        "username": empty,
        "display_name": empty,
        "bio": empty,
        "category": empty,
        "positioning": empty,
        "declaration_basis": "unknown",
        "photo_state": "not_collected",
        "links_state": "not_collected",
        "pins_state": "not_collected",
    }
    assert ProfileSnapshot.model_validate(data).links == ()
    for changes in (
        {"photo_state": "present"},
        {"links_state": "collected"},
        {"content_pillars": ["invented"]},
    ):
        with pytest.raises(ValidationError):
            ProfileSnapshot.model_validate({**data, **changes})
    for url in (
        "javascript:alert(1)",
        "https://name:secret@example.com/",
        "https://example.com/?access_token=secret",
    ):
        with pytest.raises(ValidationError):
            ProfileLink(key="app", label="app", destination=url)


def test_rubric_cannot_be_a_conversion_score_and_counters_cannot_be_duplicated() -> None:
    review = {
        "key": "review",
        "account": {"kind": "account", "id": "a", "revision_id": "a"},
        "snapshot": {"kind": "profile_snapshot", "id": "s", "revision_id": "s"},
        "reviewer": "fixture",
        "procedure": "literal review",
        "reviewed_at": "2026-02-01T00:00:00Z",
        "outcome_access": "unknown",
        "criteria": [
            {"key": key, "verdict": "unknown", "rationale": "Not observed"} for key in CRITERIA
        ],
    }
    with pytest.raises(ValidationError):
        ProfileReview.model_validate({**review, "conversion_probability": 0.99})
    funnel = {
        "key": "funnel",
        "account": review["account"],
        "clock": {"captured_at": "2026-02-01T00:00:00Z"},
        "definition": {"kind": "funnel_definition", "id": "f", "revision_id": "f"},
        "stages": [
            {
                "key": key,
                "measurement": {"kind": "metric_measurement", "id": "same", "revision_id": "same"},
            }
            for key in ("clicks", "installs")
        ],
    }
    with pytest.raises(ValidationError, match="distinct actual counter"):
        FunnelContext.model_validate(funnel)
