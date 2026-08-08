import time
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import text

import config
from logger_config import setup_logger

logger = setup_logger(__name__, 'generate_puuid.log')

engine = config.get_engine()


def fetch_players_without_puuid() -> pd.DataFrame:
    """Players registered via the form that still need a puuid resolved."""
    query = """
    SELECT id, summ_id, player_tag
    FROM public.players
    WHERE puuid IS NULL
    ORDER BY id
    """
    with engine.connect() as connection:
        return pd.read_sql(query, connection, index_col='id')


def set_puuid(player_key: int, puuid: str) -> None:
    """Store a resolved puuid against a player."""
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE public.players SET puuid = :puuid WHERE id = :id"),
            {"puuid": puuid, "id": player_key},
        )


def get_puuid_from_riot(summoner_name: str, tag: str) -> Optional[str]:
    """Resolve a Riot ID (name#tag) to a puuid via account-v1."""
    url = (
        f"{config.RIOT_ACCOUNT_BASE_URL}/riot/account/v1/accounts/by-riot-id/"
        f"{requests.utils.quote(summoner_name)}/{requests.utils.quote(tag)}"
    )

    try:
        response = requests.get(url, headers=config.riot_headers(), timeout=10)
        if response.status_code == 200:
            return response.json().get("puuid")
        if response.status_code == 404:
            logger.warning(f"No Riot account found for {summoner_name}#{tag}")
        else:
            logger.error(
                f"API error for {summoner_name}#{tag}: "
                f"{response.status_code} - {response.text[:200]}"
            )
    except requests.RequestException as e:
        logger.error(f"Request failed for {summoner_name}#{tag}: {e}")

    return None


def process_players() -> int:
    """Resolve and persist puuids for everyone missing one. Returns the count updated."""
    df = fetch_players_without_puuid()
    if df.empty:
        logger.info("All players already have a puuid")
        return 0

    logger.info(f"Resolving puuids for {len(df)} players")
    updated_count = 0

    for player_key, row in df.iterrows():
        puuid = get_puuid_from_riot(row['summ_id'], row['player_tag'])
        if puuid:
            set_puuid(player_key, puuid)
            updated_count += 1
            logger.info(f"Resolved puuid for {row['summ_id']}#{row['player_tag']}")
        else:
            logger.warning(f"Could not resolve {row['summ_id']}#{row['player_tag']}")

        time.sleep(0.1)

    return updated_count


def main():
    logger.info("Starting puuid resolution process")
    updated = process_players()
    logger.info(f"Resolved {updated} new puuids")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        raise
