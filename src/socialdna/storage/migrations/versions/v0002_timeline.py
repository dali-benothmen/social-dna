"""Versioned deterministic timeline, evidence and task results.

Revision ID: 0002_timeline
Revises: 0001_foundation
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import SchemaItem

revision = "0002_timeline"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    def identifier() -> sa.Column[str]:
        return sa.Column("id", sa.String(36), primary_key=True)

    def media() -> sa.Column[str]:
        return sa.Column("media_asset_id", sa.ForeignKey("media_assets.id"), nullable=False)

    def task() -> sa.Column[str]:
        return sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), nullable=False)

    def interval() -> list[SchemaItem]:
        return [
            sa.Column("start_ms", sa.Integer, nullable=False),
            sa.Column("end_ms", sa.Integer, nullable=False),
            sa.CheckConstraint("start_ms >= 0 AND end_ms > start_ms"),
        ]

    sa.Table(
        "media_locations",
        metadata,
        media(),
        sa.Column("local_path", sa.Text, primary_key=True),
        sa.Column("source_record_id", sa.ForeignKey("source_records.id"), nullable=False),
    )
    sa.Table(
        "media_probes",
        metadata,
        sa.Column("media_asset_id", sa.ForeignKey("media_assets.id"), primary_key=True),
        sa.Column("probe_json", sa.Text, nullable=False),
        sa.Column("tool_version", sa.Text, nullable=False),
        sa.CheckConstraint("json_valid(probe_json)"),
    )
    sa.Table(
        "analysis_task_results",
        metadata,
        sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), primary_key=True),
        sa.Column("result_json", sa.Text, nullable=False),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        sa.CheckConstraint("json_valid(result_json)"),
    )
    sa.Table(
        "analysis_task_dependencies",
        metadata,
        sa.Column("task_id", sa.ForeignKey("analysis_tasks.id"), primary_key=True),
        sa.Column("depends_on_id", sa.ForeignKey("analysis_tasks.id"), primary_key=True),
    )
    sa.Table(
        "scenes",
        metadata,
        identifier(),
        media(),
        task(),
        sa.Column("ordinal", sa.Integer, nullable=False),
        *interval(),
        sa.Column("detector", sa.Text, nullable=False),
        sa.UniqueConstraint("task_id", "ordinal"),
    )
    sa.Table(
        "frames",
        metadata,
        identifier(),
        media(),
        task(),
        sa.Column("timestamp_ms", sa.Integer, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("selection_reason", sa.Text, nullable=False),
        sa.Column("perceptual_hash", sa.Text, nullable=False),
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id"), nullable=False),
        sa.UniqueConstraint("task_id", "ordinal"),
        sa.CheckConstraint("timestamp_ms >= 0"),
    )
    sa.Table(
        "text_tracks",
        metadata,
        identifier(),
        media(),
        task(),
        sa.Column("track_type", sa.Text, nullable=False),
        sa.Column("language", sa.Text),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False),
    )
    sa.Table(
        "text_segments",
        metadata,
        identifier(),
        sa.Column("track_id", sa.ForeignKey("text_tracks.id"), nullable=False),
        *interval(),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float),
    )
    sa.Table(
        "audio_segments",
        metadata,
        identifier(),
        media(),
        task(),
        *interval(),
        sa.Column("segment_type", sa.Text, nullable=False),
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id")),
    )
    sa.Table(
        "feature_definitions",
        metadata,
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("modality", sa.Text, nullable=False),
        sa.Column("value_kind", sa.Text, nullable=False),
        sa.Column("unit", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("schema_version", sa.Text, nullable=False),
    )
    sa.Table(
        "observations",
        metadata,
        identifier(),
        media(),
        task(),
        sa.Column("feature_key", sa.ForeignKey("feature_definitions.key"), nullable=False),
        sa.Column("numeric_value", sa.Float),
        sa.Column("json_value", sa.Text),
        *interval(),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        sa.CheckConstraint("(numeric_value IS NOT NULL) != (json_value IS NOT NULL)"),
        sa.CheckConstraint("json_value IS NULL OR json_valid(json_value)"),
    )
    sa.Table(
        "evidence_items",
        metadata,
        identifier(),
        media(),
        task(),
        *interval(),
        sa.Column("subject_type", sa.Text, nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id")),
        sa.Column("excerpt", sa.Text),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
    )
    sa.Table(
        "reports",
        metadata,
        identifier(),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("format", sa.Text, nullable=False),
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id"), nullable=False),
        sa.Column("schema_version", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.UniqueConstraint("run_id", "format"),
    )
    for name in ("scenes", "audio_segments", "observations", "evidence_items"):
        table = metadata.tables[name]
        sa.Index(
            f"ix_{name}_media_interval", table.c.media_asset_id, table.c.start_ms, table.c.end_ms
        )
        sa.Index(f"ix_{name}_task", table.c.task_id)
    sa.Index(
        "ix_frames_media_time",
        metadata.tables["frames"].c.media_asset_id,
        metadata.tables["frames"].c.timestamp_ms,
    )
    sa.Index(
        "ix_text_segments_track_interval",
        metadata.tables["text_segments"].c.track_id,
        metadata.tables["text_segments"].c.start_ms,
        metadata.tables["text_segments"].c.end_ms,
    )
    sa.Index(
        "ix_observations_feature_value",
        metadata.tables["observations"].c.feature_key,
        metadata.tables["observations"].c.numeric_value,
    )


def _tables() -> list[sa.Table]:
    from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata

    metadata = foundation_metadata()
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    return [table for table in metadata.sorted_tables if table.name not in baseline]


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(_tables()):
        table.drop(op.get_bind(), checkfirst=False)
