"""Canonical foundation.

Revision ID: 0001_foundation
Revises: None

This schema is frozen with this revision. Later revisions must not mutate it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def foundation_metadata() -> sa.MetaData:
    metadata = sa.MetaData()

    def identifier() -> sa.Column[str]:
        return sa.Column("id", sa.String(36), primary_key=True)

    def json_column(name: str, default: str = "{}") -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False, server_default=default)

    def json_valid(*names: str) -> sa.CheckConstraint:
        return sa.CheckConstraint(" AND ".join(f"json_valid({name})" for name in names))

    sa.Table(
        "migration_checksums",
        metadata,
        sa.Column("revision", sa.String(64), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("applied_at", sa.Text, nullable=False),
    )
    sa.Table(
        "artifact_objects",
        metadata,
        identifier(),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("relative_path", sa.Text, nullable=False, unique=True),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("byte_size >= 0"),
        sa.CheckConstraint("length(sha256) = 64"),
    )
    sa.Table(
        "artifact_references",
        metadata,
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id"), primary_key=True),
        sa.Column("owner_type", sa.Text, primary_key=True),
        sa.Column("owner_id", sa.String(36), primary_key=True),
        sa.Column("role", sa.Text, primary_key=True),
    )
    sa.Table(
        "source_records",
        metadata,
        identifier(),
        sa.Column("source_kind", sa.Text, nullable=False),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("permission_basis", sa.Text, nullable=False),
        json_column("terms_json"),
        sa.Column("retrieved_at", sa.Text, nullable=False),
        sa.Column("raw_artifact_id", sa.ForeignKey("artifact_objects.id")),
        sa.Column("content_hash", sa.String(64)),
        json_valid("terms_json"),
    )
    sa.Table(
        "provenance_records",
        metadata,
        identifier(),
        sa.Column("source_record_id", sa.ForeignKey("source_records.id")),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("tool_name", sa.Text),
        sa.Column("tool_version", sa.Text),
        sa.Column("provider_name", sa.Text),
        sa.Column("model_name", sa.Text),
        sa.Column("model_revision", sa.Text),
        sa.Column("prompt_hash", sa.String(64)),
        json_column("config_json"),
        sa.Column("created_at", sa.Text, nullable=False),
        json_valid("config_json"),
    )
    sa.Table(
        "provenance_links",
        metadata,
        sa.Column("entity_type", sa.Text, primary_key=True),
        sa.Column("entity_id", sa.String(36), primary_key=True),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), primary_key=True),
        sa.Column("role", sa.Text, primary_key=True),
    )
    sa.Table(
        "data_availability",
        metadata,
        sa.Column("subject_type", sa.Text, primary_key=True),
        sa.Column("subject_id", sa.String(36), primary_key=True),
        sa.Column("field_key", sa.Text, primary_key=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("observed_at", sa.Text, nullable=False),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id")),
        sa.CheckConstraint(
            "status IN ('not_supplied','not_permitted','not_applicable','failed','unavailable')"
        ),
    )
    sa.Table(
        "creators",
        metadata,
        identifier(),
        sa.Column("display_name", sa.Text),
    )
    sa.Table(
        "accounts",
        metadata,
        identifier(),
        sa.Column("creator_id", sa.ForeignKey("creators.id")),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text),
        sa.Column("handle", sa.Text),
        sa.Column("niche", sa.Text),
        json_column("profile_json"),
        sa.UniqueConstraint("platform", "external_id"),
        json_valid("profile_json"),
    )
    posts = sa.Table(
        "posts",
        metadata,
        identifier(),
        sa.Column("account_id", sa.ForeignKey("accounts.id")),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text),
        sa.Column("content_type", sa.Text, nullable=False),
        sa.Column("published_at", sa.Text),
        sa.Column("source_timezone", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("caption", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.UniqueConstraint("platform", "external_id"),
    )
    sa.Index("ix_posts_account_published", posts.c.account_id, posts.c.published_at)
    sa.Table(
        "media_assets",
        metadata,
        identifier(),
        sa.Column("sha256", sa.String(64), unique=True),
        sa.Column("media_type", sa.Text, nullable=False),
        sa.Column("original_uri", sa.Text),
        sa.Column("managed_uri", sa.Text),
        sa.Column("duration_ms", sa.BigInteger),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        json_column("streams_json", "[]"),
        sa.Column("artifact_id", sa.ForeignKey("artifact_objects.id")),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0"),
        sa.CheckConstraint("width IS NULL OR width > 0"),
        sa.CheckConstraint("height IS NULL OR height > 0"),
        json_valid("streams_json"),
    )
    sa.Table(
        "post_media",
        metadata,
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("position", sa.Integer, primary_key=True),
        sa.Column("media_asset_id", sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.CheckConstraint("position >= 0"),
    )
    runs = sa.Table(
        "analysis_runs",
        metadata,
        identifier(),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("depth", sa.Text, nullable=False),
        sa.Column("profile_version", sa.Text, nullable=False),
        json_column("config_json"),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("started_at", sa.Text),
        sa.Column("finished_at", sa.Text),
        json_valid("config_json"),
        sa.CheckConstraint("depth IN ('quick','standard','deep')"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped','stale','cancelled')"
        ),
    )
    sa.Index("ix_runs_target_created", runs.c.target_type, runs.c.target_id, runs.c.created_at)
    tasks = sa.Table(
        "analysis_tasks",
        metadata,
        identifier(),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("task_key", sa.Text, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("analyzer", sa.Text, nullable=False),
        sa.Column("analyzer_version", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.Text),
        sa.Column("lease_expires_at", sa.Text),
        sa.Column("reused_from_task_id", sa.ForeignKey("analysis_tasks.id")),
        json_column("error_json"),
        sa.UniqueConstraint("run_id", "task_key"),
        json_valid("error_json"),
        sa.CheckConstraint("attempt_count >= 0"),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','skipped','stale','cancelled')"
        ),
    )
    sa.Index("ix_tasks_fingerprint_status", tasks.c.fingerprint, tasks.c.status)
    sa.Index("ix_tasks_lease", tasks.c.status, tasks.c.lease_expires_at)
    return metadata


def upgrade() -> None:
    foundation_metadata().create_all(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    foundation_metadata().drop_all(op.get_bind(), checkfirst=False)
