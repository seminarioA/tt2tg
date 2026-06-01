from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
from pathlib import Path
from typing import Optional

from telegram import Bot

import database as db
import downloader
from sender import build_caption, send_video, send_text
import config

logger = logging.getLogger(__name__)

# Accounts currently doing their initial backlog archive
_archiving: set[str] = set()

# Accounts manually paused via /stop
_paused: set[str] = set()


def pause_account(username: str):
    _paused.add(username)


def resume_account(username: str):
    _paused.discard(username)


def is_paused(username: str) -> bool:
    return username in _paused


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(raw: Optional[str]) -> Optional[date]:
    if raw and len(raw) == 8:
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
        except ValueError:
            pass
    return None


async def _process_video(bot: Bot, account: dict, url: str, info: dict) -> bool:
    """Download, send, and clean up one video. Returns True on success."""
    video_id = str(info.get("id", ""))
    if not video_id:
        return False

    username = account["username"]
    chat_id = account["chat_id"]
    upload_date = _parse_date(info.get("upload_date"))

    # Persist metadata JSON (always keep)
    meta_path = downloader.save_metadata(info, video_id, username)

    # Insert into DB (idempotent)
    await db.add_video(
        video_id=video_id,
        account_id=account["id"],
        url=url,
        metadata_path=str(meta_path),
        upload_date=upload_date,
        description=info.get("description"),
        like_count=info.get("like_count"),
        repost_count=info.get("repost_count"),
    )

    # Download
    video_path = await downloader.download_video(url, video_id)
    if not video_path:
        logger.warning("Could not download %s", url)
        return False

    caption = build_caption(
        username=username,
        upload_date=upload_date,
        like_count=info.get("like_count"),
        repost_count=info.get("repost_count"),
        description=info.get("description"),
        url=info.get("webpage_url") or url,
    )

    sent = await send_video(bot, chat_id, video_path, caption)

    # Always delete the local video file
    try:
        video_path.unlink(missing_ok=True)
    except Exception:
        pass

    if sent:
        await db.mark_video_sent(video_id)

    return sent


async def _iter_new_videos(bot: Bot, account: dict, entries: list[dict]) -> int:
    """Process entries that haven't been sent yet. Returns count of sent videos."""
    username = account["username"]
    sent = 0
    for entry in entries:
        if username in _paused:
            logger.info("@%s paused — stopping mid-send", username)
            break

        url = entry.get("webpage_url") or entry.get("url")
        if not url:
            continue

        video_id = str(entry.get("id", ""))
        if video_id and await db.video_was_sent(video_id):
            continue

        info = await downloader.fetch_video_info(url)
        if not info:
            continue

        ok = await _process_video(bot, account, url, info)
        if ok:
            sent += 1

        # Polite delay between downloads
        await asyncio.sleep(random.uniform(3, 7))

    return sent


# ── Public: called from bot command handler ───────────────────────────────────

async def archive_account(bot: Bot, account: dict, resuming: bool = False):
    """Fetch all videos and send unsent ones. resuming=True changes status messages."""
    username = account["username"]
    chat_id = account["chat_id"]

    # Prevent two parallel archive tasks for the same account
    if username in _archiving:
        logger.warning("archive_account called while @%s is already archiving — skipped", username)
        return

    _archiving.add(username)

    try:
        await send_text(bot, chat_id, f"🔍 Obteniendo videos de @{username}…")

        try:
            entries = await downloader.fetch_profile_entries(username)
        except Exception as exc:
            logger.error("fetch_profile_entries failed for @%s: %s", username, exc)
            await send_text(bot, chat_id, f"❌ Error al obtener videos de @{username}:\n{exc}")
            return

        total = len(entries)

        if resuming:
            already_sent = await db.get_sent_video_count(account["id"])
            pending = total - already_sent
            await send_text(
                bot, chat_id,
                f"▶️ @{username}\n{pending} videos pendientes de {total} totales\n📤 Continuando…",
            )
        else:
            await send_text(
                bot, chat_id,
                f"📦 Cuenta registrada: @{username}\n{total} videos encontrados\n📤 Enviando…",
            )

        # Oldest → newest
        sent = await _iter_new_videos(bot, account, list(reversed(entries)))
        await db.update_last_checked(account["id"])

        if username in _paused:
            await send_text(
                bot, chat_id,
                f"⏸️ @{username} — pausado ({sent} enviados en esta sesión). Usá /resume @{username} para continuar.",
            )
        else:
            await send_text(
                bot, chat_id,
                f"✅ @{username} — {sent} videos enviados\n🔄 Monitoreando nuevos videos…",
            )

    finally:
        _archiving.discard(username)


# ── Public: called from polling loop ─────────────────────────────────────────

async def check_new_videos(bot: Bot, account: dict):
    username = account["username"]

    if username in _archiving:
        logger.debug("Skipping @%s — initial archive still running", username)
        return

    logger.info("Polling @%s", username)

    try:
        entries = await downloader.fetch_profile_entries(username)
    except Exception as exc:
        logger.error("Polling failed for @%s: %s", username, exc)
        return

    sent = await _iter_new_videos(bot, account, entries)
    await db.update_last_checked(account["id"])

    if sent:
        logger.info("Sent %d new video(s) from @%s", sent, username)


# ── Main polling loop ─────────────────────────────────────────────────────────

async def polling_loop(bot: Bot):
    logger.info("Polling loop started (interval %d–%d min)",
                config.POLL_INTERVAL_MIN, config.POLL_INTERVAL_MAX)
    while True:
        accounts = await db.get_active_accounts()

        for account in accounts:
            try:
                await check_new_videos(bot, account)
            except Exception as exc:
                logger.error("Unhandled error for @%s: %s", account["username"], exc)
            # Brief pause between accounts
            await asyncio.sleep(random.uniform(10, 20))

        interval = random.randint(
            config.POLL_INTERVAL_MIN * 60,
            config.POLL_INTERVAL_MAX * 60,
        )
        logger.info("Next poll cycle in %ds", interval)
        await asyncio.sleep(interval)
