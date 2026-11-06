import hashlib
import json
from pathlib import Path
from typing import Any


def hash_file(path: Path, *, byte_limit: int | None = None) -> str:
    if byte_limit is not None and byte_limit < 0:
        raise ValueError("Hash byte limit must be non-negative")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as stream:
        while chunk := stream.read(
            1024 * 1024 if byte_limit is None else min(1024 * 1024, byte_limit - consumed + 1)
        ):
            consumed += len(chunk)
            if byte_limit is not None and consumed > byte_limit:
                raise ValueError("File exceeds hash byte limit")
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def hash_config(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
