"""Explicit OS-maintenance setup, never a silently installed background service.

The first live source route requires a real active, matching systemd user timer.
Offline/core operations are portable; additional scheduler adapters are not implied.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from socialdna.config.settings import Settings
from socialdna.core.exceptions import ConfigurationError, StoragePermissionError


def _quoted(value: str) -> str:
    if any(ord(character) < 32 for character in value):
        raise ConfigurationError("Maintenance paths cannot contain control characters")
    return (
        '"'
        + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
        + '"'
    )


def units(settings: Settings) -> dict[str, str]:
    root = str(settings.data_dir.resolve())
    name = "socialdna-workflow-" + hashlib.sha256(root.encode()).hexdigest()[:12]
    command = " ".join(
        _quoted(value)
        for value in (
            sys.executable,
            "-m",
            "socialdna",
            "--data-dir",
            root,
            "--offline",
            "--no-ai",
            "workflow",
            "maintain",
        )
    )
    return {
        name + ".service": (
            "[Unit]\nDescription=Expire managed SocialDNA source captures\n\n"
            "[Service]\nType=oneshot\nUMask=0077\nExecStart=" + command + "\n"
        ),
        name + ".timer": (
            "[Unit]\nDescription=Maintain SocialDNA source retention\n\n"
            "[Timer]\nOnCalendar=hourly\nPersistent=true\nRandomizedDelaySec=5m\n"
            "Unit=" + name + ".service\n\n[Install]\nWantedBy=timers.target\n"
        ),
    }


def _properties(program: str, unit: str) -> dict[str, str]:
    result = subprocess.run(
        [
            program,
            "--user",
            "show",
            unit,
            "--property=ActiveState,FragmentPath,DropInPaths,NeedDaemonReload,Unit",
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    if result.returncode:
        return {}
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def verified(settings: Settings) -> bool:
    if sys.platform != "linux" or not (program := shutil.which("systemctl")):
        return False
    expected = units(settings)
    timer = next(name for name in expected if name.endswith(".timer"))
    try:
        for name, content in expected.items():
            properties = _properties(program, name)
            if (
                properties.get("NeedDaemonReload") != "no"
                or properties.get("DropInPaths")
                or (name == timer and properties.get("ActiveState") != "active")
                or (name == timer and properties.get("Unit") != timer[:-6] + ".service")
            ):
                return False
            path = Path(properties.get("FragmentPath", ""))
            if not path.is_absolute() or not path.is_file() or path.stat().st_size > 16_384:
                return False
            if path.read_text(encoding="utf-8") != content:
                return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return True


def configuration(settings: Settings, output_dir: Path | None = None) -> dict[str, Any]:
    content = units(settings)
    if output_dir is not None:
        output_dir = output_dir.expanduser().absolute()
        if output_dir.exists() or output_dir.is_symlink() or not output_dir.parent.is_dir():
            raise ConfigurationError(
                "Maintenance export needs a new directory with an existing parent"
            )
        try:
            output_dir.mkdir()
            for name, text in content.items():
                with (output_dir / name).open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
        except OSError:
            raise StoragePermissionError(
                "Maintenance export failed; inspect the destination before retrying"
            ) from None
    return {
        "files": content,
        "maintenance_verified": verified(settings),
        "export_path": str(output_dir) if output_dir else None,
        "host_configuration_changed": False,
        "limitations": [
            "Exporting units does not install or activate them. "
            "Installation needs explicit authority.",
            "Only a matching active systemd user timer is supported for live source retention.",
            "A stopped/offline machine cannot guarantee wall-clock deletion; "
            "external copies/backups "
            "remain the operator's responsibility.",
        ],
    }
