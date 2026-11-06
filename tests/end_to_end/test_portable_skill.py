"""Real subprocess workflows in host layouts, not simulated live agent conversations."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from socialdna.domain.results import ResultEnvelope


def invoke(data: Path, *args: str, expected: int = 0) -> ResultEnvelope:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(data),
            "--offline",
            "--no-ai",
            "--format",
            "json",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "PATH": "", "PYTHONUTF8": "1"},
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return ResultEnvelope.model_validate_json(result.stdout)


@pytest.mark.parametrize("host", [".agents", ".claude", ".opencode"])
def test_same_offline_engine_and_partial_reports_in_three_host_layouts(
    tmp_path: Path, account_export: Path, host: str
) -> None:
    parent = tmp_path / "project with spaces" / host / "skills"
    parent.mkdir(parents=True)
    data = tmp_path / "library"
    destination = parent / "socialdna"
    exported = invoke(data, "skill", "export", str(destination)).data
    assert "SKILL.md" in exported["files"] and not data.exists()
    assert not exported["host_configuration_changed"]
    original = (destination / "SKILL.md").read_bytes()
    assert invoke(data, "skill", "export", str(destination), expected=2).errors
    assert (destination / "SKILL.md").read_bytes() == original and not data.exists()
    manifest = invoke(data, "capabilities").data
    features = {entry["id"]: entry for entry in manifest["capabilities"]}
    assert features["static_media"]["status"] == "available"
    assert features["local_video"]["status"] == features["ocr"]["status"] == "unavailable"
    assert features["semantic_memory"]["prerequisites"] and not data.exists()

    photo = tmp_path / "photo with spaces.png"
    Image.new("RGB", (120, 90), "orange").save(photo)
    document = json.loads(account_export.read_text())
    posts = [row for row in document["records"] if row["record_type"] == "post"]
    for index, post in enumerate(posts):
        post["content_type"] = "carousel"
        post["caption"] = "<script>alert('x')</script> طبخ recipe" + "x" * index
        for position, path in enumerate((photo, tmp_path / "missing.png")):
            document["records"].append(
                {
                    "record_type": "media",
                    "platform": "demo",
                    "post_external_id": post["external_id"],
                    "position": position,
                    "uri": str(path),
                }
            )
    account_export.write_text(json.dumps(document), encoding="utf-8")
    assert invoke(data, "import", "json", str(account_export), "--dry-run").data["valid"]
    assert not data.exists()
    imported = invoke(data, "import", "json", str(account_export)).data
    target = imported["post_ids"][0]
    analyzed = invoke(data, "analyze", "carousel", target, "--max-items", "2", expected=5)
    assert analyzed.status == "partial" and analyzed.run_id
    saved = tmp_path / "usable partial.json"
    report = invoke(
        data, "report", "generate", "--run", analyzed.run_id, "--output", str(saved), expected=5
    )
    assert report.status == "partial" and report.data["content"]["report_type"] == "carousel"
    assert json.loads(saved.read_text(encoding="utf-8")) == report.data["content"]
    evidence = report.data["content"]["evidence"]
    assert invoke(data, "evidence", "resolve", evidence["id"], "--purpose", "new_claim").data[
        "eligible"
    ]
    caption = invoke(data, "creative", "cite-text", target).data
    assert caption["eligible"]

    markdown = tmp_path / "usable partial.md"
    md = subprocess.run(
        [
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            str(data),
            "--offline",
            "--format",
            "json",
            "report",
            "generate",
            "--run",
            analyzed.run_id,
            "--format",
            "markdown",
            "--output",
            str(markdown),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert md.returncode == 5 and markdown.read_text(encoding="utf-8") == md.stdout
    assert "<script>" not in md.stdout and "&lt;script&gt;" in md.stdout
    assert "## Supplied text" in md.stdout and "## Limits" in md.stdout
    assert invoke(
        data, "report", "generate", "--run", analyzed.run_id, "--output", str(saved), expected=2
    ).errors

    spec = tmp_path / "comparison.json"
    spec.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "metric_key": "demo.views.v1",
                "features": ["caption_length"],
                "covariates": ["caption_length"],
                "design": "descriptive",
                "estimand": "descriptive",
                "feature_policy": "retrospective_content",
                "maturity_policy": "collection_proxy",
                "knowledge_cutoff": datetime.now(UTC).isoformat(),
                "publication_cutoff": "2026-11-01T00:00:00Z",
                "sampling_frame": "Six synthetic authorized posts, not real creator evidence",
                "family_id": "portable-host-fixture",
                "family_terms": ["caption_length"],
            }
        )
    )
    account = invoke(data, "analyze", "account", imported["account_ids"][0], "--spec", str(spec))
    assert account.run_id and account.data["results"]["available_n"] == 6
    assert (
        invoke(data, "compare", "reproduce", account.run_id).data["results"]
        == account.data["results"]
    )
    assert (
        invoke(data, "report", "generate", "--run", account.run_id).data["content"][
            "schema_version"
        ]
        == "2.0"
    )


def test_skill_cross_creator_command_produces_qualified_cited_report(
    tmp_path: Path, account_export: Path
) -> None:
    document = json.loads(account_export.read_text())
    original = list(document["records"])
    document["records"].append(
        {
            "record_type": "account",
            "platform": "demo",
            "external_id": "other",
            "creator_key": "independent-other",
            "niche": "education",
        }
    )
    for record in original:
        kind = record["record_type"]
        if (
            kind not in ("post", "tag", "metric_snapshot")
            or record.get("subject_type") == "account"
        ):
            continue
        other = dict(record)
        if kind == "post":
            other["external_id"] = "other-" + other["external_id"]
            other["account_external_id"] = "other"
        elif kind == "tag":
            other["post_external_id"] = "other-" + other["post_external_id"]
        else:
            other["subject_external_id"] = "other-" + other["subject_external_id"]
        document["records"].append(other)
    account_export.write_text(json.dumps(document))
    data = tmp_path / "library"
    accounts = invoke(data, "import", "json", str(account_export)).data["account_ids"]
    spec = tmp_path / "cross-creator.json"
    spec.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "metric_key": "demo.views.v1",
                "features": ["caption_length"],
                "covariates": ["caption_length"],
                "design": "cross_creator",
                "estimand": "cross_creator_comparison",
                "feature_policy": "retrospective_content",
                "maturity_policy": "collection_proxy",
                "knowledge_cutoff": datetime.now(UTC).isoformat(),
                "publication_cutoff": "2026-11-01T00:00:00Z",
                "sampling_frame": "Two synthetic creators with six supplied posts each",
                "family_id": "portable-cross-creator",
                "family_terms": ["caption_length"],
            }
        )
    )
    compared = invoke(
        data,
        "compare",
        "accounts",
        "--left",
        accounts[0],
        "--right",
        accounts[1],
        "--spec",
        str(spec),
    )
    comparison = compared.data["results"]["comparison"]
    assert comparison["effective_creator_count"] == 2 and len(comparison["pairs"]) == 6
    assert comparison["matched_effect"]["estimate"] == 0
    assert comparison["matched_effect"]["ci_low"] is None
    assert compared.run_id
    report = invoke(data, "report", "generate", "--run", compared.run_id)
    assert report.data["content"]["statistical_evidence"]
