import sqlite3
from pathlib import Path
from types import TracebackType

from qdrant_client import QdrantClient

from socialdna.core.exceptions import StorageConflict, StorageIntegrityError


class LocalVectorStore:
    """Own exactly one embedded client; initialization performs no inference."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._client: QdrantClient | None = None
        self._active = False

    def __enter__(self) -> "LocalVectorStore":
        if self._active:
            raise StorageConflict("Qdrant Local client is already open in this application.")
        self._active = True
        return self

    def _open(self) -> QdrantClient:
        if not self._active:
            raise RuntimeError("Qdrant Local is closed")
        try:
            self._client = QdrantClient(path=str(self.path))
        except RuntimeError as exc:
            if "already accessed" in str(exc):
                raise StorageConflict(
                    "Qdrant Local is in use by another client.",
                    next_action="Close the other client and retry; never remove its lock file.",
                ) from exc
            raise StorageIntegrityError(f"Cannot open Qdrant Local: {exc}") from exc
        except (OSError, ValueError, sqlite3.DatabaseError) as exc:
            raise StorageIntegrityError(
                "Derived Qdrant storage cannot be opened; canonical SQL/FTS/graph remain available."
            ) from exc
        return self._client

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            return self._open()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._active = False

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
