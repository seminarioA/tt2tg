from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import yt_dlp

import config

logger = logging.getLogger(__name__)

_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
}


def _common_opts() -> dict:
    opts = dict(_BASE_OPTS)
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


# ── Profile listing ──────────────────────────────────────────────────────────

def _fetch_entries(username: str) -> list[dict]:
    url = f"https://www.tiktok.com/@{username}"
    opts = _common_opts() | {
        "extract_flat": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info.get("entries", []) if info else []


async def fetch_profile_entries(username: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_entries, username)


# ── Full video metadata ──────────────────────────────────────────────────────

def _fetch_info(url: str) -> Optional[dict]:
    opts = _common_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.error("fetch_info failed for %s: %s", url, exc)
        return None


async def fetch_video_info(url: str) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_info, url)


# ── Download ─────────────────────────────────────────────────────────────────

def _download(url: str, video_id: str) -> Optional[Path]:
    out = config.TEMP_DIR / f"{video_id}.%(ext)s"
    opts = _common_opts() | {
        "outtmpl": str(out),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "max_filesize": 49 * 1024 * 1024,  # Telegram bot limit = 50 MB
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        logger.error("download failed for %s: %s", url, exc)
        return None

    result = config.TEMP_DIR / f"{video_id}.mp4"
    return result if result.exists() else None


async def download_video(url: str, video_id: str) -> Optional[Path]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download, url, video_id)


# ── Metadata persistence ─────────────────────────────────────────────────────

def save_metadata(info: dict, video_id: str, username: str) -> Path:
    dest_dir = config.METADATA_DIR / username
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{video_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)
    return path
