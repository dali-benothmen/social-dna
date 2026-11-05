"""Source-defined behavioral observations, exact bins and account outcomes.

Revision ID: 0009_behavioral
Revises: 0008_audience
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_behavioral"
down_revision = "0008_audience"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    evidence = metadata.tables["evidence_revisions"]
    for constraint in list(evidence.constraints):
        if isinstance(constraint, sa.CheckConstraint) and "locator_kind IN" in str(
            constraint.sqltext
        ):
            evidence.constraints.remove(constraint)
    evidence.append_constraint(
        sa.CheckConstraint(
            "locator_kind IN ('media_span','comment_span','metric_snapshot','statistical_result',"
            "'creative_event','creative_coverage','post_text','audience_record','behavioral_record')"
        )
    )

    def ref(
        name: str,
        target: str = "entity_revisions.id",
        *,
        primary: bool = False,
        nullable: bool = False,
    ) -> sa.Column[str]:
        return sa.Column(name, sa.ForeignKey(target), primary_key=primary, nullable=nullable)

    for name in ("behavioral_metric_definitions", "audience_cohorts"):
        table = sa.Table(
            name,
            metadata,
            ref("revision_id", primary=True),
            sa.Column("key", sa.Text, nullable=False),
        )
        sa.Index("ix_" + name + "_key", table.c.key)
    for name in ("metric_measurements", "metric_series", "attribution_observations"):
        table = sa.Table(
            name,
            metadata,
            ref("revision_id", primary=True),
            sa.Column("key", sa.Text, nullable=False),
            ref("subject_revision_id"),
            ref("definition_revision_id", "behavioral_metric_definitions.revision_id"),
            ref("cohort_revision_id", "audience_cohorts.revision_id"),
            sa.Column("window_start", sa.Text, nullable=False),
            sa.Column("window_end", sa.Text, nullable=False),
            sa.Column("data_cutoff", sa.Text),
            sa.Column("value", sa.Float),
            sa.Column("availability", sa.Text),
        )
        sa.Index(
            "ix_" + name + "_subject_definition_window",
            table.c.subject_revision_id,
            table.c.definition_revision_id,
            table.c.window_end,
        )
    sa.Table(
        "metric_bins",
        metadata,
        ref("revision_id", primary=True),
        ref("series_revision_id", "metric_series.revision_id"),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("source_start", sa.Float),
        sa.Column("source_end", sa.Float),
        sa.Column("source_point", sa.Float),
        sa.Column("value", sa.Float),
        sa.Column("availability", sa.Text, nullable=False),
        sa.UniqueConstraint("series_revision_id", "ordinal"),
        sa.CheckConstraint("ordinal >= 0"),
        sa.CheckConstraint(
            "(source_point IS NOT NULL AND source_start IS NULL AND source_end IS NULL)"
            " OR (source_point IS NULL AND source_start IS NOT NULL "
            "AND source_end IS NOT NULL AND source_start < source_end)"
        ),
    )
    sa.Table(
        "signed_metric_changes",
        metadata,
        ref("revision_id", primary=True),
        ref("account_revision_id"),
        ref("definition_revision_id", "behavioral_metric_definitions.revision_id"),
        ref("cohort_revision_id", "audience_cohorts.revision_id"),
        ref("start_measurement_revision_id", "metric_measurements.revision_id", nullable=True),
        ref("end_measurement_revision_id", "metric_measurements.revision_id", nullable=True),
        ref("supplied_measurement_revision_id", "metric_measurements.revision_id", nullable=True),
        sa.Column("value", sa.Float),
        sa.CheckConstraint(
            "(supplied_measurement_revision_id IS NOT NULL AND "
            "start_measurement_revision_id IS NULL AND end_measurement_revision_id IS NULL)"
            " OR (supplied_measurement_revision_id IS NULL AND "
            "start_measurement_revision_id IS NOT NULL AND end_measurement_revision_id IS NOT NULL)"
        ),
    )
    sa.Table(
        "behavioral_analyses",
        metadata,
        ref("revision_id", primary=True),
        ref("run_id", "analysis_runs.id"),
        sa.Column("fingerprint", sa.Text, nullable=False, unique=True),
        sa.UniqueConstraint("run_id"),
    )
    sa.Table(
        "behavioral_evidence_bindings",
        metadata,
        ref("evidence_revision_id", "evidence_revisions.id", primary=True),
        ref("subject_revision_id"),
    )
    dependencies = sa.Table(
        "behavioral_dependencies",
        metadata,
        ref("parent_revision_id", primary=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        ref("entity_revision_id", nullable=True),
        ref("evidence_revision_id", "evidence_revisions.id", nullable=True),
        sa.CheckConstraint(
            "(entity_revision_id IS NOT NULL) != (evidence_revision_id IS NOT NULL)"
        ),
    )
    sa.Index("ix_behavioral_entity_dependents", dependencies.c.entity_revision_id)
    sa.Index("ix_behavioral_evidence_dependents", dependencies.c.evidence_revision_id)


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0008_audience import _metadata, extend_metadata

    result = _metadata()
    extend_metadata(result)
    return result


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0006_designs import _rebuild_evidence

    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for table in metadata.sorted_tables:
        if table.name in baseline:
            continue
        table.create(op.get_bind())
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER behavioral_{table.name}_{operation.lower()} BEFORE {operation} "
                f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable behavioral history'); END"
            )


def downgrade() -> None:
    from socialdna.storage.migrations.versions.v0006_designs import _rebuild_evidence

    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    if op.get_bind().scalar(
        sa.select(sa.exists().select_from(metadata.tables["entity_revisions"]))
    ):
        raise RuntimeError("Refusing to discard behavioral history; restore a verified backup")
    for table in reversed(metadata.sorted_tables):
        if table.name not in baseline:
            if op.get_bind().scalar(sa.select(sa.exists().select_from(table))):
                raise RuntimeError(
                    "Refusing to discard behavioral history; restore a verified backup"
                )
            table.drop(op.get_bind())
    _rebuild_evidence(_metadata())
