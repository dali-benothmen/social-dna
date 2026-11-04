from collections.abc import Iterator
from contextlib import contextmanager

from socialdna.storage.database import Database
from socialdna.storage.repositories import Repository


@contextmanager
def unit_of_work(database: Database) -> Iterator[Repository]:
    """Commit on success, roll back all canonical writes on an exception."""
    with database.transaction() as connection:
        yield Repository(connection)
