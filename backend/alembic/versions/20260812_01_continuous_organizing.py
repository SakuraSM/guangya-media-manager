"""add continuous organizing, classification and quality decisions

Revision ID: 20260812_01
Revises: 20260804_01
"""

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_01"
down_revision: str | None = "20260804_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organize_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_directory_id", sa.String(128), nullable=False),
        sa.Column("source_directory_path", sa.String(512), nullable=False),
        sa.Column("target_directory_id", sa.String(128), nullable=False),
        sa.Column("target_directory_path", sa.String(512), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("schedule_type", sa.String(24), nullable=False, server_default="MANUAL"),
        sa.Column("interval_minutes", sa.Integer()),
        sa.Column("cron_expression", sa.String(64)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_job_id", sa.String(36)),
        sa.Column("last_error", sa.Text()),
        sa.Column("retry_limit", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_backoff_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "directory_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("organize_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cloud_directory_id", sa.String(128), nullable=False),
        sa.Column("directory_path", sa.String(1024), nullable=False),
        sa.Column("child_signature", sa.String(64), nullable=False),
        sa.Column("child_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_id", "cloud_directory_id", name="uq_rule_directory_snapshot"),
    )
    op.create_index("ix_directory_snapshots_rule_id", "directory_snapshots", ["rule_id"])
    op.create_table(
        "rule_source_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("organize_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cloud_file_id", sa.String(128), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("fingerprint", sa.String(128)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_id", "cloud_file_id", name="uq_rule_source_item"),
    )
    op.create_index("ix_rule_source_items_rule_id", "rule_source_items", ["rule_id"])

    op.add_column("organize_jobs", sa.Column("rule_id", sa.String(36)))
    op.create_foreign_key(
        "fk_organize_jobs_rule_id",
        "organize_jobs",
        "organize_rules",
        ["rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("organize_jobs", sa.Column("trigger_type", sa.String(24), nullable=False, server_default="MANUAL"))
    op.add_column("organize_jobs", sa.Column("scanned_directories", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organize_jobs", sa.Column("skipped_directories", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organize_jobs", sa.Column("changed_items", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("media_matches", sa.Column("library_category", sa.String(24), nullable=False, server_default="MOVIE"))
    op.add_column("media_matches", sa.Column("region_bucket", sa.String(24), nullable=False, server_default="OTHER"))
    op.add_column("media_matches", sa.Column("classification_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("media_matches", sa.Column("quality_profile", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("media_matches", sa.Column("version_group_key", sa.String(512), nullable=False, server_default=""))
    op.add_column("media_matches", sa.Column("version_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("media_matches", sa.Column("version_recommendation", sa.String(24), nullable=False, server_default="SINGLE"))
    op.execute(
        "UPDATE media_matches SET library_category = 'TV' WHERE media_type = 'TV'"
    )


def downgrade() -> None:
    for column in (
        "version_recommendation",
        "version_score",
        "version_group_key",
        "quality_profile",
        "classification_reasons",
        "region_bucket",
        "library_category",
    ):
        op.drop_column("media_matches", column)
    op.drop_constraint("fk_organize_jobs_rule_id", "organize_jobs", type_="foreignkey")
    for column in ("changed_items", "skipped_directories", "scanned_directories", "trigger_type", "rule_id"):
        op.drop_column("organize_jobs", column)
    op.drop_index("ix_rule_source_items_rule_id", table_name="rule_source_items")
    op.drop_table("rule_source_items")
    op.drop_index("ix_directory_snapshots_rule_id", table_name="directory_snapshots")
    op.drop_table("directory_snapshots")
    op.drop_table("organize_rules")
