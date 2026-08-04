"""add metadata identity and explainable decisions

Revision ID: 20260804_01
Revises: 20260801_01
"""

from alembic import op
import sqlalchemy as sa


revision: str = "20260804_01"
down_revision: str | None = "20260801_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_matches", sa.Column("metadata_provider", sa.String(32)))
    op.add_column("media_matches", sa.Column("provider_id", sa.String(128)))
    op.add_column(
        "media_matches",
        sa.Column("match_origin", sa.String(32), nullable=False, server_default="RULE"),
    )
    op.add_column(
        "media_matches",
        sa.Column("metadata_hint", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "media_matches",
        sa.Column("decision_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.execute(
        """
        UPDATE organize_jobs
        SET current_stage = '识别能力已升级，请重新扫描'
        WHERE status IN ('REVIEW_REQUIRED', 'READY', 'FAILED')
        """
    )


def downgrade() -> None:
    op.drop_column("media_matches", "decision_reasons")
    op.drop_column("media_matches", "metadata_hint")
    op.drop_column("media_matches", "match_origin")
    op.drop_column("media_matches", "provider_id")
    op.drop_column("media_matches", "metadata_provider")
