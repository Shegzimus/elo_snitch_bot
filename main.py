import requests
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from sqlalchemy import create_engine

# Load environment variables from .env file
load_dotenv()
engine = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db") # will only work if the docker DB container is running



    


def fetch_google_sheet_data(
        range_name:str="Form Responses 1!A:D", 
        credentials_path:str=".google/credentials.json"
        )-> None:
    sheet_id = os.getenv("google_sheet_id")
    
    if not sheet_id:
        raise ValueError("Google Sheet ID is not set in environment variables.")
    if not credentials_path or not os.path.exists(credentials_path):
        raise ValueError("Credentials path is not set or does not exist.")
    if not sheet_id:
        raise ValueError("Google Sheet ID is not set in environment variables.")

    # Define the required scope
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    # Load credentials from the service account file
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES)

    # Build the Sheets API service
    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    values = result.get('values', [])

    # Minor transformations
    values_df = pd.DataFrame(values[1:], columns=values[0])  # Convert to DataFrame
    values_df.rename(columns={
        'Timestamp': 'timestamp',  
        "Tag line (e.g #EUW) ": "player_tag",
        "Summoner ID (case sensitive)": "summ_id",
        "Region": "region"
    }, inplace=True)

    values_df['timestamp'] = pd.to_datetime(values_df['timestamp'], errors='coerce')  # Convert timestamp to datetime
    values_df['player_tag'] = values_df['player_tag'].str.lstrip("#")  # Strip whitespace from player_tag

    return values_df


# resp = get_puuid(api_key, "Shegz")
# print(resp)

# data = fetch_google_sheet_data()
# print(data)


def load_to_db(df: pd.DataFrame, table_name: str, db_connection:object= engine) -> None:   # using a connection object argument instead of a hard-coded engine in case we want to use a cloud database in the future

    
    if df.empty:
        print("No data to load.")
        return
    
    df.head(0).to_sql(name=table_name, con=db_connection, if_exists='replace')
    print("Table header created successfully")

    df.to_sql(name=table_name, con=db_connection, if_exists='replace')

    return None


# df.to_csv("form_responses.csv", index=False)  # Save to CSV for debugging
# print(df.head(0))
# print(df.columns)


df = fetch_google_sheet_data()
load_to_db(df, table_name="form_responses", db_connection=engine)  # Load to database