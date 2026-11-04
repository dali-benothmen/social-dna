import csv
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from socialdna.application.account_import_service import import_dataset
from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.ids import stable_id
from socialdna.ingestion.tabular import parse_import
from socialdna.storage.schema import metadata


def test_dry_run_is_read_only_and_import_is_idempotent(
    settings: Settings, account_export: Path
) -> None:
    result = import_dataset(settings, account_export, "json", dry_run=True)
    assert result["valid"] and not result["written"]
    assert not settings.data_dir.exists()
    imported = import_dataset(settings, account_export, "json")
    assert imported["written"] and len(imported["account_ids"]) == 1
    repeated = import_dataset(settings, account_export, "json")
    assert repeated["idempotent"] and not repeated["written"]
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["metric_observations"])
                )
                == 19
            )
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["import_batches"])
                )
                == 1
            )
            source = connection.execute(select(metadata.tables["source_records"])).mappings().one()
            assert source["permission_basis"] == "creator_owned_export"
            artifact = application.artifacts.get(connection, source["raw_artifact_id"])
            assert (
                application.artifacts.path_for(artifact["relative_path"]).read_bytes()
                == account_export.read_bytes()
            )
            assert connection.scalar(select(metadata.tables["accounts"].c.external_id)) == "0001"


def test_changes_and_reversions_append_history(settings: Settings, account_export: Path) -> None:
    import_dataset(settings, account_export, "json")
    payload = json.loads(account_export.read_text())
    metric = next(
        row
        for row in payload["records"]
        if row["record_type"] == "metric_snapshot" and row.get("metric_key") == "demo.views.v1"
    )
    for value in (999, 100):
        metric["value"] = value
        account_export.write_text(json.dumps(payload))
        assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            table = metadata.tables["metric_observations"]
            rows = list(
                connection.execute(
                    select(table)
                    .where(
                        table.c.metric_key == "demo.views.v1",
                        table.c.subject_id == stable_id("post", "demo", "p0"),
                    )
                    .order_by(table.c.imported_at)
                ).mappings()
            )
            # Byte-identical exports are idempotent, not new correction events.
            assert [row["value"] for row in rows] == [100, 999]
            assert rows[-1]["supersedes_id"] == rows[0]["id"]
        with pytest.raises(IntegrityError, match="append-only"):
            with application.database.transaction() as connection:
                connection.execute(table.update().values(value=0))


def test_corrected_export_is_new_event_when_source_content_changes(
    settings: Settings, account_export: Path
) -> None:
    import_dataset(settings, account_export, "json")
    payload = json.loads(account_export.read_text())
    record = next(r for r in payload["records"] if r.get("metric_key") == "demo.views.v1")
    record["value"] = 999
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    record["value"] = 100
    payload["source"]["terms"] = {"export_revision": 3}
    account_export.write_text(json.dumps(payload))
    import_dataset(settings, account_export, "json")
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            table = metadata.tables["metric_observations"]
            values = list(
                connection.scalars(
                    select(table.c.value)
                    .where(
                        table.c.subject_id == stable_id("post", "demo", "p0"),
                        table.c.metric_key == "demo.views.v1",
                    )
                    .order_by(table.c.imported_at)
                )
            )
            assert values == [100, 999, 100]


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_account",
        "naive_time",
        "changed_definition",
        "unknown_metric",
        "invalid_window",
        "comment_permission",
        "conflicting_duplicate",
    ],
)
def test_invalid_import_is_atomic(settings: Settings, account_export: Path, mutation: str) -> None:
    import_dataset(settings, account_export, "json")
    payload = json.loads(account_export.read_text())
    records = payload["records"]
    post = next(row for row in records if row["record_type"] == "post")
    metric = next(row for row in records if row.get("metric_key") == "demo.views.v1")
    if mutation == "unknown_account":
        post["account_external_id"] = "unknown"
    elif mutation == "naive_time":
        post["published_at"] = "2026-01-01T10:00:00"
    elif mutation == "changed_definition":
        next(row for row in records if row["record_type"] == "metric_definition")["definition"] = (
            "Changed meaning"
        )
    elif mutation == "unknown_metric":
        metric["metric_key"] = "demo.unknown.v1"
    elif mutation == "invalid_window":
        metric["window_start"] = "2026-01-20T00:00:00Z"
    elif mutation == "comment_permission":
        records.append(
            {
                "record_type": "comment",
                "platform": "demo",
                "post_external_id": "p0",
                "external_id": "c1",
                "body": "Private",
                "published_at": "2026-01-02T00:00:00Z",
            }
        )
    else:
        records.append({**metric, "value": 99})
    account_export.write_text(json.dumps(payload))
    result = import_dataset(settings, account_export, "json")
    assert not result["valid"] and result["errors"] and not result["written"]
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(metadata.tables["import_batches"])
                )
                == 1
            )


def test_csv_preserves_ids_and_has_physical_row_errors(
    settings: Settings, account_export: Path, tmp_path: Path
) -> None:
    payload = json.loads(account_export.read_text())
    records = payload["records"]
    fields = sorted({key for record in records for key in record})
    meta = {
        "_schema_version": "1.0",
        **{"_" + key: value for key, value in payload["source"].items()},
    }
    destination = tmp_path / "account.csv"
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*meta, *fields])
        writer.writeheader()
        writer.writerows({**meta, **record} for record in records)
    parsed = parse_import(destination, "csv")
    assert not parsed.errors
    assert parsed.records[0].external_id == "0001"
    assert import_dataset(settings, destination, "csv")["valid"]
    with destination.open("a") as stream:
        stream.write("broken,row\n")
    errors = import_dataset(settings, destination, "csv", dry_run=True)["errors"]
    assert errors[-1]["row"] > 1


def test_comments_parent_order_and_normalized_tags(
    settings: Settings, account_export: Path
) -> None:
    payload = json.loads(account_export.read_text())
    payload["source"]["comments_permitted"] = True
    base = {
        "record_type": "comment",
        "platform": "demo",
        "post_external_id": "p0",
        "body": "Permitted minimized text",
        "published_at": "2026-01-02T00:00:00Z",
    }
    payload["records"].extend(
        [
            {**base, "external_id": "child", "parent_external_id": "parent"},
            {**base, "external_id": "parent"},
            {
                "record_type": "tag",
                "platform": "demo",
                "post_external_id": "p0",
                "value": "#Learning",
            },
        ]
    )
    account_export.write_text(json.dumps(payload))
    assert import_dataset(settings, account_export, "json")["valid"]
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            comments = list(connection.execute(select(metadata.tables["comments"])).mappings())
            assert len(comments) == 2
            assert (
                next(row for row in comments if row["external_id"] == "child")["parent_comment_id"]
                is not None
            )
