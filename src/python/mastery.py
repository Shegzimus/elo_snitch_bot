import requests
import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv(dotenv_path=os.path.join("config", ".env"))

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

def mastery_check():
    """
    Fetches champion mastery data for all PUUIDs in the database.
    Returns a DataFrame with mastery information or empty DataFrame if no data.
    """
    mastery_data = []

    api_key: str = os.getenv("riot_api_key")
    if not api_key:
        raise ValueError("API key is not set in environment variables.")

    puuid_df: pd.DataFrame = fetch_puuid(db_connection=engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return pd.DataFrame()  # Return empty DataFrame consistently
    
    for idx, row in puuid_df.iterrows():
        puuid = row['puuid']
        url = f"https://euw1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?api_key={api_key}"
        headers = {"X-Riot-Token": api_key}    
        try:
            response = requests.get(url, headers=headers)      
            if response.status_code == 200:
                data = response.json()
                
                # Process each champion mastery entry
                for item in data:
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
                    
                print(f"Successfully fetched mastery data for PUUID: {puuid}")
                
            else:
                print(f"Failed for PUUID: {puuid}, Status code: {response.status_code}")
                if response.status_code == 429:
                    print("Rate limit exceeded. Consider adding delays between requests.")
                elif response.status_code == 403:
                    print("Forbidden - check your API key permissions.")

        except requests.RequestException as e:
            print(f"Request failed for PUUID: {puuid}, Error: {e}")
        except KeyError as e:
            print(f"Missing expected field in API response for PUUID: {puuid}, Field: {e}")
        except Exception as e:
            print(f"Unexpected error for PUUID: {puuid}, Error: {e}")

    # Create DataFrame from collected data
    if mastery_data:
        mastery_df = pd.DataFrame(mastery_data)
        print(f"Mastery data fetched successfully. Total records: {len(mastery_df)}")
        return mastery_df
    else:
        print("No mastery data was successfully fetched.")
        return pd.DataFrame()

def main():
    mastery_data= mastery_check()
    mastery_df = pd.DataFrame(mastery_data)
    if not mastery_df.empty:
        mastery_df.to_sql(name="mastery", con=engine, if_exists='replace', index=False)

    if not mastery_df.empty:
        print(mastery_df.head())
        print("Mastery data loaded successfully into the database.")

    else:
        print("No mastery or milestone data to load.")



if __name__ == "__main__":
    main()