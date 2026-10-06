"""Upload The Mentalist S01 episodes to S3 and print SQL for Adminer.

Usage:
    python scripts/upload_mentalist.py

Requires: boto3 (already in the project's venv)
"""

import os
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

# ── S3 credentials ──────────────────────────────────────────────────
S3_ENDPOINT = "https://s3.regru.cloud"
S3_BUCKET = "seans"
S3_ACCESS_KEY = "TB0184WVZSUWKC4UXAPR"
S3_SECRET_KEY = "CfcmegLOq7BBX1Nt0nM92kWWgNFjCmTwofk7Sv8i"
S3_REGION = "us-east-1"

# ── Paths ───────────────────────────────────────────────────────────
SEASON_DIR = Path(r"D:\downloads\torrent\The.Mentalist.2008-2015.web-dlrip_[teko]\Season_01")

# ── IDs (generate once, reuse in SQL) ───────────────────────────────
MEDIA_ITEM_ID = uuid.uuid4()
# ⚠️  Replace with your actual user_id from the `users` table.
#     Run in Adminer: SELECT id, email FROM users;
USER_ID = uuid.UUID("2ffb4ad6-e2ce-4232-a857-db71c08eced1")
TASK_ID = uuid.uuid4()

# ── KinoPoisk data for The Mentalist ────────────────────────────────
KP_ID = 395999

# ── S3 client ───────────────────────────────────────────────────────
_config = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
    retries={"max_attempts": 3},
)

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION,
    config=_config,
)


def upload_file(local_path: Path, s3_key: str) -> int:
    """Upload a file to S3, return size in bytes."""
    size = local_path.stat().st_size
    print(f"  Uploading {local_path.name} ({size / 1024 / 1024:.1f} MB) -> {s3_key}")
    s3.upload_file(str(local_path), S3_BUCKET, s3_key)
    return size


def main():
    if not SEASON_DIR.exists():
        print(f"ERROR: Directory not found: {SEASON_DIR}")
        return

    files = sorted(SEASON_DIR.glob("*.avi"))
    if not files:
        print(f"ERROR: No .avi files in {SEASON_DIR}")
        return

    print(f"Found {len(files)} episodes. Uploading to s3://{S3_BUCKET}/...\n")

    # ── Upload files ────────────────────────────────────────────────
    task_files = []
    for f in files:
        # Parse episode number from filename: s01e01_Pilot.avi -> episode=1
        name = f.stem  # s01e01_Pilot
        ep_part = name.split("_")[0]  # s01e01
        episode = int(ep_part[4:])  # s01e01 -> 1

        s3_key = f"users/{USER_ID}/{MEDIA_ITEM_ID}/{f.name}"
        size = upload_file(f, s3_key)
        task_files.append({
            "path": f.name,
            "s3_key": s3_key,
            "size_bytes": size,
            "episode": episode,
        })

    total_size = sum(tf["size_bytes"] for tf in task_files)

    # ── Print SQL ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SQL для Adminer (выполни по порядку):")
    print("=" * 70)

    print(f"""
-- 1. MediaItem (Менталист, 2008, сериал)
INSERT INTO media_items (id, kp_id, kp_type, title, original_title, year, poster_url, overview, rating_kp, genres, raw, updated_at)
VALUES (
    '{MEDIA_ITEM_ID}',
    {KP_ID},
    'tv',
    'Менталист',
    'The Mentalist',
    2008,
    'https://st.kp.yandex.net/images/film_iphone/iphone360_{KP_ID}.jpg',
    'Патрик Джейн — бывший экстрасенс-шарлатан, который после трагической гибели семьи начинает помогать полиции Калифорнии в раскрытии преступлений, используя свои навыки наблюдения и манипуляции.',
    8.2,
    ARRAY['детектив', 'драма', 'комедия', 'криминал'],
    '{{}}'::jsonb,
    NOW()
)
ON CONFLICT (kp_id) DO UPDATE SET title = 'Менталист', updated_at = NOW();
""")

    print(f"""-- 2. LibraryItem (привязка к пользователю)
-- ⚠️  Замени USER_ID на реальный id из таблицы users
INSERT INTO library_items (id, user_id, media_item_id, source_task_id, status, created_at)
VALUES (
    '{uuid.uuid4()}',
    '{USER_ID}',  -- ← замени на свой user_id
    '{MEDIA_ITEM_ID}',
    '{TASK_ID}',
    'ready',
    NOW()
)
ON CONFLICT (user_id, media_item_id) DO NOTHING;
""")

    print(f"""-- 3. Task (завершённая задача загрузки)
INSERT INTO tasks (id, user_id, media_item_id, torrent_release_id, worker_id, status, priority, attempts, max_attempts, reserved_bytes, progress_pct, speed_bps, stage, error, lease_expires_at, created_at, updated_at)
VALUES (
    '{TASK_ID}',
    '{USER_ID}',  -- ← замени на свой user_id
    '{MEDIA_ITEM_ID}',
    '{uuid.uuid4()}',  -- заглушка torrent_release_id
    NULL,
    'completed',
    0, 0, 3,
    0,
    100,
    0,
    NULL, NULL, NULL,
    NOW(), NOW()
);
""")

    print("-- 4. TaskFiles (файлы эпизодов)")
    for tf in task_files:
        print(f"""INSERT INTO task_files (id, task_id, path, size_bytes, s3_key, status, season, episode, uploaded_at)
VALUES ('{uuid.uuid4()}', '{TASK_ID}', '{tf["path"]}', {tf["size_bytes"]}, '{tf["s3_key"]}', 'uploaded', 1, {tf["episode"]}, NOW());""")

    print(f"""
-- Готово! Всего файлов: {len(task_files)}, общий размер: {total_size / 1024 / 1024 / 1024:.2f} ГБ
""")


if __name__ == "__main__":
    main()