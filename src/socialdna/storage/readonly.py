"""No-write dry-run reads of a quiescent SQLite checkpoint.

SQLite mode=ro can create WAL/SHM files. Immutable reads avoid those writes but
ignore WAL, so reject uncheckpointed data and concurrent file changes explicitly.
Real writes always revalidate under the application lock.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from socialdna.core.exceptions import ConfigurationError


def _state(path: Path) -> tuple[tuple[int, int] | None, ...]:
    result: list[tuple[int, int] | None] = []
    for item in (path, Path(str(path) + "-wal")):
        try:
            info = item.stat()
            result.append((info.st_size, info.st_mtime_ns))
        except FileNotFoundError:
            result.append(None)
    return tuple(result)


@contextmanager
def immutable_snapshot(path: Path) -> Iterator[sqlite3.Connection]:
    before = _state(path)
    if before[1] is not None and before[1][0] > 0:
        raise ConfigurationError("Dry-run validation requires a quiescent, checkpointed library")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        if _state(path) != before:
            raise ConfigurationError(
                "Library changed during dry-run validation; retry after writes finish"
            )
    finally:
        connection.close()
