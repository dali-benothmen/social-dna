import json
import os
import socket
from pathlib import Path
from typing import Any

import portalocker

from socialdna.core.exceptions import StorageConflict
from socialdna.core.time import utc_now


class DataDirectoryLock:
    """OS-released exclusive lock; never remove a live lock file to recover."""

    def __init__(self, path: Path, *, timeout: float = 2.0) -> None:
        self.path = path
        self._lock = portalocker.Lock(
            str(path),
            mode="a+",
            timeout=timeout,
            check_interval=0.05,
            flags=portalocker.LockFlags.EXCLUSIVE | portalocker.LockFlags.NON_BLOCKING,
        )

    def __enter__(self) -> "DataDirectoryLock":
        try:
            stream = self._lock.acquire()
        except portalocker.exceptions.LockException as exc:
            raise StorageConflict(
                f"Another SocialDNA process holds {self.path}.",
                next_action="Wait for the other process to finish; do not delete lock files.",
            ) from exc
        try:
            stream.seek(0)
            stream.truncate()
            json.dump(
                {"pid": os.getpid(), "hostname": socket.gethostname(), "acquired_at": utc_now()},
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            self._lock.release()
            raise
        return self

    def __exit__(self, *_: Any) -> None:
        self._lock.release()
