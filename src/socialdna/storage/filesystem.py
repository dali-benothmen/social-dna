import re
import sys
from dataclasses import dataclass
from pathlib import Path

NETWORK_FILESYSTEMS = {"nfs", "nfs4", "cifs", "smbfs", "smb3", "fuse.sshfs", "9p", "afs", "ceph"}


@dataclass(frozen=True)
class FilesystemInfo:
    kind: str | None
    network: bool
    mount: str | None


def _unescape_mount(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def detect_filesystem(path: Path, *, mountinfo: str | None = None) -> FilesystemInfo:
    """Longest-prefix Linux mount lookup; UNC paths are unsupported on Windows."""
    resolved = path.resolve()
    if str(path).startswith("\\\\"):
        return FilesystemInfo("unc", True, str(path))
    if mountinfo is None:
        if sys.platform != "linux":
            return FilesystemInfo(None, False, None)
        try:
            mountinfo = Path("/proc/self/mountinfo").read_text()
        except OSError:
            return FilesystemInfo(None, False, None)
    matches: list[tuple[Path, str]] = []
    for line in mountinfo.splitlines():
        left, separator, right = line.partition(" - ")
        fields, filesystem = left.split(), right.split()
        if not separator or len(fields) < 5 or not filesystem:
            continue
        mount = Path(_unescape_mount(fields[4]))
        if resolved.is_relative_to(mount):
            matches.append((mount, filesystem[0]))
    if not matches:
        return FilesystemInfo(None, False, None)
    mount, kind = max(matches, key=lambda item: len(str(item[0])))
    return FilesystemInfo(kind, kind in NETWORK_FILESYSTEMS, str(mount))
