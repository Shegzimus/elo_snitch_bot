import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from datetime import datetime
import json
from typing import Tuple, Dict, List

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
def format_tier_rank(tier: str, rank: str)-> str:
    return f"{tier} {rank}" if rank else tier

# Constants for tier and division order
TIER_ORDER:list[str] = [
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

DIVISION_ORDER:list[str] = ["I", "II", "III", "IV"]

def get_current_date_time()-> Tuple[str, str]:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    return date_str, timestamp

def create_daily_directory(folder: str)-> Tuple[str, str]:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    date_str = datetime.now().strftime("%Y-%m-%d")
    data_dir = os.path.join(project_root, "data", folder)
    daily_dir = os.path.join(data_dir, date_str)
    os.makedirs(daily_dir, exist_ok=True)
    return data_dir, daily_dir
    
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
def get_top_changes(changes: List[Dict[str, any]], n: int=5)-> List[Dict[str, any]]:
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
    )-> Dict[str, any]:
    
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
        
        if new_div_idx > old_div_idx:
            division_change = f"{DIVISION_ORDER[old_div_idx]} -> {DIVISION_ORDER[new_div_idx]}"
        elif new_div_idx < old_div_idx:
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

def fetch_previous_elo(db_connection: object)-> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
        current_solo: pd.DataFrame = current_df[current_df['queue_type'] == 'RANKED_SOLO_5x5']
        current_flex: pd.DataFrame = current_df[current_df['queue_type'] == 'RANKED_FLEX_SR']
        previous_solo: pd.DataFrame = previous_df[previous_df['queue_type'] == 'RANKED_SOLO_5x5']
        previous_flex: pd.DataFrame = previous_df[previous_df['queue_type'] == 'RANKED_FLEX_SR']
        
        return current_solo, current_flex, previous_solo, previous_flex

def track_elo_changes()-> List[Dict[str, any]]:
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


def fetch_winrate()-> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
    wr_solo = []
    wr_flex = []
    with engine.connect() as connection:
        query:str = f"""
        WITH latest_scans AS (
            SELECT 
                fr.summ_id,
                eh.queue_type,
                eh.tier,
                eh.rank,
                eh.league_points,
                eh.wins,
                eh.losses,
                eh.timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY fr.summ_id, eh.queue_type 
                    ORDER BY eh.timestamp DESC
                ) AS scan_number
            FROM public.elo_history eh
            JOIN public.form_responses fr 
                ON eh.player_id = fr.index
        ),
        filtered_scans AS (
            SELECT *
            FROM latest_scans
            WHERE scan_number = 1
        )
        SELECT 
            summ_id,
            queue_type,
            tier,
            rank,
            league_points as lp,
            wins,
            losses,
            (wins + losses) AS total_games,
            ROUND(((wins::numeric / NULLIF(wins + losses, 0)) * 100)::numeric, 2) AS win_rate,
            timestamp
        FROM filtered_scans
        WHERE queue_type = 'RANKED_SOLO_5x5'
        ORDER BY win_rate DESC;
"""
        df: pd.DataFrame = pd.read_sql(query, connection)

        for _, row in df.iterrows():
            if row['queue_type'] == 'RANKED_SOLO_5x5':
                wr_solo.append({
                "summ_id": str(row['summ_id']),
                "tier": str(row['tier']),
                "rank": str(row['rank']),
                "wins": int(row['wins']),
                "losses": int(row['losses']),
                "total_games": int(row['total_games']),
                "win_rate": float(row['win_rate'])
            })
            else:
                wr_flex.append({
                "summ_id": str(row['summ_id']),
                "tier": str(row['tier']),
                "rank": str(row['rank']),
                "wins": int(row['wins']),
                "losses": int(row['losses']),
                "total_games": int(row['total_games']),
                "win_rate": float(row['win_rate'])
            })
        return wr_solo, wr_flex



def format_winrate_message(winrate_data: List[Dict[str, any]], queue_type: str = "Solo/Duo") -> str:
    """
    Format win rate data for WhatsApp messages.
    
    Args:
        winrate_data: List of dictionaries containing win rate information
        queue_type: Type of queue (e.g., "Solo/Duo" or "Flex")
        
    Returns:
        Formatted message string
    """
    if not winrate_data:
        return f"*{queue_type} Queue Win Rates:*\nNo win rate data available.\n"
    
    # Sort alphabetically by summoner name
    winrate_data.sort(key=lambda x: x['summ_id'].lower())
    
    message = f"*{queue_type} Queue Win Rates:*\n"
    
    for player in winrate_data:
        # Format tier and rank (e.g., "GOLD I" or "MASTER")
        tier_rank = f"{player['tier']} {player['rank']}" if player['rank'] else player['tier']
        
        # Format win rate and record (e.g., "60.0% | 12W-8L")
        win_rate = f"{player['win_rate']}%"
        record = f"{player['wins']}W-{player['losses']}L"
        
        message += f"{player['summ_id']} - {tier_rank} ({win_rate} | {record})\n"
    
    return message


def format_elo_changes_message(changes: list) -> str:
    message = MESSAGE_HEADER
    
    # Group changes by queue type
    queue_groups = {}
    for change in changes:
        queue = change['queue']
        if queue not in queue_groups:
            queue_groups[queue] = []
        queue_groups[queue].append(change)
    
    # Format each queue group
    for queue, queue_changes in queue_groups.items():
        # Get the display name from QUEUE_TYPES, or use the queue value directly if not found
        queue_display = QUEUE_TYPES.get(queue, queue)
        message += f"*{queue_display}:*\n"
        
        # Sort changes by tier and division
        queue_changes.sort(
            key=lambda x: (
                get_tier_index(x['tier'].split()[0]),
                get_division_index(x['tier'].split()[1]) if len(x['tier'].split()) > 1 else 0,
                -x['lp']
            )
        )
        
        for change in queue_changes:
            message += (
                f"{change['summ_id']} - {change['tier']} ({change['lp']} LP) "
                f"{change['change']}\n"
            )
        message += "\n"
    
    return message.strip()

def convert_to_python_types(data: List[Dict[str, any]], is_top_changes: bool = False) -> List[Dict[str, any]]:
    """
    Convert pandas/numpy types to native Python types
    
    Args:
        data: List of dictionaries containing change data
        is_top_changes: Whether the data is for top changes (includes additional fields)
        
    Returns:
        List of dictionaries with converted types
    """
    result: list = []
    for item in data:
        if is_top_changes:
            converted = {
                "rank": int(item["rank"]),
                "summ_id": str(item["summ_id"]),
                "queue": item["queue"],
                "tier": item["tier"],
                "lp": int(item["lp"]),
                "change": item["change"],
                "absolute_change": int(item["absolute_change"])
            }
        else:
            converted = {
                "summ_id": str(item["summ_id"]),
                "queue": item["queue"],
                "tier": item["tier"],
                "lp": int(item["lp"]),
                "change": item["change"]
            }
        result.append(converted)
    return result

def main()->None:
    # Track ELO changes
    changes = track_elo_changes()

    # Track winrate
    wr_solo, wr_flex = fetch_winrate()
    
    if changes:
        # Format message for WhatsApp bot
        message = format_elo_changes_message(changes)
        
        # Convert pandas types to Python types
        python_changes = convert_to_python_types(changes)
        
        # Calculate and convert top changes
        top_changes = get_top_changes(changes, 5)
        python_top_changes = convert_to_python_types(top_changes, is_top_changes=True)
        
        # Get current date and time
        date_str, timestamp = get_current_date_time()
    
        # Create daily directory if it doesn't exist
        data_dir, daily_dir = create_daily_directory("elo_changes")
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

    if wr_solo:
        message = format_winrate_message(wr_solo, queue_type="Solo/Duo")
        _, timestamp = get_current_date_time()
        data_dir, daily_dir = create_daily_directory("winrate/solo")
        latest_path = os.path.join(data_dir, "latest.json")
        filename = f"winrate_solo_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        with open(file_path, 'w') as f:
            json.dump({
                "message": message,
                "timestamp": timestamp,
                "changes": wr_solo
            }, f, indent=2)
        
        try:
            if os.path.exists(latest_path):
                os.remove(latest_path)
            os.symlink(os.path.abspath(file_path), latest_path)
        except Exception as e:
            print(f"Warning: Could not create/update latest symlink: {e}")
        
        print(f"Winrate tracked and saved. Message saved to {file_path}")
        print(f"Latest symlink updated to point to {filename}")
    else:
        print("No solo/duo winrate data available.")

    if wr_flex:
        message = format_winrate_message(wr_flex, queue_type="Flex")
        _, timestamp = get_current_date_time()
        data_dir, daily_dir = create_daily_directory("winrate/flex")
        latest_path = os.path.join(data_dir, "latest.json")
        
        filename = f"winrate_flex_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        with open(file_path, 'w') as f:
            json.dump({
                "message": message,
                "timestamp": timestamp,
                "changes": wr_flex
            }, f, indent=2)
        
        try:
            if os.path.exists(latest_path):
                os.remove(latest_path)
            os.symlink(os.path.abspath(file_path), latest_path)
        except Exception as e:
            print(f"Warning: Could not create/update latest symlink: {e}")
        
        print(f"Winrate tracked and saved. Message saved to {file_path}")
        print(f"Latest symlink updated to point to {filename}")
    else:
        print("No flex winrate data available.")

if __name__ == "__main__":
    main()
