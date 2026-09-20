"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("10737418240")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # workers
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # media_items
    op.create_table(
        "media_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kp_id", sa.BigInteger(), unique=True),
        sa.Column("kp_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_title", sa.Text()),
        sa.Column("year", sa.Integer()),
        sa.Column("poster_url", sa.Text()),
        sa.Column("overview", sa.Text()),
        sa.Column("rating_kp", sa.Numeric(3, 1)),
        sa.Column("genres", postgresql.ARRAY(sa.String), server_default=sa.text("'{}'")),
        sa.Column("raw", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kp_type IN ('movie','tv')", name="ck_media_items_kp_type"),
    )

    # torrent_releases
    op.create_table(
        "torrent_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("media_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("tracker", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("info_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("seeders", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("leechers", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("quality", sa.Text()),
        sa.Column("voiceover", sa.Text()),
        sa.Column("magnet", sa.Text()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_item_id", "info_hash", name="uq_torrent_releases_media_hash"),
    )

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("media_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_items.id"), nullable=False),
        sa.Column("torrent_release_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("torrent_releases.id"), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("progress_pct", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("speed_bps", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("stage", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued','assigned','downloading','uploading','completed','failed','canceled')",
            name="ck_tasks_status",
        ),
    )
    op.create_index("idx_tasks_claim", "tasks", ["status", "priority", "created_at"], postgresql_where="status = 'queued'")
    op.create_index("idx_tasks_lease", "tasks", ["lease_expires_at"], postgresql_where="status IN ('assigned','downloading','uploading')")

    # task_files
    op.create_table(
        "task_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("s3_key", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("season", sa.Integer()),
        sa.Column("episode", sa.Integer()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('pending','uploaded')", name="ck_task_files_status"),
        sa.UniqueConstraint("task_id", "path", name="uq_task_files_task_path"),
    )

    # library_items
    op.create_table(
        "library_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_items.id"), nullable=False),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('in_progress','ready')", name="ck_library_items_status"),
        sa.UniqueConstraint("user_id", "media_item_id", name="uq_library_items_user_media"),
    )

    # watch_history
    op.create_table(
        "watch_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_sec", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_sec", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_file_id", name="uq_watch_history_user_file"),
    )

    # reviews
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("review", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("score BETWEEN 1 AND 10", name="ck_reviews_score"),
        sa.UniqueConstraint("user_id", "media_item_id", name="uq_reviews_user_media"),
    )

    # rooms
    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("host_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_files.id"), nullable=False),
        sa.Column("current_position", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_playing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # room_members
    op.create_table(
        "room_members",
        sa.Column("room_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("room_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("room_members")
    op.drop_table("rooms")
    op.drop_table("reviews")
    op.drop_table("watch_history")
    op.drop_table("library_items")
    op.drop_table("task_files")
    op.drop_index("idx_tasks_lease", table_name="tasks")
    op.drop_index("idx_tasks_claim", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("torrent_releases")
    op.drop_table("media_items")
    op.drop_table("workers")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS citext")