import json
import os
import subprocess
import sys
from pathlib import Path


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
        timeout=60,
        env=os.environ.copy(),
    )
    assert completed.returncode == expected, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_cross_process_account_import_analytics_comparison_report(
    account_export: Path, tmp_path: Path
) -> None:
    data_dir = tmp_path / "separate-process-data"
    assert command(data_dir, "import", "json", str(account_export), "--dry-run")["data"]["valid"]
    assert not data_dir.exists()
    imported = command(data_dir, "import", "json", str(account_export))["data"]
    account_id = imported["account_ids"][0]
    assert command(data_dir, "import", "json", str(account_export))["data"]["idempotent"]
    analyzed = command(data_dir, "analyze", "account", account_id, "--metric", "demo.views.v1")
    assert analyzed["data"]["results"]["available_n"] == 6
    assert analyzed["run_id"]
    report = command(data_dir, "report", "generate", "--account", account_id)
    assert report["data"]["content"]["run_id"] == analyzed["run_id"]
    assert Path(report["data"]["path"]).is_file()
    compared = command(
        data_dir,
        "compare",
        "posts",
        "--left",
        imported["post_ids"][0],
        "--right",
        imported["post_ids"][1],
        "--metric",
        "demo.views.v1",
        "--unmatched",
    )
    assert compared["data"]["results"]["comparison"]["left"]["n"] == 1
    assert (
        command(data_dir, "compare", "reproduce", compared["run_id"])["data"]["results"]
        == compared["data"]["results"]
    )
    reproduced = command(
        data_dir, "analyze", "account", account_id, "--reproduce-run", analyzed["run_id"]
    )
    assert reproduced["data"]["results"] == analyzed["data"]["results"]
    assert command(data_dir, "storage", "verify")["status"] == "success"


def test_invalid_dataset_returns_row_errors_and_does_not_initialize(
    account_export: Path, tmp_path: Path
) -> None:
    payload = json.loads(account_export.read_text())
    payload["records"].append({"record_type": "unknown"})
    account_export.write_text(json.dumps(payload))
    data_dir = tmp_path / "no-writes"
    result = command(data_dir, "import", "json", str(account_export), expected=2)
    assert result["status"] == "error"
    assert result["data"]["errors"][-1]["row"] == len(payload["records"])
    assert not data_dir.exists()


def test_report_requires_exactly_one_target(tmp_path: Path) -> None:
    result = command(
        tmp_path / "data", "report", "generate", "--run", "r", "--account", "a", expected=2
    )
    assert result["status"] == "error"


def test_bundled_import_examples_validate_without_storage(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    for suffix in ("csv", "json"):
        data_dir = tmp_path / suffix
        assert command(
            data_dir,
            "import",
            suffix,
            str(root / "examples/imports" / f"account.{suffix}"),
            "--dry-run",
        )["data"]["valid"]
        assert not data_dir.exists()
