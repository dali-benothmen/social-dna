"""Local model enrichment. Milestone 2 memory tables remain deferred.

Revision ID: 0003_enrichment
Revises: 0002_timeline
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_enrichment"
down_revision = "0002_timeline"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    sa.Table(
        "text_words",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("segment_id", sa.ForeignKey("text_segments.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("start_ms", sa.Integer),
        sa.Column("end_ms", sa.Integer),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.UniqueConstraint("segment_id", "ordinal"),
        sa.CheckConstraint(
            "(start_ms IS NULL AND end_ms IS NULL) OR "
            "(start_ms IS NOT NULL AND end_ms IS NOT NULL AND "
            "start_ms >= 0 AND end_ms > start_ms)"
        ),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
    )
    sa.Table(
        "ocr_boxes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("text_segment_id", sa.ForeignKey("text_segments.id"), nullable=False),
        sa.Column("frame_id", sa.ForeignKey("frames.id"), nullable=False),
        sa.Column("points_json", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.CheckConstraint("json_valid(points_json)"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1"),
    )
    sa.Table(
        "inference_inputs",
        metadata,
        sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), primary_key=True),
        sa.Column("evidence_id", sa.ForeignKey("evidence_items.id"), primary_key=True),
    )
    sa.Table(
        "provider_calls",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), nullable=False),
        sa.Column("identity_json", sa.Text, nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("request_artifact_id", sa.ForeignKey("artifact_objects.id"), nullable=False),
        sa.Column("response_artifact_id", sa.ForeignKey("artifact_objects.id")),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("json_valid(identity_json)"),
        sa.CheckConstraint("status IN ('attempted','succeeded','failed')"),
    )
    sa.Index("ix_ocr_boxes_frame", metadata.tables["ocr_boxes"].c.frame_id)
    sa.Index("ix_provider_calls_task", metadata.tables["provider_calls"].c.task_id)


def _tables() -> list[sa.Table]:
    from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
    from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata as timeline

    metadata = foundation_metadata()
    timeline(metadata)
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    return [table for table in metadata.sorted_tables if table.name not in baseline]


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(_tables()):
        table.drop(op.get_bind(), checkfirst=False)
