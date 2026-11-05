"""Offsets resolve DST folds; missing zones never acquire a local clock."""

from typing import Any

import pytest
from pydantic import ValidationError

from socialdna.domain.context import ContextClock, PublicationContext, TextField


def publication(**changes: Any) -> PublicationContext:
    return PublicationContext.model_validate(
        {
            "key": "packaging",
            "account": {"kind": "account", "id": "account", "revision_id": "a"},
            "post": {"kind": "post", "id": "post", "revision_id": "p"},
            "clock": {"captured_at": "2026-11-01T00:00:00Z"},
            "published_original": "2026-10-25T02:30:00+02:00",
            "timezone": "Europe/Berlin",
            "native_format": "video",
            "title": {"state": "present", "value": "Crème 🍋"},
            "description": {"state": "not_collected"},
            "caption": {"state": "empty", "value": ""},
            "niche": "cooking",
            "audience": "declared fixture audience",
            **changes,
        }
    )


@pytest.mark.parametrize("offset", ["+02:00", "+01:00"])
def test_dst_fold_is_disambiguated_by_the_original_offset(offset: str) -> None:
    assert (
        publication(published_original="2026-10-25T02:30:00" + offset).timezone == "Europe/Berlin"
    )


@pytest.mark.parametrize(
    "value",
    [
        "2026-03-29T02:30:00+01:00",
        "2026-03-29T02:30:00+02:00",
        "2026-10-25T02:30:00",
        "2026-01-01T00:00:00Z",
    ],
)
def test_nonexistent_local_times_unknown_offsets_and_zone_mismatch_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        publication(published_original=value)


def test_unknown_zone_and_field_states_are_preserved() -> None:
    assert publication(timezone=None).timezone is None
    assert TextField(state="empty", value="").value == ""
    for state, value in (("present", ""), ("absent", "hidden"), ("not_collected", "")):
        with pytest.raises(ValidationError):
            TextField.model_validate({"state": state, "value": value})
    with pytest.raises(ValidationError, match="earlier validity"):
        ContextClock(
            captured_at="2026-02-01T00:00:00Z",
            valid_from="2026-01-01T00:00:00Z",
            validity_basis="observed",
        )
