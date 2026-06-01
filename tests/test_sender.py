from datetime import date
import pytest
from sender import _fmt_num, _fmt_date, build_caption


class TestFmtNum:
    def test_none(self):
        assert _fmt_num(None) == "—"

    def test_zero(self):
        assert _fmt_num(0) == "0"

    def test_small(self):
        assert _fmt_num(500) == "500"

    def test_thousands(self):
        assert _fmt_num(12400) == "12.4K"

    def test_exact_thousand(self):
        assert _fmt_num(1000) == "1.0K"

    def test_millions(self):
        assert _fmt_num(1_500_000) == "1.5M"

    def test_large_millions(self):
        assert _fmt_num(10_000_000) == "10.0M"


class TestFmtDate:
    def test_none(self):
        assert _fmt_date(None) == "—"

    def test_ytdlp_string(self):
        assert _fmt_date("20250530") == "2025-05-30"

    def test_date_object(self):
        assert _fmt_date(date(2025, 5, 30)) == "2025-05-30"

    def test_unknown_string(self):
        assert _fmt_date("unknown") == "unknown"


class TestBuildCaption:
    def test_full_caption(self):
        caption = build_caption(
            username="cooliopink",
            upload_date="20250530",
            like_count=12400,
            repost_count=320,
            description="Test video description",
            url="https://www.tiktok.com/@cooliopink/video/123",
        )
        assert "@cooliopink" in caption
        assert "📅 2025-05-30" in caption
        assert "❤️ 12.4K" in caption
        assert "🔁 320" in caption
        assert "💬 Test video description" in caption
        assert "🔗 https://www.tiktok.com/@cooliopink/video/123" in caption

    def test_no_description(self):
        caption = build_caption(username="testuser")
        assert "💬" not in caption
        assert "@testuser" in caption
        assert "📅" in caption

    def test_no_url(self):
        caption = build_caption(username="testuser", description="hello")
        assert "🔗" not in caption
        assert "💬 hello" in caption

    def test_long_description_truncated(self):
        caption = build_caption(username="u", description="A" * 400)
        assert "…" in caption
        assert "💬" in caption

    def test_description_exactly_300_not_truncated(self):
        desc = "A" * 300
        caption = build_caption(username="u", description=desc)
        assert "…" not in caption

    def test_none_counts_show_dash(self):
        caption = build_caption(username="u", like_count=None, repost_count=None)
        assert "❤️ —" in caption
        assert "🔁 —" in caption
