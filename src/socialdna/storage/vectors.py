from pathlib import Path
from types import TracebackType

from qdrant_client import QdrantClient

from socialdna.core.exceptions import StorageConflict, StorageIntegrityError


class LocalVectorStore:
    """Own exactly one embedded client; initialization performs no inference."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._client: QdrantClient | None = None

    def __enter__(self) -> "LocalVectorStore":
        if self._client is not None:
            raise StorageConflict("Qdrant Local client is already open in this application.")
        try:
            self._client = QdrantClient(path=str(self.path))
        except RuntimeError as exc:
            if "already accessed" in str(exc):
                raise StorageConflict(
                    "Qdrant Local is in use by another client.",
                    next_action="Close the other client and retry; never remove its lock file.",
                ) from exc
            raise StorageIntegrityError(f"Cannot open Qdrant Local: {exc}") from exc
        return self

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            raise RuntimeError("Qdrant Local is closed")
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
