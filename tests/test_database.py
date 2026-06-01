from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
import pytest
import database


def make_pool(fetchrow_result=None, execute_result="UPDATE 1"):
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow_result)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value=execute_result)
    return pool


@pytest.mark.asyncio
async def test_add_account():
    row = {"id": 1, "username": "cool", "chat_id": 42, "is_active": True,
           "added_at": None, "last_checked": None, "is_paused": False}
    pool = make_pool(fetchrow_result=row)
    with patch("database.get_pool", return_value=pool):
        result = await database.add_account("cool", 42)
    assert result["username"] == "cool"
    assert result["chat_id"] == 42


@pytest.mark.asyncio
async def test_video_was_sent_true():
    pool = make_pool(fetchrow_result={"id": 5})
    with patch("database.get_pool", return_value=pool):
        assert await database.video_was_sent("vid123", 1) is True


@pytest.mark.asyncio
async def test_video_was_sent_false():
    pool = make_pool(fetchrow_result=None)
    with patch("database.get_pool", return_value=pool):
        assert await database.video_was_sent("vid123", 1) is False


@pytest.mark.asyncio
async def test_remove_account_found():
    pool = make_pool(execute_result="UPDATE 1")
    with patch("database.get_pool", return_value=pool):
        assert await database.remove_account("cool", 42) is True


@pytest.mark.asyncio
async def test_remove_account_not_found():
    pool = make_pool(execute_result="UPDATE 0")
    with patch("database.get_pool", return_value=pool):
        assert await database.remove_account("nobody", 42) is False


@pytest.mark.asyncio
async def test_get_active_accounts_empty():
    pool = make_pool()
    pool.fetch = AsyncMock(return_value=[])
    with patch("database.get_pool", return_value=pool):
        result = await database.get_active_accounts()
    assert result == []


@pytest.mark.asyncio
async def test_get_account_by_username_and_chat_found():
    row = {"id": 3, "username": "cool", "chat_id": -100123, "is_active": True,
           "added_at": None, "last_checked": None, "is_paused": False}
    pool = make_pool(fetchrow_result=row)
    with patch("database.get_pool", return_value=pool):
        result = await database.get_account_by_username_and_chat("cool", -100123)
    assert result is not None
    assert result["id"] == 3


@pytest.mark.asyncio
async def test_get_account_by_username_and_chat_not_found():
    pool = make_pool(fetchrow_result=None)
    with patch("database.get_pool", return_value=pool):
        result = await database.get_account_by_username_and_chat("nobody", 999)
    assert result is None


@pytest.mark.asyncio
async def test_mark_video_sent():
    pool = make_pool()
    with patch("database.get_pool", return_value=pool):
        await database.mark_video_sent("vid1", 1)
    pool.execute.assert_called_once()
    call_args = pool.execute.call_args[0]
    assert "sent_at" in call_args[0]
    assert "vid1" in call_args


@pytest.mark.asyncio
async def test_set_paused_true():
    pool = make_pool()
    with patch("database.get_pool", return_value=pool):
        await database.set_paused(3, True)
    call_args = pool.execute.call_args[0]
    assert True in call_args
    assert 3 in call_args


@pytest.mark.asyncio
async def test_reset_account_sent():
    pool = make_pool()
    with patch("database.get_pool", return_value=pool):
        await database.reset_account_sent(5)
    call_args = pool.execute.call_args[0]
    assert "sent_at = NULL" in call_args[0]
    assert 5 in call_args
