import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
# Create a database connection
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
        return [], []  # Return empty lists instead of DataFrame
    
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
            # Add None for failed requests to maintain list alignment
            solo_queue_elo.append(None)
            flex_queue_elo.append(None)

    return solo_queue_elo, flex_queue_elo


def main():
    solo_queue_elo, flex_queue_elo = elo_check()

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
        solo_df.to_sql(name="solo_queue", con=engine, if_exists='replace', index=False)
        print("Solo queue data loaded successfully into the database.")
    else:
        print("No solo queue data to load.")
        
    if not flex_df.empty:
        flex_df.to_sql(name="flex_queue", con=engine, if_exists='replace', index=False)
        print("Flex queue data loaded successfully into the database.")
    else:
        print("No flex queue data to load.")

if __name__ == "__main__":
    main()