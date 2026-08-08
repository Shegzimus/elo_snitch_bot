"""Single source of truth for paths, credentials and the database engine.

Every pipeline script imports from here instead of hardcoding
"postgresql://root:root@localhost:5432/snitch_bot_db" and re-deriving the
project root. Accepts both the UPPER_CASE names in config/.env.example and the
lower_case ones already present in existing .env files.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
ENV_PATH: Path = CONFIG_DIR / ".env"
GOOGLE_CREDENTIALS_PATH: Path = PROJECT_ROOT / ".google" / "credentials.json"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """First non-empty value among `names`, else `default`."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def require(*names: str) -> str:
    """Like _env but raises instead of returning None. Never logs the value."""
    value = _env(*names)
    if not value:
        raise RuntimeError(
            f"Missing required setting: {' or '.join(names)}. "
            f"Add it to {ENV_PATH} (see config/.env.example)."
        )
    return value


# --- Database ---------------------------------------------------------------
# DATABASE_URL wins if set; otherwise assembled from parts. Defaults match the
# credentials in config/pgadmin.env so local dev keeps working untouched.
POSTGRES_USER: str = _env("POSTGRES_USER", default="root")
POSTGRES_PASSWORD: str = _env("POSTGRES_PASSWORD", default="root")
POSTGRES_HOST: str = _env("POSTGRES_HOST", default="localhost")
POSTGRES_PORT: str = _env("POSTGRES_PORT", default="5432")
POSTGRES_DB: str = _env("POSTGRES_DB", default="snitch_bot_db")

DATABASE_URL: str = _env("DATABASE_URL") or (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# --- Riot -------------------------------------------------------------------
# Two different routing values: account-v1 is regional (europe/americas/asia),
# league-v4 and champion-mastery-v4 are platform (euw1/na1/...).
RIOT_REGION: str = _env("RIOT_REGION", default="europe")
RIOT_PLATFORM: str = _env("RIOT_PLATFORM", default="euw1")
RIOT_ACCOUNT_BASE_URL: str = f"https://{RIOT_REGION}.api.riotgames.com"
RIOT_PLATFORM_BASE_URL: str = f"https://{RIOT_PLATFORM}.api.riotgames.com"

# --- Google -----------------------------------------------------------------
GOOGLE_SHEET_RANGE: str = _env("GOOGLE_SHEET_RANGE", default="Form Responses 1!A:D")


def riot_api_key() -> str:
    """Resolved lazily so importing this module never requires a live key."""
    return require("RIOT_API_KEY", "riot_api_key")


def google_sheet_id() -> str:
    return require("GOOGLE_SHEET_ID", "google_sheet_id")


def riot_headers() -> dict:
    """Auth header for Riot requests. Never put the key in a query string --
    it ends up in logs, proxies and error messages."""
    return {"X-Riot-Token": riot_api_key()}


_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """Process-wide SQLAlchemy engine. pool_pre_ping avoids stale connections
    when the Postgres container restarts between hourly runs."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine
