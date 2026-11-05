import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialdna.core.exceptions import ConfigurationError
from socialdna.core.hashing import hash_file
from socialdna.domain.evidence import CommentLocator, EntityRef
from socialdna.reporting.research import render_research
from socialdna.storage.readonly import immutable_snapshot


def test_research_markdown_escapes_source_text_and_draft_statements() -> None:
    unsafe = "<script>alert(1)</script> [click](https://example.invalid) ![image](x) `code`"
    report = {
        "question": {"specification": {"question": unsafe, "population": unsafe}},
        "hypotheses": [{"specification": {"statement": unsafe}}],
        "citations": [
            {
                "ref": {"id": "citation", "revision_id": "revision"},
                "source": {"id": "source"},
                "locator": {
                    "kind": "comment_span",
                    "quote": unsafe,
                    "start_char": 0,
                    "end_char": len(unsafe),
                },
            }
        ],
        "limitations": [unsafe],
    }
    rendered = render_research(report)
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
    assert "[click](" not in rendered and "![image](" not in rendered
    assert "`code`" not in rendered
    assert "unevaluated" in rendered


def test_comment_locator_requires_exact_code_point_span_and_known_convention() -> None:
    ref = EntityRef(kind="comment", id="c", revision_id="r")
    post = EntityRef(kind="post", id="p", revision_id="q")
    assert (
        CommentLocator(subject=ref, post=post, start_char=0, end_char=1, quote="🍲").quote == "🍲"
    )
    with pytest.raises(ValidationError):
        CommentLocator(subject=ref, post=post, start_char=0, end_char=2, quote="🍲")
    with pytest.raises(ValidationError):
        CommentLocator.model_validate(
            {
                "subject": ref,
                "post": post,
                "start_char": 0,
                "end_char": 1,
                "quote": "x",
                "index_convention": "utf16",
            }
        )


def test_no_write_reader_rejects_uncheckpointed_wal_without_side_effects(tmp_path: Path) -> None:
    path = tmp_path / "active.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE owned (value INTEGER)")
        connection.execute("INSERT INTO owned VALUES (1)")
        connection.commit()
        before = {item.name: hash_file(item) for item in tmp_path.iterdir()}
        with pytest.raises(ConfigurationError, match="checkpointed"):
            with immutable_snapshot(path):
                pass
        assert {item.name: hash_file(item) for item in tmp_path.iterdir()} == before
    finally:
        connection.close()
