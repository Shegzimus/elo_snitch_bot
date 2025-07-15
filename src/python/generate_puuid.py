import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(dotenv_path="config/.env")
# Create a database connection
engine = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")


def fetch_player_data(db_connection: object) -> pd.DataFrame:
    with db_connection.connect() as connection:
        df = pd.read_sql(
            "SELECT index AS id, " \
            "summ_id AS summoner_name, " \
            "player_tag as tag FROM public.form_responses", 
            connection, 
            index_col='id')
        return df


def get_puuid() -> dict:
    id_puuid_map = {}  # Dictionary to store id and puuid mapping
    api_key = os.getenv("riot_api_key")
    
    if not api_key and not os.path.exists("config/.env"):
        raise ValueError("API key is not set in environment variables or .env file is missing.")
    if not api_key:
        raise ValueError("API key is not set in environment variables.")

    df = fetch_player_data(db_connection=engine)
    if df.empty:
        print("No player data found.")
        return {}  # Return empty dict instead of None

    for idx, row in df.iterrows():
        id_val = idx  # Renamed from 'id' to avoid shadowing built-in
        summoner_name = row['summoner_name']
        tag = row['tag']

        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tag}?api_key={api_key}"
        headers = {"X-Riot-Token": api_key}
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                puuid = data.get("puuid")
                id_puuid_map[id_val] = puuid
            else:
                print(f"Failed for ID: {id_val}, Status code: {response.status_code}, Response: {response.text}")
                id_puuid_map[id_val] = None
                
        except requests.RequestException as e:
            print(f"Request failed for ID: {id_val}, Error: {e}")
            id_puuid_map[id_val] = None

    return id_puuid_map

def main():
    puuid_map = get_puuid()
    if puuid_map:
        print("PUUID Map:", puuid_map)
    else:
        print("No PUUIDs found.")
    df = pd.DataFrame(list(puuid_map.items()), columns=['id', 'puuid'])
    print(df)
    
    df.head(0).to_sql(name="puuid", con=engine, if_exists='replace')
    print("Table header created successfully")

    df.to_sql(name="puuid", con=engine, if_exists='replace')
if __name__ == "__main__":
    main()