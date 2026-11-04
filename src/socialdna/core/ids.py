import json
from uuid import UUID, uuid4, uuid5

# This namespace is part of the persisted identity contract; never change it.
SOCIALDNA_NAMESPACE = UUID("cd423599-0c19-4cb5-810f-e128eac3a8ad")


def new_id() -> str:
    return str(uuid4())


def stable_id(kind: str, *external_parts: str) -> str:
    """Length-unambiguous, platform-aware external and derived identifiers."""
    if not kind or not external_parts:
        raise ValueError("Stable IDs require a kind and at least one identity part")
    name = json.dumps([kind, *external_parts], ensure_ascii=False, separators=(",", ":"))
    return str(uuid5(SOCIALDNA_NAMESPACE, name))
