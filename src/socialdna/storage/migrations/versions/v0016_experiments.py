"""Actual experiment registrations, result bindings and immutable assessment lineage.

Revision ID: 0016_experiments
Revises: 0015_discovery
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_experiments"
down_revision = "0015_discovery"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    def ref(
        name: str, target: str = "entity_revisions.id", *, primary: bool = False
    ) -> sa.Column[str]:
        return sa.Column(name, sa.ForeignKey(target), primary_key=primary, nullable=False)

    sa.Table(
        "experiment_registrations",
        metadata,
        ref("revision_id", primary=True),
        sa.Column("protocol_hash", sa.Text, nullable=False),
        sa.Column("registered_at", sa.Text, nullable=False),
    )
    results = sa.Table(
        "experiment_results",
        metadata,
        ref("revision_id", primary=True),
        ref("registration_revision_id", "experiment_registrations.revision_id"),
    )
    sa.Index("ix_experiment_results_registration", results.c.registration_revision_id)
    sa.Table(
        "experiment_measurement_bindings",
        metadata,
        ref("results_revision_id", "experiment_results.revision_id", primary=True),
        sa.Column("unit_key_hash", sa.Text, primary_key=True),
        sa.Column("outcome_key_hash", sa.Text, primary_key=True),
        ref("subject_revision_id"),
        ref("measurement_revision_id", "metric_measurements.revision_id"),
    )
    sa.Table(
        "experiment_analyses",
        metadata,
        ref("revision_id", primary=True),
        ref("registration_revision_id", "experiment_registrations.revision_id"),
        ref("results_revision_id", "experiment_results.revision_id"),
        ref("attempt_id", "test_attempts.id"),
        sa.UniqueConstraint("results_revision_id"),
    )
    assessments = sa.Table(
        "experiment_assessments",
        metadata,
        ref("revision_id", primary=True),
        ref("analysis_revision_id", "experiment_analyses.revision_id"),
        ref("prior_revision_id", "research_assessments.revision_id"),
        ref("question_revision_id"),
    )
    sa.Index("ix_experiment_assessment_question", assessments.c.question_revision_id)
    sa.Table(
        "experiment_hypotheses",
        metadata,
        ref("assessment_revision_id", "experiment_assessments.revision_id", primary=True),
        ref("hypothesis_revision_id", primary=True),
    )


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0013_context import _metadata
    from socialdna.storage.migrations.versions.v0013_context import extend_metadata as context
    from socialdna.storage.migrations.versions.v0014_profile import extend_metadata as profile
    from socialdna.storage.migrations.versions.v0015_discovery import extend_metadata as discovery

    metadata = _metadata()
    for extend in (context, profile, discovery):
        extend(metadata)
    prior = set(metadata.tables)
    extend_metadata(metadata)
    for table in metadata.tables.values():
        if table.name not in prior:
            table.create(op.get_bind())


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM experiment_registrations LIMIT 1").first():
        raise RuntimeError("Refusing to discard experiment history; restore a verified backup")
    for table in (
        "experiment_hypotheses",
        "experiment_assessments",
        "experiment_analyses",
        "experiment_measurement_bindings",
        "experiment_results",
        "experiment_registrations",
    ):
        op.execute(f"DROP TABLE {table}")
