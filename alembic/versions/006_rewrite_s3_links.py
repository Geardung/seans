"""rewrite old S3 links to new endpoint

Revision ID: 006
Revises: 005
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ENDPOINT = "https://s3.regru.cloud"
NEW_ENDPOINT = "https://s3.buckets.ru"


def upgrade() -> None:
    # Columns that may hold absolute URLs or endpoint-prefixed keys.
    for table, column in (
        ("task_files", "s3_key"),
        ("task_files", "path"),
        ("media_items", "poster_url"),
    ):
        op.execute(
            f"UPDATE {table} "
            f"SET {column} = replace({column}, '{OLD_ENDPOINT}', '{NEW_ENDPOINT}') "
            f"WHERE {column} LIKE '%{OLD_ENDPOINT}%'"
        )


def downgrade() -> None:
    for table, column in (
        ("task_files", "s3_key"),
        ("task_files", "path"),
        ("media_items", "poster_url"),
    ):
        op.execute(
            f"UPDATE {table} "
            f"SET {column} = replace({column}, '{NEW_ENDPOINT}', '{OLD_ENDPOINT}') "
            f"WHERE {column} LIKE '%{NEW_ENDPOINT}%'"
        )
