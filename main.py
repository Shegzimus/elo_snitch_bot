import requests
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load environment variables from .env file
load_dotenv()



def get_puuid(api_key:str, summoner_name:str, region:str="EUW")-> str:
    api_key = os.getenv("riot_api_key")
    if not api_key:
        raise ValueError("API key is not set in environment variables.")
    if not summoner_name:
        raise ValueError("Summoner name is required.")
    if not region:
        raise ValueError("Region is required.")
    
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{region}?api_key={api_key}"
    headers = {"X-Riot-Token": api_key}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("puuid")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
    




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

    return values




# resp = get_puuid(api_key, "Shegz")
# print(resp)

data = fetch_google_sheet_data()
print(data)