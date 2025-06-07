import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

api_key = os.getenv("riot_api_key")

def get_puuid(api_key, summoner_name, region="EUW"):
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{region}?api_key={api_key}"
    headers = {"X-Riot-Token": api_key}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("puuid")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
    

resp = get_puuid(api_key, "Shegz")
print(resp)