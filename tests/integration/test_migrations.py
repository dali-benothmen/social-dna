import shutil
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect

from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import hash_file
from socialdna.core.time import utc_now
from socialdna.storage.database import Database
from socialdna.storage.migration_runner import (
    MIGRATIONS,
    current_revision,
    migrate,
    migration_config,
)


def test_migration_downgrade_upgrade(tmp_path: Path) -> None:
    database = Database(tmp_path / "migration.db")
    try:
        migrate(database)
        with database.transaction() as connection:
            assert current_revision(connection) == "0004_analytics"
            config = migration_config()
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
            assert current_revision(connection) is None
            assert inspect(connection).get_table_names() == ["alembic_version"]
        migrate(database)
        with database.transaction() as connection:
            assert current_revision(connection) == "0004_analytics"
    finally:
        database.close()


def test_upgrade_released_foundation_preserves_existing_data(tmp_path: Path) -> None:
    database = Database(tmp_path / "upgrade.db")
    try:
        with database.transaction() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "0001_foundation")
            connection.exec_driver_sql(
                "INSERT INTO migration_checksums VALUES (?, ?, ?)",
                (
                    "0001_foundation",
                    hash_file(MIGRATIONS / "versions/v0001_foundation.py"),
                    utc_now(),
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO creators (id, display_name) VALUES ('existing', 'Keep me')"
            )
        migrate(database)
        with database.transaction() as connection:
            assert current_revision(connection) == "0004_analytics"
            assert (
                connection.exec_driver_sql(
                    "SELECT display_name FROM creators WHERE id='existing'"
                ).scalar()
                == "Keep me"
            )
            assert "observations" in inspect(connection).get_table_names()
        migrate(database)
    finally:
        database.close()


def test_failed_ddl_migration_rolls_back(tmp_path: Path) -> None:
    location = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, location)
    (location / "versions" / "v0005_failure.py").write_text(
        'from alembic import op\nrevision="0005_failure"\ndown_revision="0004_analytics"\n'
        'def upgrade():\n    op.execute("CREATE TABLE must_rollback (id INTEGER)")\n'
        '    raise RuntimeError("injected migration failure")\n'
        "def downgrade():\n    pass\n"
    )
    database = Database(tmp_path / "rollback.db")
    try:
        with pytest.raises(RuntimeError, match="injected"):
            migrate(database, location=location)
        with database.transaction() as connection:
            assert inspect(connection).get_table_names() == []
        migrate(database)
    finally:
        database.close()


def test_modified_applied_migration_detected(tmp_path: Path) -> None:
    location = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, location)
    database = Database(tmp_path / "dirty.db")
    try:
        migrate(database, location=location)
        path = location / "versions" / "v0001_foundation.py"
        path.write_text(path.read_text() + "\n# unauthorized change\n")
        with pytest.raises(StorageIntegrityError, match="modified"):
            migrate(database, location=location)
    finally:
        database.close()


def test_unknown_head_and_unversioned_data_preserved(settings: Settings) -> None:
    with open_application(settings) as application:
        with application.database.transaction() as connection:
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='future_version'")
    with pytest.raises(StorageIntegrityError, match="unknown migration"):
        with open_application(settings):
            pass
    database = Database(settings.data_dir / "foreign.db")
    try:
        with database.transaction() as connection:
            connection.exec_driver_sql("CREATE TABLE valuable (id INTEGER)")
            connection.exec_driver_sql("INSERT INTO valuable VALUES (42)")
        with pytest.raises(StorageIntegrityError, match="unversioned"):
            migrate(database)
        with database.transaction() as connection:
            assert connection.exec_driver_sql("SELECT id FROM valuable").scalar() == 42
    finally:
        database.close()
