from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, select

from socialdna.core.exceptions import StorageIntegrityError
from socialdna.core.hashing import hash_file
from socialdna.core.time import utc_now
from socialdna.storage.database import Database
from socialdna.storage.schema import metadata

MIGRATIONS = Path(__file__).parent / "migrations"


def migration_config(location: Path = MIGRATIONS) -> Config:
    config = Config()
    # ConfigParser interprets '%' even in legitimate installation paths.
    config.set_main_option("script_location", str(location).replace("%", "%%"))
    return config


def validate_history(connection: Connection, scripts: ScriptDirectory) -> None:
    heads = MigrationContext.configure(connection).get_current_heads()
    known = {rev.revision: rev for rev in scripts.walk_revisions()}
    if any(head not in known for head in heads):
        raise StorageIntegrityError(
            "Database has an unknown migration revision; use a compatible SocialDNA version."
        )
    tables = set(inspect(connection).get_table_names())
    if not heads and tables - {"alembic_version"}:
        raise StorageIntegrityError("Refusing to migrate an unversioned non-empty database.")
    if heads:
        if "migration_checksums" not in tables:
            raise StorageIntegrityError("Migration checksum ledger is missing.")
        ledger = metadata.tables["migration_checksums"]
        applied: set[str] = set()
        for head in heads:
            applied.update(rev.revision for rev in scripts.walk_revisions(base="base", head=head))
        records = {row.revision: row.sha256 for row in connection.execute(select(ledger))}
        if set(records) != applied:
            raise StorageIntegrityError("Migration checksum ledger does not match applied history.")
        for revision, recorded in records.items():
            if hash_file(Path(known[revision].path)) != recorded:
                raise StorageIntegrityError(f"Applied migration {revision} was modified.")


def migrate(database: Database, *, location: Path = MIGRATIONS) -> None:
    config = migration_config(location)
    scripts = ScriptDirectory.from_config(config)
    if len(scripts.get_heads()) != 1:
        raise StorageIntegrityError("Installed migrations must have one complete revision head.")
    # A real BEGIN (Database's engine event) makes SQLite DDL atomic here.
    with database.transaction() as connection:
        validate_history(connection, scripts)
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        ledger = metadata.tables["migration_checksums"]
        recorded: set[str] = set(connection.scalars(select(ledger.c.revision)))
        for rev in scripts.walk_revisions():
            if rev.revision not in recorded:
                connection.execute(
                    ledger.insert().values(
                        revision=rev.revision,
                        sha256=hash_file(Path(rev.path)),
                        applied_at=utc_now(),
                    )
                )


def current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()
