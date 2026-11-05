import socket

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from socialdna.application.bootstrap import initialize, open_application
from socialdna.config.settings import Settings
from socialdna.core.enums import AvailabilityStatus
from socialdna.storage.health import doctor, storage_status, storage_verify
from socialdna.storage.repositories import Repository
from socialdna.storage.schema import metadata
from socialdna.storage.unit_of_work import unit_of_work


def test_first_use_repeated_init_preserves_data(settings: Settings) -> None:
    with open_application(settings) as application:
        with unit_of_work(application.database) as repository:
            account_id = repository.upsert_account("local", "sentinel", handle="sample")
        assert application.vectors.client.get_collections().collections == []
    initialize(settings)
    with open_application(settings) as application:
        with unit_of_work(application.database) as repository:
            assert repository.account(account_id)["handle"] == "sample"
            assert repository.upsert_account("local", "sentinel", handle="changed") == account_id
        with application.database.transaction() as connection:
            assert connection.scalar(select(metadata.tables["accounts"].c.id)) == account_id
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
            assert "graph_nodes" in inspect(connection).get_table_names()
            assert "vector_documents" in inspect(connection).get_table_names()
    for folder in ("vectors", "cache", "artifacts/objects", "models", "reports", "logs"):
        assert (settings.data_dir / folder).is_dir()
    assert (settings.data_dir / "vectors" / "meta.json").is_file()


def test_transaction_rollback_and_foreign_keys(settings: Settings) -> None:
    with open_application(settings) as application:
        with pytest.raises(RuntimeError), unit_of_work(application.database) as repository:
            repository.upsert_account("local", "rollback")
            raise RuntimeError("abort")
        with application.database.transaction() as connection:
            assert list(connection.scalars(select(metadata.tables["accounts"].c.id))) == []
        with pytest.raises(IntegrityError), application.database.transaction() as connection:
            connection.execute(
                metadata.tables["posts"]
                .insert()
                .values(
                    id="bad",
                    account_id="missing",
                    platform="local",
                    content_type="video",
                )
            )
        with pytest.raises(IntegrityError), application.database.transaction() as connection:
            Repository(connection).upsert_account("local", "json")
            connection.exec_driver_sql("UPDATE accounts SET profile_json='invalid'")


def test_unknown_metrics_are_explicit(settings: Settings) -> None:
    with open_application(settings) as application:
        with unit_of_work(application.database) as repository:
            account_id = repository.upsert_account("local", "creator")
            repository.set_unavailable(
                subject_type="account",
                subject_id=account_id,
                field_key="followers",
                status=AvailabilityStatus.NOT_SUPPLIED,
                reason="Not included in supplied export.",
            )
        with application.database.transaction() as connection:
            row = connection.execute(select(metadata.tables["data_availability"])).mappings().one()
            assert row["status"] == "not_supplied"
            assert "value" not in row


def test_partial_account_update_preserves_unsupplied_fields(settings: Settings) -> None:
    with open_application(settings) as application:
        with unit_of_work(application.database) as repository:
            account_id = repository.upsert_account(
                "local", "owner", handle="original", profile={"niche": "cooking"}
            )
            repository.upsert_account("local", "owner", handle="renamed")
            repository.upsert_account("local", "owner")
            account = repository.account(account_id)
            assert account["handle"] == "renamed"
            assert account["profile_json"] == '{"niche":"cooking"}'


def test_no_network_or_models_and_health(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    initialize(settings)
    status = storage_status(settings)
    assert status["graph"]["status"] == "available"
    assert status["vectors"]["collections"] == []
    assert not list((settings.data_dir / "models").iterdir())
    assert all(check.status != "error" for check in storage_verify(settings))
    monkeypatch.setattr("socialdna.storage.health.shutil.which", lambda name: None)
    checks = {check.name: check for check in doctor(settings)}
    assert checks["ffmpeg"].status == "warning"
    assert checks["sqlite.fts5"].status == "ok"
