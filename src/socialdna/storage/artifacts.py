import hashlib
import io
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import Connection, RowMapping, func, select
from sqlalchemy.dialects.sqlite import insert

from socialdna.config.paths import DataPaths
from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import hash_file
from socialdna.core.ids import stable_id
from socialdna.core.time import utc_now
from socialdna.storage.schema import metadata


class ArtifactStore:
    """Atomic content-addressed blobs with canonical, transactional metadata."""

    def __init__(self, paths: DataPaths) -> None:
        self.paths = paths

    def path_for(self, relative_path: str) -> Path:
        target = (self.paths.root / relative_path).resolve()
        if not target.is_relative_to(self.paths.artifacts.resolve()):
            raise StorageIntegrityError("Artifact path escapes the managed artifact directory.")
        return target

    def put_bytes(
        self, connection: Connection, content: bytes, *, kind: str, mime_type: str
    ) -> str:
        return self._put(connection, io.BytesIO(content), kind=kind, mime_type=mime_type)

    def put_file(self, connection: Connection, path: Path, *, kind: str, mime_type: str) -> str:
        with path.open("rb") as stream:
            return self._put(connection, stream, kind=kind, mime_type=mime_type)

    def _put(self, connection: Connection, source: BinaryIO, *, kind: str, mime_type: str) -> str:
        digest = hashlib.sha256()
        length = 0
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.paths.artifacts, prefix=".staged-", delete=False
            ) as destination:
                temporary = Path(destination.name)
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    length += len(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            checksum = digest.hexdigest()
            relative = f"artifacts/objects/{checksum[:2]}/{checksum}"
            target = self.path_for(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hash_file(target) != checksum:
                    raise StorageIntegrityError(f"Existing artifact {checksum} is corrupt.")
            else:
                os.replace(temporary, target)
                if os.name == "posix":
                    descriptor = os.open(target.parent, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            artifact_id = stable_id("artifact", checksum)
            table = metadata.tables["artifact_objects"]
            connection.execute(
                insert(table)
                .values(
                    id=artifact_id,
                    sha256=checksum,
                    kind=kind,
                    mime_type=mime_type,
                    relative_path=relative,
                    byte_size=length,
                    created_at=utc_now(),
                )
                .on_conflict_do_nothing(index_elements=[table.c.sha256])
            )
            return artifact_id
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def add_reference(
        self, connection: Connection, artifact_id: str, *, owner_type: str, owner_id: str, role: str
    ) -> None:
        table = metadata.tables["artifact_references"]
        connection.execute(
            insert(table)
            .values(
                artifact_id=artifact_id,
                owner_type=owner_type,
                owner_id=owner_id,
                role=role,
            )
            .on_conflict_do_nothing()
        )

    def reference_count(self, connection: Connection, artifact_id: str) -> int:
        references = metadata.tables["artifact_references"]
        sources = metadata.tables["source_records"]
        media = metadata.tables["media_assets"]
        # Include direct canonical foreign-key references, not just generic owner links.
        return sum(
            int(
                connection.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(
                        column == artifact_id,
                    )
                )
                or 0
            )
            for table, column in (
                (references, references.c.artifact_id),
                (sources, sources.c.raw_artifact_id),
                (media, media.c.artifact_id),
            )
        )

    def get(self, connection: Connection, artifact_id: str) -> RowMapping:
        table = metadata.tables["artifact_objects"]
        return connection.execute(select(table).where(table.c.id == artifact_id)).mappings().one()

    def verify(self, row: RowMapping) -> bool:
        path = self.path_for(row["relative_path"])
        return (
            path.is_file()
            and path.stat().st_size == row["byte_size"]
            and hash_file(path) == row["sha256"]
        )
