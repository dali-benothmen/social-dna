"""Time-aware statistical designs, feature lineage and declared test ledgers.

Revision ID: 0006_designs
Revises: 0005_evidence
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_designs"
down_revision = "0005_evidence"
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
            "locator_kind IN ('media_span','comment_span','metric_snapshot','statistical_result')"
        )
    )

    def text(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False)

    def document(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, sa.CheckConstraint(f"json_valid({name})"), nullable=False)

    sa.Table(
        "post_media_versions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("post_id", sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        # NULL is an explicit invalidation after a supplied URI changes.
        sa.Column("media_id", sa.ForeignKey("media_assets.id")),
        sa.Column("source_id", sa.ForeignKey("source_records.id")),
        text("available_at"),
    )
    sa.Table(
        "feature_recipes",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        text("version"),
        document("spec_json"),
        text("available_at"),
    )
    sa.Table(
        "feature_values",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("post_id", sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("subject_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        sa.Column("recipe_id", sa.ForeignKey("feature_recipes.id"), nullable=False),
        text("feature_key"),
        sa.Column("value", sa.Float),
        sa.Column("available_at", sa.Text),
        sa.Column("content_valid_at", sa.Text),
        text("materialized_at"),
        document("lineage_json"),
        text("coverage"),
    )
    sa.Table(
        "analysis_feature_values",
        metadata,
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), primary_key=True),
        sa.Column("feature_value_id", sa.ForeignKey("feature_values.id"), primary_key=True),
    )
    sa.Table(
        "analysis_references",
        metadata,
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), primary_key=True),
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        document("input_json"),
    )
    sa.Table(
        "test_families",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        document("spec_json"),
        text("created_at"),
    )
    sa.Table(
        "test_attempts",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("family_id", sa.ForeignKey("test_families.id"), nullable=False),
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), unique=True),
        text("status"),
        document("result_json"),
        text("created_at"),
        sa.CheckConstraint("status IN ('started','completed','failed','refused')"),
    )
    sa.Table(
        "holdout_uses",
        metadata,
        # Both a named reservation and its exact tested-post fingerprint are single use.
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("fingerprint", sa.Text, nullable=False, unique=True),
        sa.Column("attempt_id", sa.ForeignKey("test_attempts.id"), nullable=False),
        document("split_json"),
        text("consumed_at"),
    )
    sa.Table(
        "holdout_members",
        metadata,
        sa.Column("member_key", sa.Text, primary_key=True),
        sa.Column("holdout_id", sa.ForeignKey("holdout_uses.id"), nullable=False),
        sa.Column("post_id", sa.ForeignKey("posts.id")),
        sa.Column("media_sha256", sa.ForeignKey("media_assets.sha256")),
        sa.CheckConstraint("(post_id IS NOT NULL) != (media_sha256 IS NOT NULL)"),
        sa.CheckConstraint(
            "member_key = CASE WHEN post_id IS NOT NULL "
            "THEN 'post:' || post_id ELSE 'sha256:' || media_sha256 END"
        ),
    )
    sa.Table(
        "statistical_entity_bindings",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), nullable=False),
    )
    sa.Table(
        "statistical_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), nullable=False),
        sa.Column("result_id", sa.ForeignKey("statistical_results.id")),
        sa.Column("diagnostic", sa.Text),
        sa.CheckConstraint("(result_id IS NOT NULL) != (diagnostic IS NOT NULL)"),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
    from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata as timeline
    from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment
    from socialdna.storage.migrations.versions.v0004_analytics import extend_metadata as analytics
    from socialdna.storage.migrations.versions.v0005_evidence import extend_metadata as evidence

    result = foundation_metadata()
    for extend in (timeline, enrichment, analytics, evidence):
        extend(result)
    return result


def _rebuild_evidence(metadata: sa.MetaData) -> None:
    # The migration runner disables FK enforcement BEFORE BEGIN, checks all FKs
    # before COMMIT and restores enforcement. No writable_schema manipulation.
    original = metadata.tables["evidence_revisions"]
    temporary = original.to_metadata(sa.MetaData(), name="evidence_revisions_new")
    # FK targets must be resolvable while compiling the temporary table.
    for table in metadata.sorted_tables:
        if table.name != original.name:
            table.to_metadata(temporary.metadata)
    temporary.indexes.clear()
    temporary.create(op.get_bind())
    columns = ",".join(column.name for column in original.columns)
    op.execute(
        f"INSERT INTO evidence_revisions_new ({columns}) SELECT {columns} FROM evidence_revisions"
    )
    op.execute("DROP TABLE evidence_revisions")
    op.execute("ALTER TABLE evidence_revisions_new RENAME TO evidence_revisions")
    for index in original.indexes:
        index.create(op.get_bind())
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER r1_evidence_revisions_{operation.lower()} BEFORE {operation} "
            "ON evidence_revisions BEGIN SELECT RAISE(ABORT, 'immutable evidence history'); END"
        )


def upgrade() -> None:
    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for table in metadata.sorted_tables:
        if table.name not in baseline:
            table.create(op.get_bind())
            for operation in ("UPDATE", "DELETE"):
                if table.name == "test_attempts" and operation == "UPDATE":
                    op.execute(
                        "CREATE TRIGGER designs_attempt_transition BEFORE UPDATE ON test_attempts "
                        "WHEN OLD.status != 'started' OR NEW.status NOT IN ('completed','failed') "
                        "OR NEW.id != OLD.id OR "
                        "NEW.family_id != OLD.family_id OR NEW.created_at != OLD.created_at "
                        "BEGIN SELECT RAISE(ABORT, 'completed attempts are immutable'); END"
                    )
                    continue
                op.execute(
                    f"CREATE TRIGGER designs_{table.name}_{operation.lower()} BEFORE {operation} "
                    f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable analysis history'); END"
                )


def downgrade() -> None:
    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    added = [table for table in metadata.sorted_tables if table.name not in baseline]
    if any(op.get_bind().scalar(sa.select(sa.exists().select_from(table))) for table in added) or (
        op.get_bind().scalar(
            sa.select(sa.exists().select_from(metadata.tables["entity_revisions"]))
        )
    ):
        raise RuntimeError("Refusing to discard statistical history; restore a verified backup")
    for table in reversed(added):
        table.drop(op.get_bind())
    _rebuild_evidence(_metadata())
