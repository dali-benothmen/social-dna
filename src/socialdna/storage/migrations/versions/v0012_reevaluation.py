"""Incremental selection watches, resumable requests and immutable assessment lineage.

Revision ID: 0012_reevaluation
Revises: 0011_research
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_reevaluation"
down_revision = "0011_research"
branch_labels = None
depends_on = None


def extend_metadata(metadata: sa.MetaData) -> None:
    sa.Table(
        "research_changes",
        metadata,
        sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
        sa.Column(
            "captured_at",
            sa.Text,
            nullable=False,
            server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z')"),
        ),
        sa.UniqueConstraint("kind", "target_id"),
        sqlite_autoincrement=True,
    )
    sa.Table(
        "assessment_watches",
        metadata,
        sa.Column(
            "assessment_revision_id",
            sa.ForeignKey("research_assessments.revision_id"),
            primary_key=True,
        ),
        sa.Column("manifest_json", sa.Text, nullable=False),
        sa.Column("baseline_seq", sa.Integer, nullable=False),
        sa.Column("cursor", sa.Integer, nullable=False),
        sa.Column("tokens_json", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("reasons_json", sa.Text, nullable=False),
        sa.CheckConstraint("state IN ('current','stale','superseded')"),
    )
    sa.Table(
        "reevaluation_requests",
        metadata,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "previous_revision_id",
            sa.ForeignKey("research_assessments.revision_id"),
            nullable=False,
        ),
        sa.Column("plan_json", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("progress_json", sa.Text, nullable=False),
        sa.Column("result_revision_id", sa.ForeignKey("research_assessments.revision_id")),
        sa.Column("error_type", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("status IN ('pending','running','failed','completed')"),
    )
    transitions = sa.Table(
        "assessment_transitions",
        metadata,
        sa.Column("request_id", sa.ForeignKey("reevaluation_requests.id"), primary_key=True),
        sa.Column(
            "previous_revision_id",
            sa.ForeignKey("research_assessments.revision_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "next_revision_id",
            sa.ForeignKey("research_assessments.revision_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("previous_revision_id != next_revision_id"),
    )
    sa.Index("ix_reevaluation_previous", transitions.c.previous_revision_id)


def upgrade() -> None:
    from socialdna.storage.migrations.versions.v0010_memory import _metadata
    from socialdna.storage.migrations.versions.v0010_memory import extend_metadata as memory
    from socialdna.storage.migrations.versions.v0011_research import extend_metadata as research

    metadata = _metadata()
    memory(metadata)
    research(metadata)
    extend_metadata(metadata)

    for name in (
        "research_changes",
        "assessment_watches",
        "reevaluation_requests",
        "assessment_transitions",
    ):
        metadata.tables[name].create(op.get_bind())
    # Reconstruct pre-upgrade canonical event order even if R6's queue was
    # drained. The durable copy has its own monotonic sequence and deduplicates
    # immutable identities, so an index rebuild cannot invent new evidence.
    op.execute(
        "INSERT OR IGNORE INTO research_changes(kind,target_id,captured_at) "
        "SELECT kind,target_id,at FROM ("
        "SELECT 'entity' AS kind,id AS target_id,recorded_at AS at FROM entity_revisions "
        "UNION ALL SELECT 'evidence',id,captured_at FROM evidence_revisions "
        "UNION ALL SELECT 'eligibility',id,created_at FROM evidence_withdrawals "
        "UNION ALL SELECT 'association',id,available_at FROM post_media_versions "
        "UNION ALL SELECT 'model_run',id,coalesce(finished_at,started_at,created_at) "
        "FROM analysis_runs "
        "WHERE target_type='media' AND status='succeeded') ORDER BY at,kind,target_id"
    )
    op.execute(
        "INSERT OR IGNORE INTO research_changes(kind,target_id) "
        "SELECT 'eligibility',target_id FROM audience_tombstones"
    )
    op.execute(
        "CREATE TRIGGER research_change_capture AFTER INSERT ON memory_changes BEGIN "
        "INSERT OR IGNORE INTO research_changes(kind,target_id) "
        "VALUES (NEW.kind,NEW.target_id); END"
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER research_change_{operation.lower()} BEFORE {operation} "
            "ON research_changes BEGIN SELECT RAISE(ABORT,'immutable research journal'); END"
        )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER lineage_{operation.lower()} BEFORE {operation} "
            "ON assessment_transitions BEGIN "
            "SELECT RAISE(ABORT,'immutable assessment history'); END"
        )
    for name in ("reevaluation_requests", "assessment_watches"):
        op.execute(
            f"CREATE TRIGGER {name}_delete BEFORE DELETE ON {name} BEGIN "
            "SELECT RAISE(ABORT,'preserved research history'); END"
        )
    op.execute(
        "CREATE TRIGGER watch_manifest_immutable BEFORE UPDATE ON assessment_watches "
        "WHEN NEW.manifest_json != OLD.manifest_json OR NEW.baseline_seq != OLD.baseline_seq "
        "BEGIN SELECT RAISE(ABORT,'immutable selection manifest'); END"
    )
    op.execute(
        "CREATE TRIGGER request_plan_immutable BEFORE UPDATE ON reevaluation_requests "
        "WHEN NEW.plan_json != OLD.plan_json "
        "OR NEW.previous_revision_id != OLD.previous_revision_id "
        "OR OLD.status = 'completed' BEGIN SELECT RAISE(ABORT,'immutable reevaluation plan'); END"
    )
    # Existing canonical inserts already enter the R6 durable journal. These two
    # producers did not, and can alter feature lineage without changing a post.
    op.execute(
        "CREATE TRIGGER research_media_association AFTER INSERT ON post_media_versions BEGIN "
        "INSERT INTO memory_changes(kind,target_id) VALUES ('association',NEW.id); END"
    )
    op.execute(
        "CREATE TRIGGER research_media_completion AFTER UPDATE ON analysis_runs "
        "WHEN NEW.target_type = 'media' AND NEW.status = 'succeeded' AND OLD.status != NEW.status "
        "BEGIN INSERT INTO memory_changes(kind,target_id) VALUES ('model_run',NEW.id); END"
    )


def downgrade() -> None:
    if op.get_bind().exec_driver_sql("SELECT 1 FROM assessment_watches LIMIT 1").first():
        raise RuntimeError("Refusing to discard assessment history; restore a verified backup")
    for trigger in (
        "research_media_association",
        "research_media_completion",
        "research_change_capture",
    ):
        op.execute(f"DROP TRIGGER {trigger}")
    for name in (
        "assessment_transitions",
        "reevaluation_requests",
        "assessment_watches",
        "research_changes",
    ):
        op.execute(f"DROP TABLE {name}")
