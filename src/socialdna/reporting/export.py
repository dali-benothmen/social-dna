"""Explicit, non-overwriting report exports. Managed artifacts remain canonical."""

import json
from pathlib import Path
from typing import Any

from socialdna.core.exceptions import ConfigurationError, StoragePermissionError


def export_report(result: dict[str, Any], destination: Path) -> str:
    content = result["content"]
    if result["format"] == "json":
        content = json.dumps(content, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    path = destination.expanduser().absolute()
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ConfigurationError("Report destination exists; nothing was overwritten.") from exc
    except OSError as exc:
        raise StoragePermissionError(
            "Cannot export report; check the parent directory and permissions. "
            "A failed write may leave a partial file; inspect it before retrying."
        ) from exc
    return str(path)
