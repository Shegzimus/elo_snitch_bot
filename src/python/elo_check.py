import time
from typing import List, Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from logger_config import setup_logger

logger = setup_logger(__name__, 'elo_check.log')

engine = config.get_engine()

QUEUE_TYPES = ("RANKED_SOLO_5x5", "RANKED_FLEX_SR")


def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_players(db_connection=engine) -> pd.DataFrame:
    """Players that have a resolved puuid. Anyone without one is skipped --
    generate_puuid.py is responsible for filling those in."""
    logger.info("Fetching players from database")
    with db_connection.connect() as connection:
        df: pd.DataFrame = pd.read_sql(
            """
            SELECT id, summ_id, puuid
            FROM public.players
            WHERE puuid IS NOT NULL
            ORDER BY id
            """,
            connection,
            index_col='id',
        )
    if df.empty:
        logger.warning("No players with a puuid found")
    else:
        logger.info(f"Fetched {len(df)} players with puuids")
    return df


def fetch_entries(session: requests.Session, puuid: str) -> Optional[list]:
    """Return the raw league entries for a puuid, or None if the call failed."""
    url = f"{config.RIOT_PLATFORM_BASE_URL}/lol/league/v4/entries/by-puuid/{puuid}"
    headers = config.riot_headers()

    response = session.get(url, headers=headers, timeout=30)

    if response.status_code == 200:
        return response.json()

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        logger.warning(f"Rate limited. Waiting {retry_after}s before retry...")
        time.sleep(retry_after)
        response = session.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()

    logger.error(f"Riot API returned {response.status_code}: {response.text[:200]}")
    return None


def elo_check() -> List[dict]:
    """Fetch current ranked standings for every player with a puuid.

    Returns one row per player per queue they are ranked in. Players who are
    unranked in a queue simply produce no row for it.
    """
    players_df = fetch_players()
    if players_df.empty:
        return []

    session = create_session_with_retries()
    scanned_at = pd.Timestamp.now()
    rows: List[dict] = []

    total = len(players_df)
    for position, (player_key, player) in enumerate(players_df.iterrows(), start=1):
        logger.info(f"Processing {player['summ_id']} ({position}/{total})")

        try:
            entries = fetch_entries(session, player['puuid'])
        except requests.exceptions.Timeout:
            logger.error(f"Timeout for {player['summ_id']}")
            entries = None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {player['summ_id']}: {e}")
            entries = None

        if entries is None:
            continue

        for queue_type in QUEUE_TYPES:
            entry = next((item for item in entries if item.get("queueType") == queue_type), None)
            if entry is None:
                continue
            rows.append({
                "timestamp": scanned_at,
                "player_key": player_key,
                "queue_type": queue_type,
                "tier": entry["tier"],
                "rank": entry.get("rank"),
                "league_points": entry["leaguePoints"],
                "wins": entry["wins"],
                "losses": entry["losses"],
            })

        # Riot allows 20 req/s on a dev key; 0.1s keeps us well inside that.
        time.sleep(0.1)

    return rows


def main():
    logger.info("Starting ELO check process")
    rows = elo_check()

    if not rows:
        logger.warning("No ranked data to load.")
        return

    df = pd.DataFrame(rows)
    logger.info(f"Loading {len(df)} scan rows to database")
    df.to_sql(name="elo_history", con=engine, if_exists='append', index=False)

    for queue_type, count in df['queue_type'].value_counts().items():
        logger.info(f"  {queue_type}: {count} players")
    logger.info("Scan data loaded successfully into the database.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        raise
