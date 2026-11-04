"""Versioned account exports and reproducible performance analyses.

Revision ID: 0004_analytics
Revises: 0003_enrichment
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_analytics"
down_revision = "0003_enrichment"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    def identifier() -> sa.Column[str]:
        return sa.Column("id", sa.String(36), primary_key=True)

    def text(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, nullable=False)

    def document(name: str) -> sa.Column[str]:
        return sa.Column(name, sa.Text, sa.CheckConstraint(f"json_valid({name})"), nullable=False)

    sa.Table(
        "import_batches",
        metadata,
        identifier(),
        text("dataset_id"),
        text("checksum"),
        sa.Column("source_id", sa.ForeignKey("source_records.id"), nullable=False),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        text("created_at"),
        document("counts_json"),
        sa.UniqueConstraint("dataset_id", "checksum"),
    )
    sa.Table(
        "media_references",
        metadata,
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("position", sa.Integer, primary_key=True),
        text("uri"),
        sa.Column("source_id", sa.ForeignKey("source_records.id"), nullable=False),
        sa.CheckConstraint("position >= 0"),
    )
    sa.Table(
        "tags",
        metadata,
        identifier(),
        text("kind"),
        text("normalized_value"),
        text("display_value"),
        sa.UniqueConstraint("kind", "normalized_value"),
        sa.CheckConstraint("kind IN ('hashtag','topic')"),
    )
    sa.Table(
        "post_tags",
        metadata,
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("tag_id", sa.ForeignKey("tags.id"), primary_key=True),
        text("source"),
    )
    sa.Table(
        "comments",
        metadata,
        identifier(),
        sa.Column("post_id", sa.ForeignKey("posts.id"), nullable=False),
        text("external_id"),
        text("body"),
        text("published_at"),
        sa.Column("parent_comment_id", sa.ForeignKey("comments.id")),
        sa.UniqueConstraint("post_id", "external_id"),
    )
    sa.Table(
        "metric_definitions",
        metadata,
        sa.Column("key", sa.Text, primary_key=True),
        text("platform"),
        text("subject_type"),
        text("unit"),
        text("measurement"),
        text("definition"),
        sa.CheckConstraint("subject_type IN ('post','account')"),
        sa.CheckConstraint("measurement IN ('cumulative','period')"),
        sa.CheckConstraint("unit IN ('count','seconds','ratio','percent')"),
    )
    observations = sa.Table(
        "metric_observations",
        metadata,
        identifier(),
        text("subject_type"),
        text("subject_id"),
        sa.Column("post_id", sa.ForeignKey("posts.id")),
        sa.Column("account_id", sa.ForeignKey("accounts.id")),
        sa.Column("metric_key", sa.ForeignKey("metric_definitions.key"), nullable=False),
        sa.Column("value", sa.Float),
        text("availability"),
        sa.Column("reason", sa.Text),
        text("observed_at"),
        sa.Column("window_start", sa.Text),
        sa.Column("window_end", sa.Text),
        sa.Column("post_age_seconds", sa.Float),
        text("dataset_id"),
        text("imported_at"),
        sa.Column("supersedes_id", sa.ForeignKey("metric_observations.id")),
        sa.Column("provenance_id", sa.ForeignKey("provenance_records.id"), nullable=False),
        sa.CheckConstraint(
            "(subject_type='post' AND post_id=subject_id AND account_id IS NULL) OR "
            "(subject_type='account' AND account_id=subject_id AND post_id IS NULL)"
        ),
        sa.CheckConstraint("post_id IS NOT NULL OR account_id IS NOT NULL"),
        sa.CheckConstraint("post_age_seconds IS NULL OR post_age_seconds >= 0"),
        sa.CheckConstraint(
            "(availability='available' AND value IS NOT NULL AND value >= 0) OR "
            "(availability IN "
            "('not_supplied','not_permitted','not_applicable','failed','unavailable') "
            "AND value IS NULL AND reason IS NOT NULL)"
        ),
        sa.CheckConstraint(
            "(window_start IS NULL AND window_end IS NULL) OR "
            "(window_start IS NOT NULL AND window_end IS NOT NULL AND "
            "window_start < window_end AND window_end <= observed_at)"
        ),
    )
    sa.Index(
        "ix_metrics_subject_key_age",
        observations.c.subject_id,
        observations.c.metric_key,
        observations.c.post_age_seconds,
    )
    sa.Table(
        "derived_metrics",
        metadata,
        identifier(),
        sa.Column("post_id", sa.ForeignKey("posts.id"), nullable=False),
        text("metric_key"),
        sa.Column("value", sa.Float),
        text("formula_version"),
        document("input_ids_json"),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id"), nullable=False),
    )
    sa.Table(
        "cohorts",
        metadata,
        identifier(),
        text("name"),
        document("population_spec_json"),
        sa.Column("created_by_run_id", sa.ForeignKey("analysis_runs.id"), nullable=False),
    )
    sa.Table(
        "cohort_members",
        metadata,
        sa.Column("cohort_id", sa.ForeignKey("cohorts.id"), primary_key=True),
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        text("role"),
        sa.Column("match_set_id", sa.Text),
        document("input_json"),
    )
    sa.Table(
        "statistical_analyses",
        metadata,
        identifier(),
        text("method"),
        document("spec_json"),
        text("outcome_key"),
        text("status"),
        document("result_json"),
        sa.Column("run_id", sa.ForeignKey("analysis_runs.id"), nullable=False, unique=True),
    )
    sa.Table(
        "statistical_results",
        metadata,
        identifier(),
        sa.Column("analysis_id", sa.ForeignKey("statistical_analyses.id"), nullable=False),
        text("term"),
        sa.Column("estimate", sa.Float),
        sa.Column("standard_error", sa.Float),
        sa.Column("ci_low", sa.Float),
        sa.Column("ci_high", sa.Float),
        sa.Column("p_value", sa.Float),
        sa.Column("adjusted_p_value", sa.Float),
        sa.Column("sample_count", sa.Integer, nullable=False),
        sa.Column("cluster_count", sa.Integer, nullable=False),
        document("diagnostics_json"),
    )
    sa.Table(
        "account_media_runs",
        metadata,
        sa.Column("account_run_id", sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("post_id", sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("position", sa.Integer, primary_key=True),
        sa.Column("media_run_id", sa.ForeignKey("analysis_runs.id")),
        text("status"),
        sa.Column("message", sa.Text),
    )


def _tables() -> list[sa.Table]:
    from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
    from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata as timeline
    from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment

    metadata = foundation_metadata()
    timeline(metadata)
    enrichment(metadata)
    baseline = set(metadata.tables)
    extend_metadata(metadata)
    return [table for table in metadata.sorted_tables if table.name not in baseline]


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind(), checkfirst=False)
    # Snapshots and definitions are immutable, including direct SQL writes.
    for name in ("metric_observations", "metric_definitions"):
        op.execute(
            f"CREATE TRIGGER {name}_immutable BEFORE UPDATE ON {name} "
            "BEGIN SELECT RAISE(ABORT, 'append-only metric history'); END"
        )


def downgrade() -> None:
    for table in reversed(_tables()):
        table.drop(op.get_bind(), checkfirst=False)
