"""Durable bounded URL acquisition and exact output bindings.

Revision ID: 0018_workflows
Revises: 0017_images
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_workflows"
down_revision = "0017_images"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    sa.Table(
        "workflow_sessions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("request_json", sa.Text, nullable=False),
        sa.Column("plan_json", sa.Text, nullable=False),
        sa.Column("plan_hash", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("action_code", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("json_valid(request_json) AND json_valid(plan_json)"),
        sa.CheckConstraint("length(plan_hash)=64"),
        sa.CheckConstraint(
            "state IN ('planned','running','awaiting_action','completed',"
            "'partial','failed','cancelled')"
        ),
    )
    sa.Table(
        "workflow_targets",
        metadata,
        sa.Column("workflow_id", sa.ForeignKey("workflow_sessions.id"), primary_key=True),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("target_kind", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("canonical_url", sa.Text, nullable=False),
    )
    sa.Table(
        "workflow_attempts",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("workflow_id", sa.ForeignKey("workflow_sessions.id"), nullable=False),
        sa.Column("attempt_no", sa.Integer, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("deadline_at", sa.Text, nullable=False),
        sa.Column("finished_at", sa.Text),
        sa.Column("retry_at", sa.Text),
        sa.Column("error_code", sa.Text),
        sa.UniqueConstraint("workflow_id", "attempt_no"),
        sa.CheckConstraint("attempt_no BETWEEN 1 AND 3"),
        sa.CheckConstraint("state IN ('running','committed','failed','interrupted')"),
    )
    captures = sa.Table(
        "acquisition_captures",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("attempt_id", sa.ForeignKey("workflow_attempts.id"), nullable=False, unique=True),
        sa.Column("source_id", sa.ForeignKey("source_records.id"), nullable=False, unique=True),
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False, unique=True),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("policy_version", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.CheckConstraint("state IN ('active','purge_pending','erased')"),
    )
    sa.Index("ix_acquisition_expiry", captures.c.state, captures.c.expires_at)
    sa.Table(
        "workflow_bindings",
        metadata,
        sa.Column("workflow_id", sa.ForeignKey("workflow_sessions.id"), primary_key=True),
        sa.Column("role", sa.Text, primary_key=True),
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("capture_id", sa.ForeignKey("acquisition_captures.id")),
        sa.CheckConstraint("role IN ('account','post','capture','report')"),
    )


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0017_images import _metadata
    from socialdna.storage.migrations.versions.v0017_images import extend_metadata as images

    metadata = _metadata()
    images(metadata)
    prior = set(metadata.tables)
    extend_metadata(metadata)
    for name in metadata.tables:
        if name not in prior:
            metadata.tables[name].create(op.get_bind())


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM workflow_sessions LIMIT 1").first():
        raise RuntimeError("Refusing to discard workflow history; restore a verified backup")
    for name in (
        "workflow_bindings",
        "acquisition_captures",
        "workflow_attempts",
        "workflow_targets",
        "workflow_sessions",
    ):
        op.execute(f"DROP TABLE {name}")
