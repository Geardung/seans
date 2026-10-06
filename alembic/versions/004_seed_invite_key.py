"""seed bootstrap invite key

Revision ID: 004
Revises: 003
Create Date: 2026-10-06
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "invite_keys", "created_by",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    key = uuid.uuid4().hex
    op.execute(
        f"INSERT INTO invite_keys (id, key, created_by) "
        f"VALUES ('{uuid.uuid4()}', '{key}', NULL)"
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM invite_keys WHERE created_by IS NULL"))
    op.alter_column(
        "invite_keys", "created_by",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )