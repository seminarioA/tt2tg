from __future__ import annotations

import asyncpg
from datetime import date
from typing import Optional

import config

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Accounts ─────────────────────────────────────────────────────────────────

async def get_account_by_id(account_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM accounts WHERE id = $1", account_id)
    return dict(row) if row else None


async def add_account(username: str, chat_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO accounts (username, chat_id)
        VALUES ($1, $2)
        ON CONFLICT (username, chat_id) DO UPDATE
          SET is_active = TRUE
        RETURNING *
        """,
        username, chat_id,
    )
    return dict(row)


async def remove_account(username: str, chat_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE accounts SET is_active = FALSE WHERE username = $1 AND chat_id = $2 AND is_active = TRUE",
        username, chat_id,
    )
    return result.split()[-1] != "0"


async def get_active_accounts() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM accounts WHERE is_active = TRUE ORDER BY added_at"
    )
    return [dict(r) for r in rows]


async def get_account_by_username_and_chat(username: str, chat_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM accounts WHERE username = $1 AND chat_id = $2",
        username, chat_id,
    )
    return dict(row) if row else None


async def update_last_checked(account_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE accounts SET last_checked = NOW() WHERE id = $1", account_id
    )


async def set_paused(account_id: int, paused: bool):
    pool = await get_pool()
    await pool.execute(
        "UPDATE accounts SET is_paused = $1 WHERE id = $2", paused, account_id
    )


async def get_accounts_with_unsent_videos() -> list[dict]:
    """Active, non-paused accounts with unsent videos — used for restart recovery."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (a.id) a.*
        FROM accounts a
        JOIN videos v ON v.account_id = a.id
        WHERE a.is_active = TRUE AND a.is_paused = FALSE AND v.sent_at IS NULL
        ORDER BY a.id, a.added_at
        """
    )
    return [dict(r) for r in rows]


async def get_account_video_count(account_id: int) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM videos WHERE account_id = $1", account_id
    )
    return row["n"]


async def get_sent_video_count(account_id: int) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM videos WHERE account_id = $1 AND sent_at IS NOT NULL",
        account_id,
    )
    return row["n"]


# ── Videos ───────────────────────────────────────────────────────────────────

async def video_was_sent(video_id: str, account_id: int) -> bool:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM videos WHERE video_id = $1 AND account_id = $2 AND sent_at IS NOT NULL",
        video_id, account_id,
    )
    return row is not None


async def add_video(
    *,
    video_id: str,
    account_id: int,
    url: str,
    metadata_path: Optional[str] = None,
    upload_date: Optional[date] = None,
    description: Optional[str] = None,
    like_count: Optional[int] = None,
    repost_count: Optional[int] = None,
) -> bool:
    """Insert video for this account, ignore if already exists. Returns True if inserted."""
    pool = await get_pool()
    result = await pool.execute(
        """
        INSERT INTO videos
          (video_id, account_id, url, metadata_path, upload_date,
           description, like_count, repost_count)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (video_id, account_id) DO NOTHING
        """,
        video_id, account_id, url, metadata_path, upload_date,
        description, like_count, repost_count,
    )
    return result.split()[-1] != "0"


async def mark_video_sent(video_id: str, account_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE videos SET sent_at = NOW() WHERE video_id = $1 AND account_id = $2",
        video_id, account_id,
    )


async def reset_account_sent(account_id: int):
    """Mark all videos of an account as unsent so they get re-sent from scratch."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE videos SET sent_at = NULL WHERE account_id = $1", account_id
    )
