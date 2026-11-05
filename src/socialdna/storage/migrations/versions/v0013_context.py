"""Typed publishing context projections and exact field citations.

Revision ID: 0013_context
Revises: 0012_reevaluation
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_context"
down_revision = "0012_reevaluation"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    evidence = metadata.tables["evidence_revisions"]
    for constraint in list(evidence.constraints):
        if isinstance(constraint, sa.CheckConstraint) and "locator_kind IN" in str(
            constraint.sqltext
        ):
            previous = str(constraint.sqltext)
            evidence.constraints.remove(constraint)
            evidence.append_constraint(sa.CheckConstraint(previous[:-1] + ",'context_record')"))
    records = sa.Table(
        "context_records",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("account_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        sa.Column("post_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.Column("captured_at", sa.Text, nullable=False),
    )
    sa.Index("ix_context_account_capture", records.c.account_revision_id, records.c.captured_at)
    sa.Index("ix_context_post", records.c.post_revision_id)
    sa.Table(
        "context_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column(
            "subject_revision_id", sa.ForeignKey("context_records.revision_id"), nullable=False
        ),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0010_memory import _metadata
    from socialdna.storage.migrations.versions.v0010_memory import extend_metadata as memory
    from socialdna.storage.migrations.versions.v0011_research import extend_metadata as research
    from socialdna.storage.migrations.versions.v0012_reevaluation import (
        extend_metadata as reevaluation,
    )

    result = _metadata()
    memory(result)
    research(result)
    reevaluation(result)
    return result


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    metadata = _metadata()
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for name in ("context_records", "context_evidence_bindings"):
        metadata.tables[name].create(op.get_bind())
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER context_{name}_{operation.lower()} BEFORE {operation} ON {name} "
                "BEGIN SELECT RAISE(ABORT,'immutable context history'); END"
            )


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM entity_revisions LIMIT 1").first():
        raise RuntimeError("Refusing to discard context history; restore a verified backup")
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    for name in ("context_evidence_bindings", "context_records"):
        op.execute(f"DROP TABLE {name}")
    _rebuild_evidence(_metadata())
