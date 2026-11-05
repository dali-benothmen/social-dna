"""R1 installed-process contract: real imported text/count and decoded media."""

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.analysis_service import analyze_video
from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.hashing import hash_file
from socialdna.domain.media import AnalysisOptions
from socialdna.storage.schema import metadata


def command(data_dir: Path, *args: str, expected: int = 0) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(data_dir),
            "--offline",
            "--format",
            "json",
            *args,
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=90,
    )
    assert completed.returncode == expected, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_frame_comment_metric_registration_restart_report_and_withdrawal(
    settings: Settings,
    account_export: Path,
    video: Path,
    tmp_path: Path,
) -> None:
    export = json.loads(account_export.read_text())
    export["source"]["comments_permitted"] = True
    export["records"].append(
        {
            "record_type": "comment",
            "platform": "demo",
            "post_external_id": "p0",
            "external_id": "c",
            "body": "I will cook this!",
            "published_at": "2026-01-02T00:00:00Z",
        }
    )
    account_export.write_text(json.dumps(export))
    imported = import_dataset(settings, account_export, "json")
    assert imported["valid"]
    with open_application(settings) as application:
        analyzed = analyze_video(
            application, str(video), options=AnalysisOptions(depth="quick", no_ai=True)
        )
        with application.database.transaction() as connection:
            evidence = metadata.tables["evidence_items"]
            frame_id = connection.scalar(
                select(evidence.c.id).where(evidence.c.subject_type == "frame").limit(1)
            )
            comment_id = connection.scalar(select(metadata.tables["comments"].c.id))
            metrics = metadata.tables["metric_observations"]
            snapshot_id = connection.scalar(
                select(metrics.c.id).where(metrics.c.metric_key == "demo.views.v1").limit(1)
            )
            # Ordinary media/account analysis must not create research registrations.
            revisions = metadata.tables["entity_revisions"]
            assert not connection.scalar(
                select(revisions.c.id).where(revisions.c.kind == "research_question")
            )
    data_dir = settings.data_dir
    frame = command(data_dir, "evidence", "resolve", frame_id, "--run", analyzed["run_id"])["data"]
    comment = command(
        data_dir, "evidence", "cite-comment", comment_id, "--start", "0", "--end", "17"
    )["data"]
    metric = command(data_dir, "evidence", "cite-metric", snapshot_id)["data"]
    assert frame["eligible"] and comment["eligible"] and metric["eligible"]
    assert comment["locator"]["quote"] == "I will cook this!"
    spec = tmp_path / "research.json"
    spec.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "key": "cooking-fixture",
                "question": "Why might a meal preview be associated with performance?",
                "population": "Permission-labelled software fixtures, not empirical evidence",
                "evidence": [item["ref"] for item in (frame, comment, metric)],
                "hypotheses": [
                    {
                        "key": "anticipation",
                        "statement": "A preview might create anticipation.",
                        "population": "Fixture posts",
                        "data_needs": ["Reviewed construct measures"],
                    }
                ],
            }
        )
    )
    registered = command(data_dir, "research", "register", "--spec", str(spec))["data"]
    question_id = registered["question"]["id"]
    shown = command(data_dir, "research", "show", question_id)["data"]
    assert len(shown["citations"]) == 3 and not shown["evaluation_ready"]
    report = command(data_dir, "research", "report", question_id)["data"]
    archived_path = Path(report["artifact"]["path"])
    archived_hash = hash_file(archived_path)
    assert len(report["content"]["citations"]) == 3
    for citation in report["content"]["citations"]:
        result = command(
            data_dir,
            "evidence",
            "resolve",
            citation["ref"]["id"],
            "--revision",
            citation["ref"]["revision_id"],
        )["data"]
        assert result["eligible"]
    command(data_dir, "evidence", "resolve", frame_id, "--media", "wrong-media", expected=2)
    command(
        data_dir,
        "evidence",
        "withdraw",
        "--source",
        imported["source_id"],
        "--reason",
        "Do not reuse this export",
    )
    current = command(data_dir, "research", "show", report["ref"]["id"], expected=5)["data"]
    assert current["content"]["status"] == "partial"
    assert sum(item["eligible"] for item in current["content"]["citations"]) == 1
    assert hash_file(archived_path) == archived_hash
    command(data_dir, "research", "register", "--spec", str(spec), expected=2)
    assert command(data_dir, "storage", "verify")["status"] == "success"


def test_research_dry_run_and_invalid_spec_do_not_initialize(tmp_path: Path) -> None:
    data_dir = tmp_path / "no-writes"
    spec = tmp_path / "draft.json"
    spec.write_text(json.dumps({"key": "draft", "question": "Question?", "population": "Posts"}))
    assert not command(data_dir, "research", "register", "--spec", str(spec), "--dry-run")["data"][
        "written"
    ]
    assert not data_dir.exists()
    spec.write_text('{"key":"x","question":"Q","population":"P","evaluation":"proven"}')
    assert (
        command(data_dir, "research", "register", "--spec", str(spec), expected=2)["status"]
        == "error"
    )
    assert not data_dir.exists()
