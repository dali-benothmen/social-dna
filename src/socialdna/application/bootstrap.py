import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from socialdna.config.paths import DataPaths
from socialdna.config.settings import Settings
from socialdna.core.exceptions import (
    SocialDNAError,
    StorageIntegrityError,
    StoragePermissionError,
)
from socialdna.storage.artifacts import ArtifactStore
from socialdna.storage.backup import assert_recovery_ready, prepare_upgrade, reconcile_restore
from socialdna.storage.database import Database
from socialdna.storage.filesystem import FilesystemInfo, detect_filesystem
from socialdna.storage.locking import DataDirectoryLock
from socialdna.storage.migration_runner import migrate
from socialdna.storage.vectors import LocalVectorStore


@dataclass
class Application:
    settings: Settings
    paths: DataPaths
    database: Database
    vectors: LocalVectorStore
    artifacts: ArtifactStore
    filesystem: FilesystemInfo


@contextmanager
def open_application(settings: Settings) -> Iterator[Application]:
    """Initialize idempotently under the data lock and close every resource on exit."""
    paths = DataPaths(settings.data_dir)
    filesystem = detect_filesystem(paths.root)
    if filesystem.network:
        raise StorageIntegrityError(
            f"Unsupported network filesystem ({filesystem.kind}) for {paths.root}.",
            next_action="Choose a local --data-dir; SQLite WAL needs same-host access.",
        )
    try:
        paths.root.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            stack.enter_context(DataDirectoryLock(paths.lock, timeout=settings.lock_timeout))
            assert_recovery_ready(paths, allow_pending=True)
            paths.create()
            database = Database(paths.database, busy_timeout_ms=settings.busy_timeout_ms)
            stack.callback(database.close)
            prepare_upgrade(paths, database)
            migrate(database)
            reconcile_restore(paths, database)
            from socialdna.storage.evidence_repository import backfill_evidence

            backfill_evidence(database)
            vectors = stack.enter_context(LocalVectorStore(paths.vectors))
            yield Application(settings, paths, database, vectors, ArtifactStore(paths), filesystem)
    except SocialDNAError:
        raise
    except PermissionError as exc:
        raise StoragePermissionError(
            f"Cannot access data directory {paths.root}: {exc}",
            next_action="Use a writable --data-dir owned by your user.",
        ) from exc
    except (SQLAlchemyError, sqlite3.DatabaseError) as exc:
        raise StorageIntegrityError(f"Storage operation failed: {exc}") from exc
    except OSError as exc:
        raise StorageIntegrityError(f"Storage filesystem operation failed: {exc}") from exc
    except (ValueError, KeyError) as exc:
        raise StorageIntegrityError(f"Storage metadata is invalid: {exc}") from exc


def initialize(settings: Settings) -> dict[str, Any]:
    with open_application(settings) as application:
        return {
            "data_dir": str(application.paths.root),
            "database": str(application.paths.database),
            "vectors": str(application.paths.vectors),
            "initialized": True,
        }
