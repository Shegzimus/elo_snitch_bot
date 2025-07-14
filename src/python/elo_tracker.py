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
    "IRON",
    "BRONZE",
    "SILVER",
    "GOLD",
    "PLATINUM",
    "EMERALD",
    "DIAMOND",
    "MASTER",
    "GRANDMASTER",
    "CHALLENGER"
]

DIVISION_ORDER = ["I", "II", "III", "IV"]

# Helper function to get tier index
def get_tier_index(tier: str)-> int:
    return TIER_ORDER.index(tier)

# Helper function to get division index
def get_division_index(division: str)-> int:
    if division is None:
        return 0
    return DIVISION_ORDER.index(division)

# 2nd order helper function to calculate absolute ELO change value
def calculate_absolute_change(change_str: str)-> int:
    """
    Calculate the absolute value of ELO change from change string
    Returns absolute LP change value
    """
    if not change_str:
        return 0
    
    # Extract LP change from string (first number with + or -)
    lp_str = change_str.split()[0]
    if lp_str.startswith("+") or lp_str.startswith("-"):
        try:
            return abs(int(lp_str))
        except ValueError:
            return 0
    return 0

# Function to get top N changes by absolute lp change
def get_top_changes(changes: list, n: int=5)-> list:
    """
    Get top N changes by absolute ELO change value
    Returns a list of top changes sorted by absolute change (descending)
    """
    if not changes:
        return []
    
    # Calculate absolute change for each change
    for change in changes:
        change['absolute_change'] = calculate_absolute_change(change['change'])
    
    # Sort changes by absolute change (descending)
    sorted_changes: list = sorted(changes, key=lambda x: x['absolute_change'], reverse=True)
    
    # Get top N changes
    top_changes: list = sorted_changes[:n]
    
    # Format top changes for display
    formatted_top = []
    for i, change in enumerate(top_changes, 1):
        formatted_top.append({
            'rank': i,
            'summ_id': change['summ_id'],
            'queue': change['queue'],
            'tier': change['tier'],
            'lp': change['lp'],
            'change': change['change'],
            'absolute_change': change['absolute_change']
        })
    
    return formatted_top

def calculate_elo_change(
    old_tier: str,
    old_division: str,
    old_lp: int,
    new_tier: str,
    new_division: str,
    new_lp: int
    )-> dict:
    
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
    lp_change: int = new_lp - old_lp if old_lp is not None else new_lp
    
    # Check for tier change
    old_tier_idx: int = get_tier_index(old_tier)
    new_tier_idx: int = get_tier_index(new_tier)
    
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

def fetch_puuid(db_connection: object)-> pd.DataFrame:
    with db_connection.connect() as connection:
        df = pd.read_sql("""
            SELECT fr.summ_id, p.puuid
            FROM public.puuid p
            JOIN public.form_responses fr ON p.id = fr.index
        """, connection)
        return df

def fetch_previous_elo(db_connection: object)-> pd.DataFrame:
    with db_connection.connect() as connection:
        # Fetch the last two scans from elo_history
        query = """
        SELECT 
            fr.summ_id,
            eh.queue_type,
            eh.tier,
            eh.rank,
            eh.league_points,
            eh.wins,
            eh.losses,
            eh.timestamp,
            ROW_NUMBER() OVER (PARTITION BY fr.summ_id, eh.queue_type ORDER BY eh.timestamp DESC) as scan_number
        FROM elo_history eh
        JOIN public.form_responses fr ON eh.player_id = fr.index
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

def track_elo_changes()-> list:
    puuid_df = fetch_puuid(engine)
    if puuid_df.empty:
        print("No PUUID data found.")
        return None
    
    current_solo_df, current_flex_df, previous_solo_df, previous_flex_df = fetch_previous_elo(engine)
    
    changes = []
    
    for _, row in puuid_df.iterrows():
        summ_id = row['summ_id']
        
        if not current_solo_df.empty:
            current_solo = current_solo_df[current_solo_df['summ_id'] == summ_id]
            if not current_solo.empty:
                previous_solo = previous_solo_df[previous_solo_df['summ_id'] == summ_id]
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
                            "summ_id": summ_id,
                            "queue": "Solo/Duo Queue",
                            "tier": format_tier_rank(current_solo['tier'].iloc[0], current_solo['rank'].iloc[0]),
                            "lp": current_solo['league_points'].iloc[0],
                            "change": change_info["total_change"]
                        })
        
        if not current_flex_df.empty:
            current_flex = current_flex_df[current_flex_df['summ_id'] == summ_id]
            if not current_flex.empty:
                previous_flex = previous_flex_df[previous_flex_df['summ_id'] == summ_id]
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
                            "summ_id": summ_id,
                            "queue": "Flex Queue",
                            "tier": format_tier_rank(current_flex['tier'].iloc[0], current_flex['rank'].iloc[0]),
                            "lp": current_flex['league_points'].iloc[0],
                            "change": change_info["total_change"]
                        })
    
    return changes

def get_player_progression(
    player_id: int, 
    queue_type: str, 
    days: int=30
    )-> pd.DataFrame:

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

def format_whatsapp_message(changes:list)-> str:
    message = MESSAGE_HEADER
    
    # Add top 5 changes section
    top_changes = get_top_changes(changes, 5)
    if top_changes:
        message += "\n*TOP 5 CHANGES:*\n"
        for change in top_changes:
            message += f"\u2022 #{change['rank']} (Player {change['summ_id']}): {change['tier']} ({change['lp']} LP) {change['change']}\n"
        message += "\n"
    
    # Add full changes section
    message += "*FULL CHANGES:*\n"
    
    # Group changes by queue
    queue_changes = {}
    for change in changes:
        queue = change['queue']
        if queue not in queue_changes:
            queue_changes[queue] = []
        queue_changes[queue].append(change)
    
    # Format each queue's changes
    for queue, changes in queue_changes.items():
        message += f"\u2022 {queue}:\n"
        for change in changes:
            message += f"  Player: {change['summ_id']}\n"
            message += f"  Rank: {change['tier']}\n"
            message += f"  LP: {change['lp']} ({change['change']})\n\n"
    
    return message

def main()->None:
    # Track ELO changes
    changes = track_elo_changes()
    
    if changes:
        # Format message for WhatsApp bot
        message = format_whatsapp_message(changes)
        
        # Convert pandas types to Python types
        python_changes = []
        for change in changes:
            python_change = {
                "summ_id": str(change["summ_id"]),
                "queue": change["queue"],
                "tier": change["tier"],
                "lp": int(change["lp"]),
                "change": change["change"]
            }
            python_changes.append(python_change)
        
        # Calculate top changes
        top_changes = get_top_changes(changes, 5)
        
        # Convert top changes to Python types
        python_top_changes = []
        for change in top_changes:
            python_top_change = {
                "rank": int(change["rank"]),
                "summ_id": str(change["summ_id"]),
                "queue": change["queue"],
                "tier": change["tier"],
                "lp": int(change["lp"]),
                "change": change["change"],
                "absolute_change": int(change["absolute_change"])
            }
            python_top_changes.append(python_top_change)
        
        # Get current date and time
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        
        # Get project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Create daily directory if it doesn't exist
        data_dir = os.path.join(project_root, "data", "elo_changes")
        daily_dir = os.path.join(data_dir, date_str)
        os.makedirs(daily_dir, exist_ok=True)
        
        # Create a symlink to the latest file
        latest_path = os.path.join(data_dir, "latest.json")
        
        # Save message to file in daily directory
        filename = f"elo_changes_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        with open(file_path, 'w') as f:
            json.dump({
                "message": message,
                "timestamp": timestamp,
                "changes": python_changes,
                "top_changes": python_top_changes
            }, f, indent=2)
        
        # Create or update symlink to latest file
        try:
            if os.path.exists(latest_path):
                os.remove(latest_path)
            os.symlink(os.path.abspath(file_path), latest_path)
        except Exception as e:
            print(f"Warning: Could not create/update latest symlink: {e}")
        
        print(f"ELO changes tracked and saved. Message saved to {file_path}")
        print(f"Latest symlink updated to point to {filename}")
    else:
        print("No ELO changes detected.")

if __name__ == "__main__":
    main()
