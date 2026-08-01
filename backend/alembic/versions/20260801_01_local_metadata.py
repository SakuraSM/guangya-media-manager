"""allow local metadata when TMDB has no record

Revision ID: 20260801_01
Revises: 20260729_01
"""

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_01"
down_revision: str | None = "20260729_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_entities",
        sa.Column("metadata_source", sa.String(length=16), nullable=False, server_default="TMDB"),
    )
    op.add_column("media_entities", sa.Column("provider_id", sa.String(length=128)))
    op.add_column("media_entities", sa.Column("local_key", sa.String(length=64)))
    op.execute("UPDATE media_entities SET provider_id = CAST(tmdb_id AS VARCHAR)")
    op.alter_column("media_entities", "tmdb_id", existing_type=sa.Integer(), nullable=True)
    op.create_unique_constraint("uq_media_entities_local_key", "media_entities", ["local_key"])


def downgrade() -> None:
    connection = op.get_bind()
    local_count = connection.scalar(
        sa.text("SELECT COUNT(*) FROM media_entities WHERE metadata_source = 'LOCAL'")
    )
    if local_count:
        raise RuntimeError("存在本地元数据，无法安全降级；请先导出或移除相关记录")
    op.drop_constraint("uq_media_entities_local_key", "media_entities", type_="unique")
    op.alter_column("media_entities", "tmdb_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("media_entities", "local_key")
    op.drop_column("media_entities", "provider_id")
    op.drop_column("media_entities", "metadata_source")
