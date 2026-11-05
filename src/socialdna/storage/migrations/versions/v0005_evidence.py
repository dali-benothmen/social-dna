"""Universal revisioned evidence and draft research registration.

Revision ID: 0005_evidence
Revises: 0004_analytics

Legacy rows remain authoritative for their original observations. This additive
slice freezes captured payloads and attaches typed source bindings.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_evidence"
down_revision = "0004_analytics"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    def text(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False)

    def document(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, sa.CheckConstraint(f"json_valid({name})"), nullable=False)

    sa.Table(
        "entity_identities",
        metadata,
        sa.Column("kind", sa.Text, primary_key=True),
        sa.Column("entity_id", sa.Text, primary_key=True),
        text("created_at"),
    )
    revisions = sa.Table(
        "entity_revisions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        text("kind"),
        text("entity_id"),
        sa.Column("revision_no", sa.Integer, nullable=False),
        text("schema_version"),
        text("content_hash"),
        document("payload_json"),
        text("recorded_at"),
        sa.Column("available_at", sa.Text),
        text("capture_mode"),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        sa.Column("source_id", sa.ForeignKey("source_records.id")),
        sa.ForeignKeyConstraint(
            ["kind", "entity_id"], ["entity_identities.kind", "entity_identities.entity_id"]
        ),
        sa.UniqueConstraint("kind", "entity_id", "revision_no"),
        sa.CheckConstraint("revision_no > 0 AND length(content_hash)=64"),
        sa.CheckConstraint("capture_mode IN ('source_capture','legacy_capture','authored')"),
    )
    sa.Index("ix_entity_revisions_identity", revisions.c.kind, revisions.c.entity_id)
    bindings = [
        ("account", "accounts", "id"),
        ("post", "posts", "id"),
        ("media", "media_assets", "id"),
        ("comment", "comments", "id"),
        ("metric_snapshot", "metric_observations", "id"),
        ("metric_definition", "metric_definitions", "key"),
        ("frame", "frames", "id"),
        ("scene", "scenes", "id"),
        ("observation", "observations", "id"),
        ("text_segment", "text_segments", "id"),
        ("audio_segment", "audio_segments", "id"),
        ("ocr_box", "ocr_boxes", "id"),
    ]
    sa.Table(
        "legacy_entity_bindings",
        metadata,
        sa.Column("revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        *(
            sa.Column(kind + "_id", sa.ForeignKey(f"{table}.{key}"))
            for kind, table, key in bindings
        ),
        sa.CheckConstraint(
            " + ".join(f"({kind}_id IS NOT NULL)" for kind, _, _ in bindings) + " = 1"
        ),
    )
    sa.Table(
        "evidence_records", metadata, sa.Column("id", sa.Text, primary_key=True), text("created_at")
    )
    evidence = sa.Table(
        "evidence_revisions",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("evidence_id", sa.ForeignKey("evidence_records.id"), nullable=False),
        sa.Column("subject_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        text("locator_kind"),
        text("schema_version"),
        document("locator_json"),
        text("content_hash"),
        text("captured_at"),
        sa.Column("available_at", sa.Text),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        sa.Column("source_id", sa.ForeignKey("source_records.id")),
        sa.Column("producer_run_id", sa.ForeignKey("analysis_runs.id")),
        sa.Column("producer_task_id", sa.ForeignKey("analysis_tasks.id")),
        sa.UniqueConstraint("evidence_id", "content_hash"),
        sa.CheckConstraint("locator_kind IN ('media_span','comment_span','metric_snapshot')"),
        sa.CheckConstraint("length(content_hash)=64"),
    )
    sa.Index("ix_evidence_revisions_subject", evidence.c.subject_revision_id)
    sa.Index("ix_evidence_revisions_identity", evidence.c.evidence_id)
    sa.Table(
        "legacy_media_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column(
            "legacy_evidence_id", sa.ForeignKey("evidence_items.id"), nullable=False, unique=True
        ),
        sa.Column("media_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
    )
    sa.Table(
        "comment_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("comment_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
        sa.Column("comment_id", sa.ForeignKey("comments.id"), nullable=False),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.CheckConstraint("start_char >= 0 AND end_char > start_char"),
    )
    sa.Table(
        "metric_evidence_bindings",
        metadata,
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("metric_observation_id", sa.ForeignKey("metric_observations.id"), nullable=False),
        sa.Column("definition_revision_id", sa.ForeignKey("entity_revisions.id"), nullable=False),
    )
    sa.Table(
        "evidence_aliases",
        metadata,
        sa.Column("alias", sa.Text, primary_key=True),
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), nullable=False),
    )
    sa.Table(
        "evidence_links",
        metadata,
        sa.Column("owner_revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.Column("evidence_revision_id", sa.ForeignKey("evidence_revisions.id"), primary_key=True),
        sa.Column("role", sa.Text, primary_key=True),
        sa.Column("scope_revision_id", sa.ForeignKey("entity_revisions.id"), primary_key=True),
        sa.CheckConstraint(
            "role IN ('observed','supporting','contradicting','alternative',"
            "'context','excluded','non_discriminating')"
        ),
    )
    sa.Table(
        "evidence_withdrawals",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        # Privacy tombstones may name a post-checkpoint source absent from a
        # restored backup. Normal withdrawal writers still validate existence.
        sa.Column("source_id", sa.Text, unique=True),
        sa.Column("evidence_id", sa.Text, unique=True),
        text("reason"),
        text("actor"),
        text("created_at"),
        sa.CheckConstraint("(source_id IS NOT NULL) != (evidence_id IS NOT NULL)"),
        sa.CheckConstraint("length(trim(reason)) > 0 AND length(trim(actor)) > 0"),
    )
    sa.Table(
        "evidence_backfill",
        metadata,
        sa.Column("kind", sa.Text, primary_key=True),
        text("last_id"),
        text("status"),
        sa.CheckConstraint("status IN ('pending','complete')"),
    )


def _tables() -> list[sa.Table]:
    from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
    from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata as timeline
    from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment
    from socialdna.storage.migrations.versions.v0004_analytics import extend_metadata as analytics

    metadata = foundation_metadata()
    timeline(metadata)
    enrichment(metadata)
    analytics(metadata)
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    return [table for table in metadata.sorted_tables if table.name not in baseline]


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind(), checkfirst=False)
    for name in (
        "entity_revisions",
        "legacy_entity_bindings",
        "evidence_records",
        "evidence_revisions",
        "legacy_media_evidence_bindings",
        "comment_evidence_bindings",
        "metric_evidence_bindings",
        "evidence_aliases",
        "evidence_links",
        "evidence_withdrawals",
        "evidence_items",
    ):
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER r1_{name}_{operation.lower()} BEFORE {operation} ON {name} "
                "BEGIN SELECT RAISE(ABORT, 'immutable evidence history'); END"
            )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.exec_driver_sql(
        "SELECT EXISTS(SELECT 1 FROM entity_revisions) "
        "OR EXISTS(SELECT 1 FROM evidence_withdrawals)"
    ).scalar():
        raise RuntimeError(
            "Refusing to discard research/evidence history; restore a verified backup separately"
        )
    for operation in ("update", "delete"):
        op.execute(f"DROP TRIGGER r1_evidence_items_{operation}")
    for table in reversed(_tables()):
        table.drop(op.get_bind(), checkfirst=False)
