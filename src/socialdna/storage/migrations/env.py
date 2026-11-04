from alembic import context

from socialdna.storage.schema import metadata

# Connections and explicit transaction boundaries belong to the migration runner.
connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=metadata, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
