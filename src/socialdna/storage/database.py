import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, Connection
from sqlalchemy.pool import NullPool


class Database:
    def __init__(self, path: Path, *, busy_timeout_ms: int = 5000) -> None:
        self.path = path
        self.engine: Engine = create_engine(
            URL.create("sqlite", database=str(path)),
            poolclass=NullPool,
        )

        @event.listens_for(self.engine, "connect")
        def configure_connection(dbapi_connection: sqlite3.Connection, _: Any) -> None:
            # Disable sqlite3's legacy implicit transaction handling. Our begin event
            # covers SELECT, DDL and SAVEPOINT as well as DML on Python 3.11+.
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=FULL")
                cursor.execute("PRAGMA wal_autocheckpoint=1000")
            finally:
                cursor.close()

        @event.listens_for(self.engine, "begin")
        def begin_transaction(connection: Connection) -> None:
            connection.exec_driver_sql("BEGIN")

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            yield connection

    @contextmanager
    def migration_transaction(self) -> Iterator[Connection]:
        """Atomic SQLite table rebuild with FK validation before commit.

        SQLite requires foreign_keys=OFF outside the transaction for a parent
        table rebuild. This dedicated, unpooled connection is never lent to an
        application writer while enforcement is disabled.
        """
        from socialdna.core.exceptions import StorageIntegrityError

        with self.engine.connect() as connection:
            driver = connection.connection.driver_connection
            assert driver is not None
            driver.execute("PRAGMA foreign_keys=OFF")
            try:
                with connection.begin():
                    yield connection
                    if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                        raise StorageIntegrityError("Migration foreign-key check failed")
            finally:
                driver.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.engine.dispose()
