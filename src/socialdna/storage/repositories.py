from typing import Any

from sqlalchemy import Connection, RowMapping, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.core.enums import AvailabilityStatus
from socialdna.core.hashing import canonical_json
from socialdna.core.ids import new_id, stable_id
from socialdna.core.time import utc_now
from socialdna.storage.schema import metadata


class Repository:
    """Core repository methods; transaction lifetime belongs to the caller."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def upsert_account(
        self,
        platform: str,
        external_id: str,
        *,
        handle: str | None = None,
        profile: dict[str, Any] | None = None,
    ) -> str:
        account_id = stable_id("account", platform, external_id)
        table = metadata.tables["accounts"]
        statement = insert(table).values(
            id=account_id,
            platform=platform,
            external_id=external_id,
            handle=handle,
            profile_json=canonical_json(profile or {}),
        )
        changes = {}
        if handle is not None:
            changes["handle"] = statement.excluded.handle
        if profile is not None:
            changes["profile_json"] = statement.excluded.profile_json
        conflict_keys = [table.c.platform, table.c.external_id]
        self.connection.execute(
            statement.on_conflict_do_update(index_elements=conflict_keys, set_=changes)
            if changes
            else statement.on_conflict_do_nothing(index_elements=conflict_keys)
        )
        return account_id

    def account(self, account_id: str) -> RowMapping | None:
        table = metadata.tables["accounts"]
        return (
            self.connection.execute(select(table).where(table.c.id == account_id))
            .mappings()
            .one_or_none()
        )

    def record_source(
        self,
        *,
        source_kind: str,
        source_uri: str,
        permission_basis: str,
        raw_artifact_id: str | None = None,
        terms: dict[str, Any] | None = None,
    ) -> str:
        source_id = new_id()
        self.connection.execute(
            metadata.tables["source_records"]
            .insert()
            .values(
                id=source_id,
                source_kind=source_kind,
                source_uri=source_uri,
                permission_basis=permission_basis,
                raw_artifact_id=raw_artifact_id,
                terms_json=canonical_json(terms or {}),
                retrieved_at=utc_now(),
            )
        )
        return source_id

    def set_unavailable(
        self,
        *,
        subject_type: str,
        subject_id: str,
        field_key: str,
        status: AvailabilityStatus,
        reason: str,
        provenance_id: str | None = None,
    ) -> None:
        table = metadata.tables["data_availability"]
        statement = insert(table).values(
            subject_type=subject_type,
            subject_id=subject_id,
            field_key=field_key,
            status=status.value,
            reason=reason,
            observed_at=utc_now(),
            provenance_id=provenance_id,
        )
        self.connection.execute(
            statement.on_conflict_do_update(
                index_elements=[table.c.subject_type, table.c.subject_id, table.c.field_key],
                set_={
                    name: getattr(statement.excluded, name)
                    for name in ("status", "reason", "observed_at", "provenance_id")
                },
            )
        )
