import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from socialdna.application.bootstrap import open_application
from socialdna.config.settings import Settings
from socialdna.core.exceptions import StorageConflict, StorageIntegrityError
from socialdna.storage.filesystem import FilesystemInfo, detect_filesystem
from socialdna.storage.locking import DataDirectoryLock
from socialdna.storage.vectors import LocalVectorStore


def test_lock_contention_and_release(tmp_path: Path) -> None:
    lock_path = tmp_path / "writer.lock"
    with DataDirectoryLock(lock_path, timeout=0):
        owner = json.loads(lock_path.read_text())
        assert owner["pid"] == os.getpid()
        with pytest.raises(StorageConflict):
            with DataDirectoryLock(lock_path, timeout=0):
                pass
        assert json.loads(lock_path.read_text()) == owner
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; "
                "from socialdna.storage.locking import DataDirectoryLock; "
                "from socialdna.core.exceptions import StorageConflict; "
                "\ntry:\n with DataDirectoryLock(Path(sys.argv[1]),timeout=0): pass\n"
                "except StorageConflict: sys.exit(6)\n",
                str(lock_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 6, result.stderr
    with DataDirectoryLock(lock_path, timeout=0):
        pass


def test_qdrant_client_single_owner_and_close(tmp_path: Path) -> None:
    vector_dir = tmp_path / "vectors"
    with LocalVectorStore(vector_dir) as first:
        assert first.client.get_collections().collections == []
        with pytest.raises(StorageConflict):
            with LocalVectorStore(vector_dir) as second:
                _ = second.client  # Ownership starts with actual lazy native acquisition.
    with LocalVectorStore(vector_dir) as reopened:
        assert reopened.client.get_collections().collections == []
    with pytest.raises(RuntimeError, match="closed"):
        _ = reopened.client


def test_process_crash_releases_application_locks(tmp_path: Path) -> None:
    data = tmp_path / "crashed"
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os,sys; from pathlib import Path; "
            "from socialdna.config.settings import Settings; "
            "from socialdna.application.bootstrap import open_application; "
            "\nwith open_application(Settings(data_dir=Path(sys.argv[1]))): os._exit(23)\n",
            str(data),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 23, process.stderr
    with open_application(Settings(data_dir=data, lock_timeout=0)):
        pass


def test_network_mount_detection_and_no_writes(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mounts = "1 0 8:1 / / rw - ext4 /dev/sda rw\n2 1 0:2 / /mnt/research rw - nfs host:/data rw"
    if sys.platform != "win32":
        assert detect_filesystem(Path("/mnt/research/new/data"), mountinfo=mounts).network
        assert not detect_filesystem(Path("/mnt/research-other"), mountinfo=mounts).network
        escaped = "3 1 0:3 / /mnt/my\\040data rw - cifs //host/data rw"
        assert detect_filesystem(Path("/mnt/my data/library"), mountinfo=escaped).network
    monkeypatch.setattr(
        "socialdna.application.bootstrap.detect_filesystem",
        lambda path: FilesystemInfo("nfs", True, "/mnt/research"),
    )
    with pytest.raises(StorageIntegrityError, match="network filesystem"):
        with open_application(settings):
            pass
    assert not settings.data_dir.exists()
