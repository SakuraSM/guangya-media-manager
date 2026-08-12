"""add persistent realtime job progress events

Revision ID: 20260812_02
Revises: 20260812_01
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_02"
down_revision: str | None = "20260812_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organize_jobs",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "organize_jobs",
        sa.Column(
            "progress_detail",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_table(
        "job_progress_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("organize_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False, server_default="JOB"),
        sa.Column("match_id", sa.String(36)),
        sa.Column("group_key", sa.String(512)),
        sa.Column("file_operation_id", sa.String(36)),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_progress_events_job_id", "job_progress_events", ["job_id"])
    op.create_index(
        "ix_job_progress_events_job_cursor",
        "job_progress_events",
        ["job_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_progress_events_job_cursor", table_name="job_progress_events")
    op.drop_index("ix_job_progress_events_job_id", table_name="job_progress_events")
    op.drop_table("job_progress_events")
    op.drop_column("organize_jobs", "progress_detail")
    op.drop_column("organize_jobs", "revision")
