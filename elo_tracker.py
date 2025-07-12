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

# Constants for tier and division order
TIER_ORDER = [
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"
]

DIVISION_ORDER = ["I", "II", "III", "IV"]

# Helper function to get tier index
def get_tier_index(tier):
    return TIER_ORDER.index(tier)

# Helper function to get division index
def get_division_index(division):
    if division is None:
        return 0
    return DIVISION_ORDER.index(division)

# Helper function to calculate ELO change
def calculate_elo_change(old_tier, old_division, old_lp, new_tier, new_division, new_lp):
    """
    Calculate comprehensive ELO change including tier and division changes
    Returns a dictionary with detailed change information
    """
    if old_tier is None:
        # First time tracking - just show current tier
        return {
            "lp_change": new_lp,
            "tier_change": None,
            "division_change": None,
            "total_change": f"+{new_lp} LP ({new_tier} {new_division if new_division else ''})"
        }
    
    # Calculate LP change
    lp_change = new_lp - old_lp if old_lp is not None else new_lp
    
    # Check for tier change
    old_tier_idx = get_tier_index(old_tier)
    new_tier_idx = get_tier_index(new_tier)
    
    tier_change = None
    if new_tier_idx > old_tier_idx:
        tier_change = "PROMOTED"
    elif new_tier_idx < old_tier_idx:
        tier_change = "DEMOTED"
    
    # Check for division change
    division_change = None
    if old_tier == new_tier and old_division and new_division: # Skips division comparison if elo is MASTER and above
        old_div_idx = get_division_index(old_division)
        new_div_idx = get_division_index(new_division)
        
        if new_div_idx < old_div_idx:
            division_change = f"{DIVISION_ORDER[old_div_idx]} -> {DIVISION_ORDER[new_div_idx]}"
        elif new_div_idx > old_div_idx:
            division_change = f"{DIVISION_ORDER[new_div_idx]} -> {DIVISION_ORDER[old_div_idx]}"
    
    # Format total change message
    change_parts = []
    
    # Add LP change
    if lp_change != 0:
        change_parts.append(f"{lp_change:+} LP")
    
    # Add tier change
    if tier_change:
        change_parts.append(f"{tier_change} from {old_tier} to {new_tier}")
    
    # Add division change
    if division_change:
        change_parts.append(f"Division {division_change}")
    
    # If no changes, just show current tier
    if not change_parts:
        change_parts.append(f"{new_tier} {new_division if new_division else ''}")
    
    return {
        "lp_change": lp_change,
        "tier_change": tier_change,
        "division_change": division_change,
        "total_change": " - ".join(change_parts)
    }

def fetch_puuid(db_connection):
    with db_connection.connect() as connection:
        df = pd.read_sql("SELECT id, puuid FROM public.puuid", connection)
        return df

def fetch_previous_elo(db_connection):
    with db_connection.connect() as connection:
        # Fetch the last two scans from elo_history
        query = """
        SELECT 
            player_id as id,
            queue_type,
            tier,
            rank,
            league_points,
            wins,
            losses,
            timestamp,
            ROW_NUMBER() OVER (PARTITION BY player_id, queue_type ORDER BY timestamp DESC) as scan_number
        FROM elo_history
        """
        
        df = pd.read_sql(query, connection)
        
        # Separate into current and previous scans
        current_df = df[df['scan_number'] == 1]
        previous_df = df[df['scan_number'] == 2]
        
        # Separate by queue type
        current_solo = current_df[current_df['queue_type'] == 'RANKED_SOLO_5x5']
        current_flex = current_df[current_df['queue_type'] == 'RANKED_FLEX_SR']
        previous_solo = previous_df[previous_df['queue_type'] == 'RANKED_SOLO_5x5']
        previous_flex = previous_df[previous_df['queue_type'] == 'RANKED_FLEX_SR']
        
        return current_solo, current_flex, previous_solo, previous_flex

def track_elo_changes():
    # Fetch current data
    puuid_df = fetch_puuid(engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return None
    
    # Fetch previous ELO data
    current_solo_df, current_flex_df, previous_solo_df, previous_flex_df = fetch_previous_elo(engine)
    
    # Track changes
    changes = []
    
    # For each player in the database
    for _, row in puuid_df.iterrows():
        player_id = row['id']
        
        # Process solo queue
        if not current_solo_df.empty:
            current_solo = current_solo_df[current_solo_df['id'] == player_id]
            if not current_solo.empty:
                previous_solo = previous_solo_df[previous_solo_df['id'] == player_id]
                if not previous_solo.empty:
                    change_info = calculate_elo_change(
                        old_tier=previous_solo['tier'].iloc[0],
                        old_division=previous_solo['rank'].iloc[0],
                        old_lp=previous_solo['league_points'].iloc[0],
                        new_tier=current_solo['tier'].iloc[0],
                        new_division=current_solo['rank'].iloc[0],
                        new_lp=current_solo['league_points'].iloc[0]
                    )
                    
                    if change_info["total_change"] != f"{current_solo['tier'].iloc[0]} {current_solo['rank'].iloc[0] if current_solo['rank'].iloc[0] else ''}":
                        changes.append({
                            "id": player_id,
                            "queue": "Solo/Duo Queue",
                            "tier": format_tier_rank(current_solo['tier'].iloc[0], current_solo['rank'].iloc[0]),
                            "lp": current_solo['league_points'].iloc[0],
                            "change": change_info["total_change"]
                        })
        
        # Process flex queue
        if not current_flex_df.empty:
            current_flex = current_flex_df[current_flex_df['id'] == player_id]
            if not current_flex.empty:
                previous_flex = previous_flex_df[previous_flex_df['id'] == player_id]
                if not previous_flex.empty:
                    change_info = calculate_elo_change(
                        old_tier=previous_flex['tier'].iloc[0],
                        old_division=previous_flex['rank'].iloc[0],
                        old_lp=previous_flex['league_points'].iloc[0],
                        new_tier=current_flex['tier'].iloc[0],
                        new_division=current_flex['rank'].iloc[0],
                        new_lp=current_flex['league_points'].iloc[0]
                    )
                    
                    if change_info["total_change"] != f"{current_flex['tier'].iloc[0]} {current_flex['rank'].iloc[0] if current_flex['rank'].iloc[0] else ''}":
                        changes.append({
                            "id": player_id,
                            "queue": "Flex Queue",
                            "tier": format_tier_rank(current_flex['tier'].iloc[0], current_flex['rank'].iloc[0]),
                            "lp": current_flex['league_points'].iloc[0],
                            "change": change_info["total_change"]
                        })
    
    return changes

def store_elo_snapshot(data, db_connection):
    """
    Store a complete snapshot of all players' ELO data in the elo_history table
    
    Args:
        data: List of dictionaries containing ELO data
        db_connection: SQLAlchemy database connection
    """
    timestamp = datetime.now()
    
    # First get mapping of summonerId to database id
    summoner_ids = [entry.get('summonerId') for entry in data if entry.get('summonerId')]
    if not summoner_ids:
        print("No summoner IDs found in data")
        return
    
    # Get player IDs from database
    with db_connection.connect() as connection:
        result = pd.read_sql(
            "SELECT id, puuid FROM public.puuid WHERE puuid IN :summoner_ids",
            connection,
            params={'summoner_ids': tuple(summoner_ids)}
        )
        
        # Create mapping of summonerId to database id
        player_map = dict(zip(result['puuid'], result['id']))
    
    # Create a list of dictionaries for bulk insert
    history_data = []
    
    for entry in data:
        summoner_id = entry.get('summonerId')
        if not summoner_id or summoner_id not in player_map:
            continue
            
        history_data.append({
            'player_id': player_map[summoner_id],
            'queue_type': entry.get('queueType'),
            'tier': entry.get('tier'),
            'rank': entry.get('rank'),
            'league_points': entry.get('leaguePoints', 0),
            'wins': entry.get('wins', 0),
            'losses': entry.get('losses', 0),
            'timestamp': timestamp
        })
    
    # Bulk insert into elo_history table
    if history_data:
        df = pd.DataFrame(history_data)
        df.to_sql('elo_history', db_connection, if_exists='append', index=False)
        print(f"Stored {len(history_data)} ELO snapshots in elo_history table")
    else:
        print("No ELO data to store")

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
    
    # Fetch player names from database
    player_ids = [change['id'] for change in changes]
    with engine.connect() as connection:
        player_names = pd.read_sql(
            f"SELECT id FROM public.puuid WHERE id IN ({','.join(map(str, player_ids))})",
            connection
        )
        player_names_dict = dict(zip(player_names['id'], player_names['id']))
    
    message = MESSAGE_HEADER
    for change in changes:
        player_name = player_names_dict.get(change['id'], f"Player {change['id']}")
        message += f"• {player_name} ({change['queue']}):\n"
        message += f"  Rank: {change['tier']}\n"
        message += f"  LP: {change['lp']} ({change['change']})\n\n"
    
    return message

def main():
    # Track ELO changes
    changes = track_elo_changes()
    
    if changes:
        # Format message for WhatsApp bot
        message = format_whatsapp_message(changes)
        
        # Convert pandas types to Python types
        python_changes = []
        for change in changes:
            python_change = {
                "id": int(change["id"]),
                "queue": change["queue"],
                "tier": change["tier"],
                "lp": int(change["lp"]),
                "change": change["change"]
            }
            python_changes.append(python_change)
        
        # Save message to file for bot to read
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"elo_changes_{timestamp}.json", 'w') as f:
            json.dump({
                "message": message,
                "timestamp": timestamp,
                "changes": python_changes
            }, f, indent=2)
        
        print(f"ELO changes tracked and saved. Message saved to elo_changes_{timestamp}.json")
    else:
        print("No ELO changes detected.")

if __name__ == "__main__":
    main()
