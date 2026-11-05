from pathlib import Path

import pytest
from pydantic import ValidationError

from socialdna.audience.annotations import AnnotationSet, ReactionAnnotation, literal_candidates
from socialdna.audience.collections import CollectionSpec
from socialdna.audience.linking import ContentLink, parse_reference_time

REF = {"kind": "comment", "id": "comment", "revision_id": "revision"}


@pytest.mark.parametrize(
    "text,expected", [("0:02", 2000), ("01:02:03.25", 3723250), ("0:00,001", 1)]
)
def test_explicit_playback_parser(text: str, expected: int) -> None:
    assert parse_reference_time(text) == expected


@pytest.mark.parametrize("text", ["2026-01-07T00:00:00Z", "2 seconds", "0:60", "01:60:00", "-0:02"])
def test_comment_publication_is_not_playback(text: str) -> None:
    with pytest.raises(ValueError):
        parse_reference_time(text)


@pytest.mark.parametrize(
    "text,language,label",
    [
        ("I need to make this tonight", "en", "expressed_intention"),
        ("I already made this", "en", "other"),
        ("¿Cómo hacerlo?", "es", "ambiguous"),
        ("I need to make this", None, "ambiguous"),
        ("How much salt?", "en", "question"),
    ],
)
def test_literal_candidates_are_not_behavior_or_multilingual_inference(
    text: str, language: str | None, label: str
) -> None:
    labels, negated = literal_candidates(text, language)
    assert label in labels
    if language != "en":
        assert negated is None
    assert not set(labels).intersection({"conversion", "verified_preparation"})


def test_unicode_spans_and_review_coverage_are_strict() -> None:
    base = {
        "key": "review",
        "comment": REF,
        "start_char": 0,
        "end_char": 2,
        "quote": "🍳!",
        "labels": ["expressed_intention"],
        "rationale": "literal review",
    }
    assert ReactionAnnotation.model_validate(base).quote == "🍳!"
    with pytest.raises(ValidationError, match="Unicode"):
        ReactionAnnotation.model_validate({**base, "end_char": 3})
    with pytest.raises(ValidationError, match="human-reviewed"):
        ReactionAnnotation.model_validate({**base, "complete_rubric_review": True})
    with pytest.raises(ValidationError):
        ReactionAnnotation.model_validate({**base, "labels": ["verified_conversion"]})


def test_inferred_links_do_not_acquire_explicit_timestamps() -> None:
    with pytest.raises(ValidationError, match="fabricated explicit"):
        ContentLink.model_validate(
            {
                "key": "link",
                "reaction_key": "a",
                "target": {**REF, "kind": "post"},
                "origin": "human_interpretation",
                "reference_kind": "timestamp",
                "reference_text": "0:02",
                "description": "Interpreted opening link",
            }
        )


def test_ranked_partial_data_cannot_claim_complete_census() -> None:
    base = {
        "key": "ranked",
        "permission_basis": "owned",
        "source_uri": "urn:test",
        "posts": [{**REF, "kind": "post"}],
        "collected_at": "2026-01-07T00:00:00Z",
        "ordering": "ranked",
        "sampling_method": "ranked",
        "completeness": "partial",
        "declared_frame": "Top comments",
        "supplied_count": 0,
        "deleted_moderated_coverage": "unknown",
    }
    assert CollectionSpec.model_validate(base).known_total is None
    with pytest.raises(ValidationError, match="census"):
        CollectionSpec.model_validate(
            {
                **base,
                "completeness": "complete_for_declared_frame",
                "pagination_complete": True,
                "truncated": False,
            }
        )


def test_audience_templates_match_the_actual_versioned_schemas() -> None:
    examples = Path(__file__).resolve().parents[2] / "examples" / "audience"
    CollectionSpec.model_validate_json((examples / "collection.json").read_text())
    spec = AnnotationSet.model_validate_json((examples / "annotations.json").read_text())
    assert spec.annotations[0].state == "proposed"  # Templates assert no actual human review.
