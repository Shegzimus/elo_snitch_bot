import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
engine:object = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")


def fetch_puuid(db_connection: object) -> pd.DataFrame:
    with db_connection.connect() as connection:
        df: pd.DataFrame = pd.read_sql(
            "SELECT id, puuid FROM public.puuid", 
            connection, 
            index_col='id')
        if df.empty:
            print("No PUUID data found.")
        else:
            print(f"Fetched {len(df)} rows of PUUID data.")
        return df

def elo_check() -> tuple[list, list]:
    solo_queue_elo: list = []
    flex_queue_elo: list = []
    api_key: str = os.getenv("riot_api_key")

    puuid_df: pd.DataFrame = fetch_puuid(db_connection=engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return [], []
    
    for idx, row in puuid_df.iterrows():
        id_val = idx  # Renamed from 'id' to avoid shadowing built-in
        puuid = row['puuid']

        url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}"
        headers = {"X-Riot-Token": api_key}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            
            # Find solo queue and flex queue data
            solo_queue = next((item for item in data if item["queueType"] == "RANKED_SOLO_5x5"), None)
            flex_queue = next((item for item in data if item["queueType"] == "RANKED_FLEX_SR"), None)
            
            solo_queue_elo.append(solo_queue)
            flex_queue_elo.append(flex_queue)
        else:
            print(f"Failed for ID: {id_val}, Status code: {response.status_code}, Response: {response.text}")
            solo_queue_elo.append(None)
            flex_queue_elo.append(None)

    return solo_queue_elo, flex_queue_elo, puuid_df


def main():
    solo_queue_elo, flex_queue_elo, puuid_df = elo_check()

    # Filter out None values and create DataFrames directly from the list of dictionaries
    solo_queue_data = [item for item in solo_queue_elo if item is not None]
    flex_queue_data = [item for item in flex_queue_elo if item is not None]
    
    # Create DataFrames from the filtered data
    solo_df = pd.DataFrame(solo_queue_data)
    flex_df = pd.DataFrame(flex_queue_data)
    
    print("Solo Queue Data:")
    print(solo_df)
    print("\nFlex Queue Data:")
    print(flex_df)
    
    # Only proceed if we have data
    if not solo_df.empty:
        # Filter puuid_df to match the length of solo_df
        valid_player_ids = [puuid_df.index[i] for i, elo in enumerate(solo_queue_elo) if elo is not None]
        # Add player_id, queue_type, and timestamp columns
        solo_df['queue_type'] = 'RANKED_SOLO_5x5'
        solo_df['player_id'] = valid_player_ids
        solo_df['timestamp'] = pd.Timestamp.now()
        # Select only the columns we need
        solo_df = solo_df[['timestamp','player_id', 'queue_type', 'tier', 'rank', 'leaguePoints', 'wins', 'losses', ]]
        # Rename columns to match the database schema
        solo_df = solo_df.rename(columns={'leaguePoints': 'league_points'})
        # Append to elo_history table
        solo_df.to_sql(name="elo_history", con=engine, if_exists='append', index=False)
        print("Solo queue data loaded successfully into the database.")
    else:
        print("No solo queue data to load.")
        
    if not flex_df.empty:
        # Filter puuid_df to match the length of flex_df
        valid_player_ids = [puuid_df.index[i] for i, elo in enumerate(flex_queue_elo) if elo is not None]
        # Add player_id, queue_type, and timestamp columns
        flex_df['queue_type'] = 'RANKED_FLEX_SR'
        flex_df['player_id'] = valid_player_ids
        flex_df['timestamp'] = pd.Timestamp.now()
        # Select only the columns we need
        flex_df = flex_df[['timestamp','player_id', 'queue_type', 'tier', 'rank', 'leaguePoints', 'wins', 'losses' ]]
        # Rename columns to match the database schema
        flex_df = flex_df.rename(columns={'leaguePoints': 'league_points'})
        # Append to elo_history table
        flex_df.to_sql(name="elo_history", con=engine, if_exists='append', index=False)
        print("Flex queue data loaded successfully into the database.")
    else:
        print("No flex queue data to load.")

if __name__ == "__main__":
    main()