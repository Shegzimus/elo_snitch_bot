import requests
import os
import json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
# Create a database connection
engine:object = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")

def fetch_puuid(db_connection: object) -> pd.DataFrame:
    with db_connection.connect() as connection:
        df: pd.DataFrame = pd.read_sql(
            "SELECT id, puuid FROM public.puuid LIMIT 5", 
            connection, 
            index_col='id')
        if df.empty:
            print("No PUUID data found.")
        else:
            print(f"Fetched {len(df)} rows of PUUID data.")
        return df



def mastery_check():
    mastery_data = []
    milestone_data = []

    api_key: str = os.getenv("riot_api_key")
    if not api_key:
        raise ValueError("API key is not set in environment variables.")

    puuid_df: pd.DataFrame = fetch_puuid(db_connection=engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return []  # Return empty list instead of DataFrame

    
    for idx, row in puuid_df.iterrows():
        id_val = idx  # Renamed from 'id' to avoid shadowing built-in
        puuid = row['puuid']

        url = f"https://euw1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?api_key={api_key}"
        headers = {"X-Riot-Token": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json() if response.status_code == 200 else []

            if response.status_code == 200:
                for item in data:
                    # Main champion info
                    mastery_data.append({
                        'puuid': item['puuid'],
                        'championId': item['championId'],
                        'championLevel': item['championLevel'],
                        'championPoints': item['championPoints'],
                        'lastPlayTime': datetime.fromtimestamp(item['lastPlayTime'] / 1000),
                        'championPointsSinceLastLevel': item['championPointsSinceLastLevel'],
                        'championPointsUntilNextLevel': item['championPointsUntilNextLevel'],
                        'markRequiredForNextLevel': item['markRequiredForNextLevel'],
                        'tokensEarned': item['tokensEarned'],
                        'championSeasonMilestone': item['championSeasonMilestone']
                    })

                    # Milestone grades for the champion
                    for grade in item.get('milestoneGrades', []):
                        milestone_data.append({
                            'puuid': item['puuid'],
                            'championId': item['championId'],
                            'grade': grade
                        })

                mastery_df = pd.DataFrame(mastery_data)
                milestone_df = pd.DataFrame(milestone_data)

                return mastery_df, milestone_df












            else:
                print(f"Failed for ID: {id_val}, Status code: {response.status_code}, Response: {response.text}")
                mastery_data.append(None)

        except requests.RequestException as e:
            print(f"Request failed for ID: {id_val}, Error: {e}")
            mastery_data.append(None)

    print("Mastery data fetched successfully.")
    return mastery_data


def main():
    # data = mastery_check()
    # df = pd.DataFrame(data)  # Convert list of dictionaries to DataFrame
    # print(df.head())

    puuid:str = os.getenv("shegz_puuid")
    api_key:str = os.getenv("riot_api_key")
    count:int = 5  # Number of top champion masteries to fetch
    url:str = f"https://euw1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}&api_key={api_key}"
    headers:dict = {"X-Riot-Token": api_key}

    mastery_data = []
    milestone_data = []


    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        for item in data:
            # Main champion info
            mastery_data.append({
                'puuid': item['puuid'],
                'championId': item['championId'],
                'championLevel': item['championLevel'],
                'championPoints': item['championPoints'],
                'lastPlayTime': datetime.fromtimestamp(item['lastPlayTime'] / 1000),
                'championPointsSinceLastLevel': item['championPointsSinceLastLevel'],
                'championPointsUntilNextLevel': item['championPointsUntilNextLevel'],
                'markRequiredForNextLevel': item['markRequiredForNextLevel'],
                'tokensEarned': item['tokensEarned'],
                'championSeasonMilestone': item['championSeasonMilestone']
            })

            # Milestone grades for the champion
            for grade in item.get('milestoneGrades', []):
                milestone_data.append({
                    'puuid': item['puuid'],
                    'championId': item['championId'],
                    'grade': grade
                })

        mastery_df = pd.DataFrame(mastery_data)
        milestone_df = pd.DataFrame(milestone_data)

        print(mastery_df)

        print(milestone_df)
    else:
        print(f"Failed to fetch data: {response.status_code}, {response.text}")









if __name__ == "__main__":
    main()