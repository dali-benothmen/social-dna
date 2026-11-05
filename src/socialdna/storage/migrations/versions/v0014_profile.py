"""Immutable event meanings for actual profile-funnel source definitions.

Revision ID: 0014_profile
Revises: 0013_context
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_profile"
down_revision = "0013_context"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    sa.Table(
        "funnel_event_bindings",
        metadata,
        sa.Column(
            "definition_revision_id",
            sa.ForeignKey("behavioral_metric_definitions.revision_id"),
            primary_key=True,
        ),
        sa.Column(
            "context_revision_id", sa.ForeignKey("context_records.revision_id"), nullable=False
        ),
        sa.Column("signal", sa.Text, nullable=False),
        sa.Column("uniqueness", sa.Text, nullable=False),
        sa.Column("event_code_hash", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "signal IN ('attention','profile_visits','follows','link_clicks','app_installs',"
            "'purchases','returning_followers','churn')"
        ),
        sa.CheckConstraint("uniqueness IN ('unique_accounts','events','unknown')"),
    )


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0013_context import _metadata
    from socialdna.storage.migrations.versions.v0013_context import extend_metadata as context

    metadata = _metadata()
    context(metadata)
    extend_metadata(metadata)
    metadata.tables["funnel_event_bindings"].create(op.get_bind())
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER funnel_event_bindings_{operation.lower()} BEFORE {operation} "
            "ON funnel_event_bindings BEGIN "
            "SELECT RAISE(ABORT,'immutable source event meaning'); END"
        )


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM funnel_event_bindings LIMIT 1").first():
        raise RuntimeError("Refusing to discard source event history; restore a verified backup")
    op.execute("DROP TABLE funnel_event_bindings")
