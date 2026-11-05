"""Bounded search registration, fit ledger and exact observed-unit history.

Revision ID: 0015_discovery
Revises: 0014_profile
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_discovery"
down_revision = "0014_profile"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    sa.Table(
        "discovery_rounds",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("registration_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        sa.Column("result_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.Column("attempt_id", sa.ForeignKey("test_attempts.id"), nullable=False),
        sa.Column("parent_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("max_fits", sa.Integer, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("status IN ('started','completed','failed','refused')"),
        sa.CheckConstraint("max_fits BETWEEN 1 AND 128"),
    )
    sa.Table(
        "discovery_attempts",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("round_id", sa.ForeignKey("discovery_rounds.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("candidate_key", sa.Text, nullable=False),
        sa.Column("phase", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("result_json", sa.Text, nullable=False),
        sa.UniqueConstraint("round_id", "ordinal"),
        sa.CheckConstraint("phase IN ('inner','training','outer')"),
        sa.CheckConstraint("status IN ('started','completed','failed','refused')"),
        sa.CheckConstraint("json_valid(result_json)"),
    )
    members = sa.Table(
        "discovery_members",
        metadata,
        sa.Column("round_id", sa.ForeignKey("discovery_rounds.id"), primary_key=True),
        sa.Column("member_key", sa.Text, primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.CheckConstraint("role IN ('train','test','transfer','purged')"),
    )
    sa.Index("ix_discovery_member", members.c.member_key)
    sa.Table(
        "discovery_bindings",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("round_id", sa.ForeignKey("discovery_rounds.id"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.CheckConstraint("role IN ('registration','result','pattern')"),
    )


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0013_context import _metadata
    from socialdna.storage.migrations.versions.v0013_context import extend_metadata as context
    from socialdna.storage.migrations.versions.v0014_profile import extend_metadata as profile

    metadata = _metadata()
    context(metadata)
    profile(metadata)
    previous = set(metadata.tables)
    extend_metadata(metadata)
    for table in metadata.tables.values():
        if table.name not in previous:
            table.create(op.get_bind())


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM discovery_rounds LIMIT 1").first():
        raise RuntimeError("Refusing to discard discovery history; restore a verified backup")
    for name in (
        "discovery_bindings",
        "discovery_members",
        "discovery_attempts",
        "discovery_rounds",
    ):
        op.execute(f"DROP TABLE {name}")
