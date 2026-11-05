"""Reviewed literature, prepared protocols and immutable assessments.

Revision ID: 0011_research
Revises: 0010_memory
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_research"
down_revision = "0010_memory"
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
            "'creative_event','creative_coverage','post_text','audience_record','behavioral_record',"
            "'study_excerpt','research_record')"
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

    sa.Table(
        "study_evidence_bindings",
        metadata,
        ref("evidence_revision_id", "evidence_revisions.id", primary=True),
        ref("finding_revision_id"),
        ref("source_revision_id"),
    )
    sa.Table(
        "research_evidence_bindings",
        metadata,
        ref("evidence_revision_id", "evidence_revisions.id", primary=True),
        ref("subject_revision_id"),
    )
    protocols = sa.Table(
        "research_protocols",
        metadata,
        ref("revision_id", primary=True),
        ref("question_revision_id"),
    )
    sa.Index("ix_research_protocol_question", protocols.c.question_revision_id)
    assessments = sa.Table(
        "research_assessments",
        metadata,
        ref("revision_id", primary=True),
        ref("protocol_revision_id", "research_protocols.revision_id"),
        ref("question_revision_id"),
        sa.Column("input_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    sa.Index(
        "ix_research_assessment_question",
        assessments.c.question_revision_id,
        assessments.c.created_at,
    )
    dependencies = sa.Table(
        "assessment_dependencies",
        metadata,
        ref("assessment_revision_id", "research_assessments.revision_id", primary=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        ref("entity_revision_id", nullable=True),
        ref("evidence_revision_id", "evidence_revisions.id", nullable=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.CheckConstraint(
            "(entity_revision_id IS NOT NULL) != (evidence_revision_id IS NOT NULL)"
        ),
    )
    sa.Index("ix_assessment_entity_dependency", dependencies.c.entity_revision_id)
    sa.Index("ix_assessment_evidence_dependency", dependencies.c.evidence_revision_id)


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0010_memory import _metadata
    from socialdna.storage.migrations.versions.v0010_memory import extend_metadata as memory

    metadata = _metadata()
    memory(metadata)
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    _rebuild_evidence(metadata)
    for table in metadata.tables.values():
        if table.name not in baseline:
            table.create(op.get_bind())
            for operation in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER research_{table.name}_{operation.lower()} "
                    f"BEFORE {operation} ON {table.name} BEGIN "
                    "SELECT RAISE(ABORT,'immutable research history'); END"
                )


def downgrade() -> None:
    from socialdna.storage.migrations.versions.v0010_memory import _metadata
    from socialdna.storage.migrations.versions.v0010_memory import extend_metadata as memory

    prior = _metadata()
    memory(prior)
    current = sa.MetaData()
    for table in prior.tables.values():
        table.to_metadata(current)
    extend_metadata(current)
    added = [table for table in current.tables.values() if table.name not in prior.tables]
    if op.get_bind().scalar(
        sa.select(sa.exists().select_from(current.tables["entity_revisions"]))
    ) or any(op.get_bind().scalar(sa.select(sa.exists().select_from(table))) for table in added):
        raise RuntimeError("Refusing to discard research history; restore a verified backup")
    for table in reversed(added):
        table.drop(op.get_bind())
    _rebuild_evidence(prior)


def _rebuild_evidence(metadata: sa.MetaData) -> None:
    # As in earlier migrations, FK enforcement is suspended before BEGIN by the
    # migration runner and checked before COMMIT. Preserve the R6 journal as well
    # as immutable guards; do not sort the intentional R6 document FK cycle.
    triggers: list[str] = list(
        op.get_bind()
        .exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name='evidence_revisions'"
        )
        .scalars()
    )
    original = metadata.tables["evidence_revisions"]
    temporary = original.to_metadata(sa.MetaData(), name="evidence_revisions_new")
    for table in metadata.tables.values():
        if table.name != original.name:
            table.to_metadata(temporary.metadata)
    temporary.indexes.clear()
    temporary.create(op.get_bind())
    columns = ",".join(c.name for c in original.columns)
    op.execute(
        f"INSERT INTO evidence_revisions_new ({columns}) SELECT {columns} FROM evidence_revisions"
    )
    op.execute("DROP TABLE evidence_revisions")
    op.execute("ALTER TABLE evidence_revisions_new RENAME TO evidence_revisions")
    for index in original.indexes:
        index.create(op.get_bind())
    for trigger in triggers:
        op.execute(trigger)
