import requests
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from datetime import datetime
import json

load_dotenv()

# Create database connection
engine = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db")

# Constants for message formatting
MESSAGE_HEADER = "*ELO CHANGES UPDATE*\n\n"
QUEUE_TYPES = {
    "RANKED_SOLO_5x5": "Solo/Duo Queue",
    "RANKED_FLEX_SR": "Flex Queue"
}

# Helper function to format tier/rank
def format_tier_rank(tier, rank):
    return f"{tier} {rank}" if rank else tier

# Helper function to calculate ELO change
def calculate_elo_change(old_elo, new_elo):
    if old_elo is None:
        return f"+{new_elo}"
    return f"+{new_elo - old_elo}" if new_elo > old_elo else f"-{old_elo - new_elo}"

def fetch_puuid(db_connection):
    with db_connection.connect() as connection:
        df = pd.read_sql("SELECT id, puuid, name FROM public.puuid", connection)
        return df

def fetch_previous_elo(db_connection):
    with db_connection.connect() as connection:
        # Fetch the latest ELO data
        solo_df = pd.read_sql("SELECT * FROM solo_queue", connection)
        flex_df = pd.read_sql("SELECT * FROM flex_queue", connection)
        return solo_df, flex_df

def track_elo_changes():
    api_key = os.getenv("riot_api_key")
    
    # Fetch current data
    puuid_df = fetch_puuid(engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return None
    
    # Fetch previous ELO data
    previous_solo_df, previous_flex_df = fetch_previous_elo(engine)
    
    # Store current ELO data
    current_solo_data = []
    current_flex_data = []
    
    # Track changes
    changes = []
    
    for _, row in puuid_df.iterrows():
        puuid = row['puuid']
        player_name = row['name']
        
        url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}"
        headers = {"X-Riot-Token": api_key}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for queue in data:
                queue_type = queue["queueType"]
                tier = queue["tier"]
                rank = queue["rank"]
                lp = queue["leaguePoints"]
                store_elo_snapshot(queue)
                
                # Find previous ELO for this player and queue
                previous_data = None
                if queue_type == "RANKED_SOLO_5x5":
                    previous_data = previous_solo_df[previous_solo_df["summonerId"] == puuid]
                else:
                    previous_data = previous_flex_df[previous_flex_df["summonerId"] == puuid]
                
                previous_lp = None if previous_data.empty else previous_data["leaguePoints"].iloc[0]
                
                # Store current data
                if queue_type == "RANKED_SOLO_5x5":
                    current_solo_data.append(queue)
                else:
                    current_flex_data.append(queue)
                
                # Track changes
                if previous_lp is not None and lp != previous_lp:
                    change = calculate_elo_change(previous_lp, lp)
                    changes.append({
                        "player": player_name,
                        "queue": QUEUE_TYPES[queue_type],
                        "tier": format_tier_rank(tier, rank),
                        "lp": lp,
                        "change": change
                    })
                    
        except Exception as e:
            print(f"Error fetching data for {puuid}: {str(e)}")
            continue
    
    # Save current data to database
    if current_solo_data:
        pd.DataFrame(current_solo_data).to_sql(
            "solo_queue", engine, if_exists='replace', index=False
        )
    
    if current_flex_data:
        pd.DataFrame(current_flex_data).to_sql(
            "flex_queue", engine, if_exists='replace', index=False
        )
    
    return changes

def store_elo_snapshot(data):
    """Store a complete snapshot of all players' ELO data"""
    timestamp = datetime.now()
    for entry in data:
        entry['timestamp'] = timestamp
        # Insert into elo_history table

def get_player_progression(player_id, queue_type, days=30):
    """Get ELO progression for a player over time"""
    query = """
    SELECT 
        timestamp,
        tier,
        rank,
        league_points,
        wins,
        losses
    FROM elo_history
    WHERE player_id = :player_id
    AND queue_type = :queue_type
    AND timestamp >= NOW() - INTERVAL :days days
    ORDER BY timestamp ASC
    """
    return pd.read_sql(query, engine, params={
        'player_id': player_id,
        'queue_type': queue_type,
        'days': days
    })

def calculate_progress_metrics(progress_data):
    """Calculate useful metrics from progression data"""
    return {
        'total_lp_change': progress_data['league_points'].diff().sum(),
        'average_daily_change': progress_data['league_points'].diff().mean(),
        'win_rate': (progress_data['wins'].diff() / 
                    (progress_data['wins'].diff() + progress_data['losses'].diff())).mean(),
        'rank_changes': len(progress_data[progress_data['tier'].shift() != progress_data['tier']])
    }

def format_whatsapp_message(changes):
    if not changes:
        return "No ELO changes detected."
    
    message = MESSAGE_HEADER
    for change in changes:
        message += f"• {change['player']} ({change['queue']}):\n"
        message += f"  Rank: {change['tier']}\n"
        message += f"  LP: {change['lp']} ({change['change']})\n\n"
    
    return message

def main():
    # Track ELO changes
    changes = track_elo_changes()
    
    if changes:
        # Format message for WhatsApp bot
        message = format_whatsapp_message(changes)
        
        # Save message to file for bot to read
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"elo_changes_{timestamp}.json", 'w') as f:
            json.dump({
                "message": message,
                "timestamp": timestamp,
                "changes": changes
            }, f, indent=2)
        
        print(f"ELO changes tracked and saved. Message saved to elo_changes_{timestamp}.json")
    else:
        print("No ELO changes detected.")

if __name__ == "__main__":
    main()
