import os
import sys

# Fake env vars required by config.py before any src import
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:AAFakeTokenForTesting")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("DATA_DIR", "/tmp/tt2tg_test")

# Make src/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
