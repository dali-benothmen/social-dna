import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.application.performance_service import analyze_account, compare, reproduce
from socialdna.application.report_service import generate_report
from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id
from socialdna.domain.media import AnalysisOptions
from socialdna.domain.research import PerformanceSpec
from socialdna.storage.schema import metadata

ACCOUNT = stable_id("account", "demo", "0001")


def test_account_report_freezes_cohort_and_reproduces(
    settings: Settings, account_export: Path
) -> None:
    import_dataset(settings, account_export, "json")
    spec = PerformanceSpec(
        metric_key="demo.views.v1", features=("caption_length",), bootstrap_resamples=200
    )
    with open_application(settings) as application:
        analyzed = analyze_account(application, ACCOUNT, spec)
        assert analyzed["results"]["available_n"] == 6
        assert analyzed["results"]["outcome"]["median"] == 350
        run_id = analyzed["run_id"]
        assert all(row["snapshot_ids"] for row in analyzed["posts"])
        with application.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["cohort_members"])
                )
                == 6
            )
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["derived_metrics"])
                )
                == 6
            )
    payload = json.loads(account_export.read_text())
    for row in payload["records"]:
        if row.get("metric_key") == "demo.views.v1":
            row["value"] = 9000
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        report = generate_report(application, run_id)
        assert report["content"]["results"]["outcome"]["median"] == 350
        assert Path(report["path"]).is_file()
        reproduced = analyze_account(application, ACCOUNT, None, reproduce_run=run_id)
        assert reproduced["results"] == analyzed["results"]
        markdown = generate_report(application, run_id, "markdown")["content"]
        assert "socialdna:metric/" in markdown and "provenance" in markdown


def test_missing_shares_saves_do_not_enter_rate_denominator(
    settings: Settings, account_export: Path
) -> None:
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        likes = analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.likes.v1", denominator_key="demo.views.v1"),
        )
        assert likes["results"]["outcome"]["median"] == pytest.approx(0.1)
        missing = analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(
                metric_key="demo.likes.v1",
                numerator_keys=("demo.shares.v1", "demo.saves.v1"),
                denominator_key="demo.views.v1",
            ),
        )
        assert missing["results"]["available_n"] == 0
        assert missing["results"]["outcome"]["median"] is None
        assert all(
            row["metric_states"]["demo.shares.v1"] == "not_permitted" for row in missing["posts"]
        )


def test_ancient_snapshots_are_excluded(settings: Settings, account_export: Path) -> None:
    payload = json.loads(account_export.read_text())
    row = next(row for row in payload["records"] if row.get("metric_key") == "demo.views.v1")
    row["observed_at"] = "2028-01-01T00:00:00Z"
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        result = analyze_account(application, ACCOUNT, PerformanceSpec(metric_key="demo.views.v1"))
        assert result["results"]["available_n"] == 5
        assert result["results"]["missingness"]["no_age_aligned_snapshot"] == 1


def test_account_media_batch_links_real_features_and_survives_missing_files(
    settings: Settings, account_export: Path, video: Path
) -> None:
    percent_named_video = video.parent / "owned%20literal.mkv"
    shutil.copyfile(video, percent_named_video)
    payload = json.loads(account_export.read_text())
    payload["records"].extend(
        [
            {"record_type": "media", "platform": "demo", "post_external_id": post, "uri": uri}
            for post, uri in (
                ("p0", percent_named_video.as_uri()),
                ("p1", "missing.mp4"),
                ("p2", "https://example.invalid/not-fetched.mp4"),
            )
        ]
    )
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        result = analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1", features=("visual.motion",)),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        assert result["status"] == "partial"
        assert len(result["batch"]) == 6
        successful = next(
            row for row in result["posts"] if row["post_id"] == stable_id("post", "demo", "p0")
        )
        assert successful["features"]["duration_seconds"] == 3
        assert successful["features"]["visual.motion"] is not None
        assert successful["feature_evidence_ids"]
        assert len([row for row in result["batch"] if row["status"] == "failed"]) == 2
        assert "Remote media is reference-only" in str(result["batch"])
        reproduced = analyze_account(application, ACCOUNT, None, reproduce_run=result["run_id"])
        assert reproduced["status"] == "partial"
        assert reproduced["results"] == result["results"]


def test_matched_comparisons_and_no_silent_cross_platform_metrics(
    settings: Settings, account_export: Path, video: Path
) -> None:
    payload = json.loads(account_export.read_text())
    payload["records"].extend(
        {
            "record_type": "media",
            "platform": "demo",
            "post_external_id": f"p{i}",
            "uri": video.as_uri(),
        }
        for i in range(6)
    )
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        result = compare(
            application,
            "posts",
            [stable_id("post", "demo", f"p{i}") for i in range(3)],
            [stable_id("post", "demo", f"p{i}") for i in range(3, 6)],
            PerformanceSpec(metric_key="demo.views.v1"),
        )
        assert len(result["results"]["comparison"]["pairs"]) == 3
        assert result["results"]["comparison"]["matched_effect"]["median"] == -300
        assert reproduce(application, result["run_id"])["results"] == result["results"]


def test_period_outcome_uses_window_end_not_delayed_collection(
    settings: Settings, account_export: Path
) -> None:
    payload = json.loads(account_export.read_text())
    payload["records"].extend(
        [
            {
                "record_type": "metric_definition",
                "platform": "demo",
                "key": "demo.daily_views.v1",
                "definition": "Views in exact period",
                "measurement": "period",
            },
            {
                "record_type": "metric_snapshot",
                "platform": "demo",
                "subject_external_id": "p0",
                "metric_key": "demo.daily_views.v1",
                "observed_at": "2026-02-01T00:00:00Z",
                "window_start": "2026-01-07T00:00:00Z",
                "window_end": "2026-01-08T00:00:00Z",
                "value": 35,
            },
        ]
    )
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as application:
        with pytest.raises(ConfigurationError, match="window_seconds"):
            analyze_account(application, ACCOUNT, PerformanceSpec(metric_key="demo.daily_views.v1"))
        result = analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.daily_views.v1", window_seconds=86400),
        )
        assert result["results"]["available_n"] == 1
        assert result["results"]["observation_age_seconds"]["median"] == 7 * 86400


def test_changed_media_reference_invalidates_current_link(
    settings: Settings, account_export: Path, video: Path
) -> None:
    payload = json.loads(account_export.read_text())
    reference = {
        "record_type": "media",
        "platform": "demo",
        "post_external_id": "p0",
        "uri": video.as_uri(),
    }
    payload["records"].append(reference)
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        first = analyze_account(
            application,
            ACCOUNT,
            PerformanceSpec(metric_key="demo.views.v1"),
            analyze_media=True,
            media_options=AnalysisOptions(depth="quick", no_ai=True),
        )
        old = next(
            row for row in first["posts"] if row["post_id"] == stable_id("post", "demo", "p0")
        )
        assert old["features"]["duration_seconds"] == 3
    reference["uri"] = "changed-but-unavailable.mp4"
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        current = analyze_account(application, ACCOUNT, PerformanceSpec(metric_key="demo.views.v1"))
        changed = next(row for row in current["posts"] if row["post_id"] == old["post_id"])
        assert changed["features"]["duration_seconds"] is None
        assert generate_report(application, first["run_id"])["content"]["posts"] == first["posts"]
