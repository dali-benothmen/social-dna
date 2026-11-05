"""A platform/surface contract cannot be promoted to ranking-weight recovery."""

import pytest
from pydantic import ValidationError

from socialdna.domain.platform_research import SURFACES, PlatformReportSpec, PlatformScope


def test_platforms_have_distinct_surfaces_and_unsupported_claims_are_rejected() -> None:
    assert SURFACES["instagram"] != SURFACES["youtube"] != SURFACES["tiktok"]
    scope = {
        "platform": "youtube",
        "surface": "shorts",
        "native_format": "video",
        "language": "en",
        "market": "US",
        "niche": "education",
        "audience": "source-defined",
    }
    with pytest.raises(ValidationError, match="Surface"):
        PlatformScope.model_validate({**scope, "surface": "for_you"})
    for claim in ("proprietary_weights", "guaranteed_virality", "causal", "executed_experiment"):
        with pytest.raises(ValidationError):
            PlatformReportSpec.model_validate(
                {
                    "account": {"kind": "account", "id": "a", "revision_id": "a"},
                    "scope": scope,
                    "traffic": "organic",
                    "as_of": "2026-01-01T00:00:00Z",
                    "claim_level": claim,
                }
            )
