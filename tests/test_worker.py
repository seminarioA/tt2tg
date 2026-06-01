from datetime import date
from unittest.mock import AsyncMock, patch
import pytest
from worker import _parse_date, _key, pause_account, resume_account


class TestParseDate:
    def test_valid(self):
        assert _parse_date("20250530") == date(2025, 5, 30)

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_wrong_length(self):
        assert _parse_date("202505") is None

    def test_invalid_date(self):
        assert _parse_date("20251345") is None  # month 13

    def test_start_of_year(self):
        assert _parse_date("20210601") == date(2021, 6, 1)


class TestKey:
    def test_positive_chat_id(self):
        assert _key("cooliopink", 123456) == "cooliopink:123456"

    def test_negative_chat_id(self):
        assert _key("user", -1001234567890) == "user:-1001234567890"


class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_calls_db(self):
        account = {"id": 7}
        with patch("worker.db") as mock_db:
            mock_db.set_paused = AsyncMock()
            await pause_account(account)
            mock_db.set_paused.assert_called_once_with(7, True)

    @pytest.mark.asyncio
    async def test_resume_calls_db(self):
        account = {"id": 7}
        with patch("worker.db") as mock_db:
            mock_db.set_paused = AsyncMock()
            await resume_account(account)
            mock_db.set_paused.assert_called_once_with(7, False)


class TestIterNewVideos:
    @pytest.mark.asyncio
    async def test_skips_already_sent(self):
        from unittest.mock import MagicMock
        from worker import _iter_new_videos

        bot = MagicMock()
        account = {"id": 1, "username": "test", "chat_id": 100}
        entries = [{"id": "vid1", "url": "https://tiktok.com/1"}]

        with patch("worker.db") as mock_db:
            mock_db.video_was_sent = AsyncMock(return_value=True)
            mock_db.get_account_by_username_and_chat = AsyncMock(
                return_value={"is_paused": False}
            )
            sent = await _iter_new_videos(bot, account, entries)

        assert sent == 0

    @pytest.mark.asyncio
    async def test_stops_when_paused(self):
        from unittest.mock import MagicMock
        from worker import _iter_new_videos

        bot = MagicMock()
        account = {"id": 1, "username": "test", "chat_id": 100}
        entries = [
            {"id": "vid1", "url": "https://tiktok.com/1"},
            {"id": "vid2", "url": "https://tiktok.com/2"},
        ]

        with patch("worker.db") as mock_db:
            mock_db.video_was_sent = AsyncMock(return_value=False)
            # Return paused=True on first check inside the loop
            mock_db.get_account_by_username_and_chat = AsyncMock(
                return_value={"is_paused": True}
            )
            sent = await _iter_new_videos(bot, account, entries)

        assert sent == 0
