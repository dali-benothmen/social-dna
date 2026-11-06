"""Static asset/region citations and canonical ordered analyses.

Revision ID: 0017_images
Revises: 0016_experiments
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_images"
down_revision = "0016_experiments"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    evidence = metadata.tables["evidence_revisions"]
    for constraint in list(evidence.constraints):
        if isinstance(constraint, sa.CheckConstraint) and "locator_kind IN" in str(
            constraint.sqltext
        ):
            prior = str(constraint.sqltext)
            evidence.constraints.remove(constraint)
            evidence.append_constraint(sa.CheckConstraint(prior[:-1] + ",'image_record')"))
    sa.Table(
        "static_records",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id")),
        sa.Column("media_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.Column("post_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.CheckConstraint("(media_revision_id IS NOT NULL) != (post_revision_id IS NOT NULL)"),
    )
    sa.Table(
        "static_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("subject_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
    )
    sa.Table(
        "task_citation_inputs",
        metadata,
        sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), primary_key=True),
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0013_context import _metadata
    from socialdna.storage.migrations.versions.v0013_context import extend_metadata as context
    from socialdna.storage.migrations.versions.v0014_profile import extend_metadata as profile
    from socialdna.storage.migrations.versions.v0015_discovery import extend_metadata as discovery
    from socialdna.storage.migrations.versions.v0016_experiments import (
        extend_metadata as experiments,
    )

    result = _metadata()
    for extend in (context, profile, discovery, experiments):
        extend(result)
    return result


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    metadata = _metadata()
    prior = set(metadata.tables)
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for name in metadata.tables:
        if name not in prior:
            metadata.tables[name].create(op.get_bind())


def downgrade() -> None:
    if (
        # As in earlier evidence rebuilds, reject populated canonical history
        # before any DDL, including when the new static tables are still empty.
        op.get_bind().exec_driver_sql("SELECT 1 FROM entity_revisions LIMIT 1").first()
        or op.get_bind().exec_driver_sql("SELECT 1 FROM static_evidence_bindings LIMIT 1").first()
        or op.get_bind().exec_driver_sql("SELECT 1 FROM static_records LIMIT 1").first()
    ):
        raise RuntimeError("Refusing to discard static evidence; restore a verified backup")
    from socialdna.storage.migrations.versions.v0011_research import _rebuild_evidence

    for name in ("task_citation_inputs", "static_evidence_bindings", "static_records"):
        op.execute(f"DROP TABLE {name}")
    _rebuild_evidence(_metadata())
