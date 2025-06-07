import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

engine = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")


def fetch_player_data(db_connection:object=engine) -> pd.DataFrame:
    """
    Fetches player data from the database and returns it as a DataFrame.
    
    Args:
        db_connection (object): SQLAlchemy engine object for database connection.
        
    Returns:
        pd.DataFrame: DataFrame containing player data.
    """


    with engine.connect() as connection:
        query = """
        SELECT summ_id, player_tag FROM public.form_responses
        """

        for row in query:
            summ_id = row['summ_id']
            player_tag = row['player_tag']
            print(f"Summoner ID: {summ_id}, Player Tag: {player_tag}")




def get_puuid(summoner_name:str, tag:str, db_connection:object=engine)-> str:
    
    load_dotenv()
    api_key = os.getenv("riot_api_key")
    if not api_key and not os.path.exists(".env"):
        raise ValueError("API key is not set in environment variables or .env file is missing.")
    if not api_key:
        raise ValueError("API key is not set in environment variables.")
    


    # with engine.connect() as connection:
    #     query = """
    #     SELECT summ_id, player_tag FROM public.form_responses
    #     """

    #     for row in query:
    #         summ_id = row['summ_id']
    #         player_tag = row['player_tag']
    #         print(f"Summoner ID: {summ_id}, Player Tag: {player_tag}")


    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tag}?api_key={api_key}"
    headers = {"X-Riot-Token": api_key}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("puuid")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


with engine.connect() as connection:
    query = """
    SELECT summ_id, player_tag FROM public.form_responses
    """

    for row in query:
        summ_id = row['summ_id']
        player_tag = row['player_tag']
        print(f"Summoner ID: {summ_id}, Player Tag: {player_tag}")