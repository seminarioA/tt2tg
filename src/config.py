import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL: str = os.environ["DATABASE_URL"]

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
METADATA_DIR = DATA_DIR / "metadata"
TEMP_DIR = DATA_DIR / "temp"

POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "10"))
POLL_INTERVAL_MAX = int(os.getenv("POLL_INTERVAL_MAX", "15"))

COOKIES_FILE: str | None = os.getenv("COOKIES_FILE")

METADATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
