"""Observable creative events and pinned multimodal recipes.

Revision ID: 0007_creative
Revises: 0006_designs
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_creative"
down_revision = "0006_designs"
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
            "'creative_event','creative_coverage','post_text')"
        )
    )
    values = metadata.tables["feature_values"]
    values.c.post_id.nullable = True
    values.append_column(sa.Column("media_id", sa.ForeignKey("media_assets.id")))
    values.append_constraint(sa.CheckConstraint("(post_id IS NOT NULL) != (media_id IS NOT NULL)"))

    def text(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False)

    sets = sa.Table(
        "creative_annotation_sets",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("media_id", sa.ForeignKey("media_assets.id"), nullable=False),
        text("key"),
        text("available_at"),
        sa.Column("source_id", sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("producer_run_id", sa.ForeignKey("analysis_runs.id")),
        sa.Column("producer_task_id", sa.ForeignKey("analysis_tasks.id")),
    )
    sa.Index("ix_creative_sets_media_key_time", sets.c.media_id, sets.c.key, sets.c.available_at)
    events = sa.Table(
        "creative_events",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("media_id", sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("post_revision_id", sa.ForeignKey("entity_revisions.id")),
        sa.Column("technique_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        text("state"),
        text("verdict"),
        sa.CheckConstraint("state IN ('proposed','reviewed','disputed')"),
        sa.CheckConstraint("verdict IN ('present','ambiguous')"),
    )
    sa.Index(
        "ix_creative_events_media_technique", events.c.media_id, events.c.technique_revision_id
    )
    sa.Table(
        "creative_annotation_members",
        metadata,
        sa.Column(
            "annotation_revision_id",
            sa.ForeignKey("creative_annotation_sets.revision_id"),
            primary_key=True,
        ),
        sa.Column(
            "event_revision_id", sa.ForeignKey("creative_events.revision_id"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.UniqueConstraint("annotation_revision_id", "event_revision_id"),
    )
    sa.Table(
        "creative_coverages",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("media_id", sa.ForeignKey("media_assets.id"), nullable=False),
        text("modality"),
        text("mode"),
    )
    sa.Table(
        "creative_set_coverages",
        metadata,
        sa.Column(
            "annotation_revision_id",
            sa.ForeignKey("creative_annotation_sets.revision_id"),
            primary_key=True,
        ),
        sa.Column(
            "coverage_revision_id", sa.ForeignKey("creative_coverages.revision_id"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer, primary_key=True),
    )
    sa.Table(
        "creative_event_anchors",
        metadata,
        sa.Column(
            "event_revision_id", sa.ForeignKey("creative_events.revision_id"), primary_key=True
        ),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        text("kind"),
        *(
            sa.Column(name, sa.Integer)
            for name in (
                "start_min_ms",
                "start_max_ms",
                "end_min_ms",
                "end_max_ms",
                "nominal_start_ms",
                "nominal_end_ms",
            )
        ),
        sa.Column("unknown_reason", sa.Text),
        sa.Column("box_json", sa.Text),
        sa.CheckConstraint("ordinal >= 0"),
    )
    sa.Table(
        "creative_event_inputs",
        metadata,
        sa.Column(
            "event_revision_id", sa.ForeignKey("creative_events.revision_id"), primary_key=True
        ),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), nullable=False),
        text("modality"),
        text("role"),
    )
    sa.Table(
        "creative_event_relations",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column(
            "annotation_revision_id",
            sa.ForeignKey("creative_annotation_sets.revision_id"),
            nullable=False,
        ),
        sa.Column(
            "source_revision_id", sa.ForeignKey("creative_events.revision_id"), nullable=False
        ),
        sa.Column(
            "target_revision_id", sa.ForeignKey("creative_events.revision_id"), nullable=False
        ),
        text("relation"),
        text("status"),
        sa.Column("tolerance_ms", sa.Integer, nullable=False),
        sa.CheckConstraint("relation IN ('precedes','overlaps','simultaneous_within_tolerance')"),
        sa.CheckConstraint("status IN ('verified','possible')"),
    )
    sa.Table(
        "direct_media_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("media_id", sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("media_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
    )
    sa.Table(
        "post_text_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("post_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        text("field"),
        sa.Column("tag_index", sa.Integer),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.CheckConstraint("start_char >= 0 AND end_char > start_char"),
    )
    sa.Table(
        "creative_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("event_revision_id", sa.ForeignKey("creative_events.revision_id")),
        sa.Column("coverage_revision_id", sa.ForeignKey("creative_coverages.revision_id")),
        sa.CheckConstraint("(event_revision_id IS NOT NULL) != (coverage_revision_id IS NOT NULL)"),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0006_designs import _metadata, extend_metadata

    metadata = _metadata()
    extend_metadata(metadata)
    return metadata


def _rebuild_values(table: sa.Table) -> None:
    connection = op.get_bind()
    old_columns = [
        column["name"]
        for column in sa.inspect(connection).get_columns(table.name)
        if column["name"] in table.c
    ]
    temporary = table.to_metadata(sa.MetaData(), name="feature_values_new")
    for other in table.metadata.sorted_tables:
        if other.name != table.name:
            other.to_metadata(temporary.metadata)
    temporary.indexes.clear()
    temporary.create(connection)
    names = ",".join(old_columns)
    op.execute(f"INSERT INTO feature_values_new ({names}) SELECT {names} FROM feature_values")
    op.execute("DROP TABLE feature_values")
    op.execute("ALTER TABLE feature_values_new RENAME TO feature_values")
    for index in table.indexes:
        index.create(connection)
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER designs_feature_values_{operation.lower()} BEFORE {operation} "
            "ON feature_values BEGIN SELECT RAISE(ABORT, 'immutable analysis history'); END"
        )


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0006_designs import _rebuild_evidence

    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    _rebuild_values(metadata.tables["feature_values"])
    for table in metadata.sorted_tables:
        if table.name not in baseline:
            table.create(op.get_bind())
            for operation in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER creative_{table.name}_{operation.lower()} BEFORE {operation} "
                    f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable creative history'); END"
                )


def downgrade() -> None:
    from socialdna.storage.migrations.versions.v0006_designs import _rebuild_evidence

    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    added = [table for table in metadata.sorted_tables if table.name not in baseline]
    if (
        any(op.get_bind().scalar(sa.select(sa.exists().select_from(table))) for table in added)
        or op.get_bind().scalar(
            sa.select(sa.exists().select_from(metadata.tables["feature_values"]))
        )
        or op.get_bind().scalar(
            sa.select(sa.exists().select_from(metadata.tables["entity_revisions"]))
        )
    ):
        raise RuntimeError("Refusing to discard creative history; restore a verified backup")
    for table in reversed(added):
        table.drop(op.get_bind())
    prior = _metadata()
    _rebuild_values(prior.tables["feature_values"])
    _rebuild_evidence(prior)
