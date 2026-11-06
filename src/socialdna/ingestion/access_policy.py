"""Source-native display is not permission for derived analytics or semantic indexing."""

from sqlalchemy import Connection, inspect, select

from socialdna.core.exceptions import ConfigurationError
from socialdna.core.time import utc_now
from socialdna.storage.schema import metadata


def restriction(connection: Connection, source_id: str, operation: str) -> str | None:
    # Older-head compatibility fixtures have no workflow source producer.
    if not connection.info.get("workflow_policy_schema"):
        if not inspect(connection).has_table("acquisition_captures"):
            return None
        connection.info["workflow_policy_schema"] = True
    table = metadata.tables["acquisition_captures"]
    row = connection.execute(select(table).where(table.c.source_id == source_id)).mappings().first()
    if row is None:
        return None
    if row["state"] != "active" or row["expires_at"] <= utc_now():
        return "The source capture expired or was erased; refresh requires a new explicit plan."
    if operation not in {"inspect", "native_report"}:
        return (
            "This API capture permits source-native inspection/reporting only; derived analytics, "
            "research claims, embeddings and cross-creator aggregation are not authorized."
        )
    return None


def assert_operation(connection: Connection, source_id: str, operation: str) -> None:
    if reason := restriction(connection, source_id, operation):
        raise ConfigurationError(reason)
