import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from typing import Dict, Optional, Tuple

load_dotenv(dotenv_path=os.path.join("config", ".env"))

engine = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")


def ensure_puuid_table_exists() -> None:
    """Ensure the puuid table exists in the database."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS public.puuid (
                id INTEGER PRIMARY KEY, 
                index INTEGER,
                puuid TEXT
            )
        """))


def fetch_player_data() -> pd.DataFrame:
    """Fetch player data including existing puuids if available."""
    query = """
    SELECT 
        index AS id,
        summ_id AS summoner_name,
        player_tag AS tag,
        puuid
    FROM public.form_responses_2
    """
    with engine.connect() as connection:
        return pd.read_sql(query, connection, index_col='id')


def update_puuid_in_form_responses_2(player_id: int, puuid: str) -> None:
    """Update a player's puuid in the form_responses_2 table."""
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE form_responses_2 SET puuid = :puuid WHERE index = :id"),
            {"puuid": puuid, "id": player_id}
        )


def get_puuid_from_riot(summoner_name: str, tag: str, api_key: str) -> Optional[str]:
    """Get puuid from Riot API using summoner name and tag."""
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tag}"
    headers = {"X-Riot-Token": api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("puuid")
        print(f"API Error for {summoner_name}#{tag}: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        print(f"Request failed for {summoner_name}#{tag}: {e}")
    
    return None


def process_players() -> Dict[int, str]:
    """Process all players, updating puuids as needed."""
    api_key = os.getenv("RIOT_API_KEY") or os.getenv("riot_api_key")
    if not api_key:
        raise ValueError("Riot API key not found in environment variables.")

    df = fetch_player_data()
    if df.empty:
        print("No player data found.")
        return {}

    puuid_map = {}
    updated_count = 0
    
    for player_id, row in df.iterrows():
        summoner_name = row['summoner_name']
        tag = row['tag']
        existing_puuid = row.get('puuid')
        
        if pd.notna(existing_puuid) and existing_puuid:
            puuid_map[player_id] = existing_puuid
            continue
            
        puuid = get_puuid_from_riot(summoner_name, tag, api_key)
        if puuid:
            puuid_map[player_id] = puuid
            update_puuid_in_form_responses_2(player_id, puuid)
            updated_count += 1
            print(f"Updated puuid for {summoner_name}#{tag}")
        else:
            print(f"Failed to get puuid for {summoner_name}#{tag}")
            puuid_map[player_id] = None
    
    if updated_count > 0:
        print(f"Updated {updated_count} player puuids.")
    
    return puuid_map


def main():
    print("Starting puuid update process...")
    
    ensure_puuid_table_exists()
    
    puuid_map = process_players()
    
    if puuid_map:
        print(f"Processed {len(puuid_map)} players.")
        df = pd.DataFrame(
            [(player_id, puuid) for player_id, puuid in puuid_map.items() if puuid],
            columns=['player_id', 'puuid']
        )
        print("\nSummary of puuids:")
        print(df)
    else:
        print("No players were processed.")


if __name__ == "__main__":
    main()