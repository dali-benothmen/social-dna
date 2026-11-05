"""A qualitative profile judgment is never a measured conversion probability."""

from typing import Any

from socialdna.analytics.funnels import rates
from socialdna.domain.profile import FunnelRate


def test_actual_rate_and_unknown_source_gates() -> None:
    base: dict[str, Any] = {
        "signal": "profile_visits",
        "value": 100,
        "availability": "available",
        "uniqueness": "unique_accounts",
        "cohort": {"id": "cohort", "revision_id": "c"},
        "cohort_known": True,
        "clock": {
            "window_start": "2026-01-01",
            "window_end": "2026-02-01",
            "data_cutoff": "2026-02-01",
        },
        "population_basis": "accounts",
        "unit": "accounts",
        "evidence": {"id": "e", "revision_id": "e"},
    }
    request = FunnelRate(
        numerator="follows",
        denominator="visits",
        source_reports_subset=True,
        linkage_evidence=({"id": "e", "revision_id": "e"},),
    )
    manifest = {
        "join_basis": "source_reported_nested_counts",
        "deduplication": "source_unique_per_window",
    }
    stages = {"visits": base, "follows": {**base, "signal": "follows", "value": 20}}
    assert rates(stages, (request,), manifest)[0]["value"] == 0.2
    cases = [
        {"value": None, "availability": "not_permitted"},
        {"cohort_known": False},
        {"cohort": {"id": "different", "revision_id": "d"}},
        {"uniqueness": "unknown"},
        {"population_basis": "plays"},
        {"unit": "events"},
        {"value": 101},
        {"clock": {**base["clock"], "data_cutoff": None}},
    ]
    for change in cases:
        result = rates(
            {**stages, "follows": {**stages["follows"], **change}}, (request,), manifest
        )[0]
        assert result["value"] is None and result["reason"]
    assert (
        rates(stages, (request.model_copy(update={"source_reports_subset": False}),), manifest)[0][
            "value"
        ]
        is None
    )
    assert (
        rates({**stages, "visits": {**base, "value": 0}}, (request,), manifest)[0]["reason"]
        == "nonpositive_denominator"
    )
