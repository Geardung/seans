"""add tmdb_id to media_items

Revision ID: 003
Revises: 002
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_items", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.create_index("ix_media_items_tmdb_id", "media_items", ["tmdb_id"])


def downgrade() -> None:
    op.drop_index("ix_media_items_tmdb_id", table_name="media_items")
    op.drop_column("media_items", "tmdb_id")
