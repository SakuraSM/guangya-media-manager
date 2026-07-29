"""Add directory-aware media hierarchy and source classification.

Revision ID: 20260729_01
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision: str = "20260729_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_ITEM_COLUMNS = (
    sa.Column("relative_path", sa.String(length=1024), nullable=False, server_default=""),
    sa.Column(
        "classification",
        sa.String(length=32),
        nullable=False,
        server_default="UNKNOWN",
    ),
    sa.Column("filter_reason", sa.String(length=64), nullable=False, server_default=""),
    sa.Column(
        "user_action",
        sa.String(length=16),
        nullable=False,
        server_default="DEFAULT",
    ),
    sa.Column("group_key", sa.String(length=512), nullable=False, server_default=""),
)

MEDIA_MATCH_COLUMNS = (
    sa.Column("group_key", sa.String(length=512), nullable=False, server_default=""),
    sa.Column("episode_title", sa.String(length=256), nullable=False, server_default=""),
    sa.Column("episode_date", sa.String(length=10), nullable=True),
    sa.Column("release_info", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
)


def upgrade() -> None:
    connection = op.get_bind()
    Base.metadata.create_all(connection)
    inspector = sa.inspect(connection)
    _add_missing_columns(inspector, "source_items", SOURCE_ITEM_COLUMNS)
    inspector = sa.inspect(connection)
    _add_missing_columns(inspector, "media_matches", MEDIA_MATCH_COLUMNS)
    connection.execute(
        sa.text(
            """
            UPDATE organize_jobs
            SET status = 'FAILED',
                current_stage = '需要重新扫描',
                error_message = '媒体识别模型已升级，请重新扫描任务'
            WHERE status IN (
                'DRAFT', 'SCANNING', 'IDENTIFYING', 'REVIEW_REQUIRED', 'READY',
                'COPYING', 'SCRAPING', 'FINALIZING'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("media_match_episodes")
    op.drop_table("media_episodes")
    op.drop_table("media_seasons")
    for column in reversed(MEDIA_MATCH_COLUMNS):
        op.drop_column("media_matches", column.name)
    for column in reversed(SOURCE_ITEM_COLUMNS):
        op.drop_column("source_items", column.name)


def _add_missing_columns(
    inspector: sa.Inspector,
    table_name: str,
    columns: tuple[sa.Column[object], ...],
) -> None:
    existing_names = {column["name"] for column in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in existing_names:
            op.add_column(table_name, column)
