"""Rebuildable citation-backed research memory and durable indexing work.

Revision ID: 0010_memory
Revises: 0009_behavioral
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_memory"
down_revision = "0009_behavioral"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    def ref(name: str, target: str, *, nullable: bool = False) -> sa.Column[str]:
        return sa.Column(name, sa.ForeignKey(target), nullable=nullable)

    sa.Table(
        "memory_projection_state",
        metadata,
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )
    sa.Table(
        "memory_changes",
        metadata,
        sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
    )
    sa.Table(
        "embedding_spaces",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("spec_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    documents = sa.Table(
        "vector_documents",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("owner_kind", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("representation_key", sa.Text, nullable=False),
        sa.Column("family", sa.Text, nullable=False),
        ref("desired_revision_id", "vector_document_revisions.id", nullable=True),
        sa.Column("state", sa.Text, nullable=False),
    )
    sa.Index("ix_memory_owner", documents.c.owner_kind, documents.c.owner_id)
    revisions = sa.Table(
        "vector_document_revisions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        ref("document_id", "vector_documents.id"),
        ref("owner_revision_id", "entity_revisions.id"),
        ref("evidence_revision_id", "evidence_revisions.id", nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("available_at", sa.Text),
        sa.Column("redacted", sa.Boolean, nullable=False, server_default="0"),
    )
    sa.Index("ix_memory_revision_owner", revisions.c.owner_revision_id)
    sa.Index("ix_memory_revision_evidence", revisions.c.evidence_revision_id)
    sa.Table(
        "vector_document_evidence",
        metadata,
        sa.Column(
            "document_revision_id", sa.ForeignKey("vector_document_revisions.id"), primary_key=True
        ),
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
    )
    entries = sa.Table(
        "vector_index_entries",
        metadata,
        sa.Column("document_id", sa.ForeignKey("vector_documents.id"), primary_key=True),
        sa.Column("space_id", sa.ForeignKey("embedding_spaces.id"), primary_key=True),
        sa.Column("point_id", sa.Text, nullable=False, unique=True),
        ref("desired_revision_id", "vector_document_revisions.id", nullable=True),
        ref("indexed_revision_id", "vector_document_revisions.id", nullable=True),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("indexed_generation", sa.Integer, nullable=False, server_default="0"),
        sa.Column("state", sa.Text, nullable=False),
        sa.CheckConstraint("generation > 0 AND indexed_generation >= 0"),
    )
    sa.Index("ix_vector_pending", entries.c.space_id, entries.c.state)
    sa.Table(
        "vector_outbox",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        ref("document_id", "vector_documents.id"),
        ref("space_id", "embedding_spaces.id"),
        sa.Column("operation", sa.Text, nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        ref("revision_id", "vector_document_revisions.id", nullable=True),
        sa.Column("content_hash", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("last_error", sa.Text),
        sa.UniqueConstraint("document_id", "space_id", "generation"),
        sa.CheckConstraint("operation IN ('upsert','delete')"),
    )
    sa.Table(
        "graph_nodes",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("entity_id", sa.Text, nullable=False),
    )
    edges = sa.Table(
        "graph_edges",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        ref("source_revision_id", "graph_nodes.revision_id"),
        ref("target_revision_id", "graph_nodes.revision_id"),
        ref("owner_revision_id", "entity_revisions.id"),
        ref("evidence_revision_id", "evidence_revisions.id", nullable=True),
        sa.Column("relation", sa.Text, nullable=False),
        sa.Column("qualification_json", sa.Text, nullable=False),
        sa.Column("projection_version", sa.Text, nullable=False),
    )
    sa.Index("ix_graph_source", edges.c.source_revision_id)
    sa.Index("ix_graph_target", edges.c.target_revision_id)
    sa.Index("ix_graph_owner", edges.c.owner_revision_id)


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0009_behavioral import _metadata, extend_metadata

    result = _metadata()
    extend_metadata(result)
    return result


def upgrade() -> None:
    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    # Explicit ordering avoids the intentional document/current-revision FK cycle.
    for name in (
        "memory_projection_state",
        "memory_changes",
        "embedding_spaces",
        "vector_documents",
        "vector_document_revisions",
        "vector_document_evidence",
        "vector_index_entries",
        "vector_outbox",
        "graph_nodes",
        "graph_edges",
    ):
        assert name not in baseline
        metadata.tables[name].create(op.get_bind())
    op.execute("CREATE VIRTUAL TABLE memory_fts USING fts5(revision_id UNINDEXED, text)")
    for table, kind in (
        ("entity_revisions", "entity"),
        ("evidence_revisions", "evidence"),
        ("evidence_withdrawals", "eligibility"),
        ("audience_tombstones", "eligibility"),
    ):
        key = "target_id" if table == "audience_tombstones" else "id"
        op.execute(
            f"CREATE TRIGGER memory_{table}_insert AFTER INSERT ON {table} BEGIN "
            f"INSERT INTO memory_changes(kind,target_id) VALUES ('{kind}',NEW.{key}); END"
        )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER memory_space_{operation.lower()} BEFORE {operation} "
            "ON embedding_spaces BEGIN SELECT RAISE(ABORT,'immutable embedding space'); END"
        )
    op.execute(
        "INSERT INTO memory_changes(kind,target_id) SELECT 'entity',id FROM entity_revisions"
    )
    op.execute(
        "INSERT INTO memory_changes(kind,target_id) SELECT 'evidence',id FROM evidence_revisions"
    )


def downgrade() -> None:
    # Derived rows can be rebuilt, but registered space provenance must not silently disappear.
    if op.get_bind().exec_driver_sql("SELECT 1 FROM embedding_spaces LIMIT 1").first():
        raise RuntimeError("Refusing to discard embedding-space history; restore a verified backup")
    for table in (
        "entity_revisions",
        "evidence_revisions",
        "evidence_withdrawals",
        "audience_tombstones",
    ):
        op.execute(f"DROP TRIGGER memory_{table}_insert")
    op.execute("DROP TABLE memory_fts")
    for name in (
        "graph_edges",
        "graph_nodes",
        "vector_outbox",
        "vector_index_entries",
        "vector_document_evidence",
        "vector_document_revisions",
        "vector_documents",
        "embedding_spaces",
        "memory_changes",
        "memory_projection_state",
    ):
        op.execute(f"DROP TABLE {name}")
