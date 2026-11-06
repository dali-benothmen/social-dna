"""Source-qualified assisted media compositions.

Revision ID: 0019_content
Revises: 0018_workflows
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_content"
down_revision = "0018_workflows"
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
            evidence.append_constraint(sa.CheckConstraint(previous[:-1] + ",'content_record')"))
    sa.Table(
        "content_records",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("workflow_id", sa.ForeignKey("workflow_sessions.id"), nullable=False),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id")),
    )
    sa.Table(
        "content_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column(
            "subject_revision_id", sa.ForeignKey("content_records.revision_id"), nullable=False
        ),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0017_images import _metadata
    from socialdna.storage.migrations.versions.v0017_images import extend_metadata as images
    from socialdna.storage.migrations.versions.v0018_workflows import extend_metadata as workflows

    result = _metadata()
    images(result)
    workflows(result)
    return result


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    metadata = _metadata()
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for name in ("content_records", "content_evidence_bindings"):
        metadata.tables[name].create(op.get_bind())
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER content_{name}_{operation.lower()} "
                f"BEFORE {operation} ON {name} BEGIN "
                "SELECT RAISE(ABORT,'immutable content history'); END"
            )


def downgrade() -> None:
    if (
        op.get_bind().exec_driver_sql("SELECT 1 FROM content_records LIMIT 1").first()
        or op.get_bind().exec_driver_sql("SELECT 1 FROM evidence_revisions LIMIT 1").first()
    ):
        # A direct Alembic caller may still have FK enforcement enabled. Never
        # rebuild a referenced populated evidence table during a downgrade.
        raise RuntimeError("Refusing to discard canonical history; restore a verified backup")
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    for name in ("content_evidence_bindings", "content_records"):
        op.execute(f"DROP TABLE {name}")
    _rebuild_evidence(_metadata())
