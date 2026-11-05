"""Audience collections, reviewed reactions and retention lineage.

Revision ID: 0008_audience
Revises: 0007_creative
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_audience"
down_revision = "0007_creative"
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
            "'creative_event','creative_coverage','post_text','audience_record')"
        )
    )

    def text(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False)

    def ref(
        name: str, target: str, *, primary: bool = False, nullable: bool = False
    ) -> sa.Column[str]:
        return sa.Column(name, sa.ForeignKey(target), primary_key=primary, nullable=nullable)

    collections = sa.Table(
        "audience_collections",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        text("key"),
        text("available_at"),
    )
    sa.Index("ix_audience_collection_key_time", collections.c.key, collections.c.available_at)
    sa.Table(
        "audience_collection_members",
        metadata,
        ref("collection_revision_id", "audience_collections.revision_id", primary=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        ref("comment_revision_id", "entity_revisions.id"),
        sa.Column("eligible", sa.Boolean, nullable=False),
        sa.Column("language", sa.Text),
        sa.Column("creator_authored", sa.Boolean),
        sa.Column("exclusion_reason", sa.Text),
        sa.UniqueConstraint("collection_revision_id", "comment_revision_id"),
    )
    sets = sa.Table(
        "audience_annotation_sets",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        ref("collection_revision_id", "audience_collections.revision_id"),
        text("key"),
    )
    sa.Index("ix_audience_sets_collection_key", sets.c.collection_revision_id, sets.c.key)
    sa.Table(
        "reaction_annotations",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        ref("collection_revision_id", "audience_collections.revision_id"),
        ref("comment_revision_id", "entity_revisions.id"),
        ref("span_evidence_revision_id", "evidence_revisions.id"),
        text("state"),
    )
    sa.Table(
        "reaction_clusters",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        ref("collection_revision_id", "audience_collections.revision_id"),
        text("state"),
    )
    sa.Table(
        "reaction_cluster_members",
        metadata,
        ref("cluster_revision_id", "reaction_clusters.revision_id", primary=True),
        ref("reaction_revision_id", "reaction_annotations.revision_id", primary=True),
        text("role"),
        sa.CheckConstraint("role IN ('member','representative','counterexample')"),
    )
    sa.Table(
        "content_reaction_links",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        ref("collection_revision_id", "audience_collections.revision_id"),
        ref("reaction_revision_id", "reaction_annotations.revision_id"),
        ref("target_revision_id", "entity_revisions.id"),
        text("origin"),
        text("state"),
        sa.Column("playback_reference_ms", sa.Integer),
    )
    for plural, target in (
        ("reactions", "reaction_annotations"),
        ("clusters", "reaction_clusters"),
        ("links", "content_reaction_links"),
    ):
        sa.Table(
            "audience_set_" + plural,
            metadata,
            ref("set_revision_id", "audience_annotation_sets.revision_id", primary=True),
            ref("member_revision_id", target + ".revision_id"),
            sa.Column("ordinal", sa.Integer, primary_key=True),
            sa.UniqueConstraint("set_revision_id", "member_revision_id"),
        )
    sa.Table(
        "audience_analyses",
        metadata,
        ref("revision_id", "entity_revisions.id", primary=True),
        ref("collection_revision_id", "audience_collections.revision_id"),
        ref("set_revision_id", "audience_annotation_sets.revision_id", nullable=True),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id"), nullable=False, unique=True),
        sa.Column("fingerprint", sa.Text, nullable=False, unique=True),
    )
    sa.Table(
        "audience_evidence_bindings",
        metadata,
        ref("evidence_revision_id", "evidence_revisions.id", primary=True),
        ref("subject_revision_id", "entity_revisions.id"),
        ref("collection_revision_id", "audience_collections.revision_id"),
    )
    dependencies = sa.Table(
        "audience_dependencies",
        metadata,
        ref("parent_revision_id", "entity_revisions.id", primary=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        ref("entity_revision_id", "entity_revisions.id", nullable=True),
        ref("evidence_revision_id", "evidence_revisions.id", nullable=True),
        sa.CheckConstraint(
            "(entity_revision_id IS NOT NULL) != (evidence_revision_id IS NOT NULL)"
        ),
    )
    sa.Index("ix_audience_entity_dependents", dependencies.c.entity_revision_id)
    sa.Index("ix_audience_evidence_dependents", dependencies.c.evidence_revision_id)
    sa.Table(
        "audience_redactions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        text("scope_kind"),
        text("target_id"),
        text("reason"),
        text("actor"),
        text("requested_at"),
        text("plan_hash"),
        text("status"),
        sa.Column("completed_at", sa.Text),
        sa.CheckConstraint("scope_kind IN ('comment','source')"),
        sa.CheckConstraint("status IN ('pending','complete')"),
    )
    sa.Table(
        "audience_tombstones",
        metadata,
        text("target_kind"),
        text("target_id"),
        ref("operation_id", "audience_redactions.id"),
        sa.PrimaryKeyConstraint("target_kind", "target_id"),
        sa.CheckConstraint(
            "target_kind IN ('comment','source','entity_revision','evidence_revision',"
            "'artifact','statistical_analysis')"
        ),
    )


def _metadata() -> sa.MetaData:
    from socialdna.storage.migrations.versions.v0007_creative import _metadata, extend_metadata

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
        if table.name == "audience_redactions":
            continue  # Authorized pending -> complete operational journal, not research content.
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER audience_{table.name}_{operation.lower()} BEFORE {operation} "
                f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable audience history'); END"
            )


def downgrade() -> None:
    from socialdna.storage.migrations.versions.v0006_designs import _rebuild_evidence

    metadata = _metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    if op.get_bind().scalar(
        sa.select(sa.exists().select_from(metadata.tables["entity_revisions"]))
    ):
        raise RuntimeError("Refusing to discard audience history; restore a verified backup")
    for table in reversed(metadata.sorted_tables):
        if table.name not in baseline:
            if op.get_bind().scalar(sa.select(sa.exists().select_from(table))):
                raise RuntimeError(
                    "Refusing to discard audience history; restore a verified backup"
                )
            table.drop(op.get_bind())
    _rebuild_evidence(_metadata())
