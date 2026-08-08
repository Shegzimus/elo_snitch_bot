import os
import pandas as pd
from datetime import datetime
import json
from typing import Tuple, Dict, List

import config
from logger_config import setup_logger

logger = setup_logger(__name__, 'elo_tracker.log')

engine = config.get_engine()

# Constants for message formatting
MESSAGE_HEADER = "*ELO CHANGES UPDATE*\n\n"
QUEUE_TYPES = {
    "RANKED_SOLO_5x5": "Solo/Duo Queue",
    "RANKED_FLEX_SR": "Flex Queue"
}

def format_tier_rank(tier: str, rank: str)-> str:
    return f"{tier} {rank}" if rank else tier

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

DIVISION_ORDER:list[str] = ["IV", "III", "II", "I"]

DIVISIONS_PER_TIER: int = 4
LP_PER_DIVISION: int = 100
LP_PER_TIER: int = DIVISIONS_PER_TIER * LP_PER_DIVISION

# Master, Grandmaster and Challenger have no divisions and share one continuous
# LP pool -- the upper two are percentile cutoffs, not separate LP ranges.
APEX_TIERS: frozenset = frozenset({"MASTER", "GRANDMASTER", "CHALLENGER"})

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
    
def write_snapshot(daily_path: str, latest_path: str, payload: Dict[str, any])-> None:
    """Write a snapshot to its dated file and mirror it to latest.json.

    latest.json is a plain copy rather than a symlink: os.symlink needs the
    SeCreateSymbolicLink privilege on Windows, so the symlink always failed and
    latest.json never actually existed.
    """
    for path in (daily_path, latest_path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)

def get_tier_index(tier: str)-> int:
    if tier not in TIER_ORDER:
        raise ValueError(f"Unknown tier: {tier!r}. Expected one of {TIER_ORDER}")
    return TIER_ORDER.index(tier)

def get_division_index(division: str)-> int:
    """
    Get division index where higher index = better division
    IV=0 (worst), III=1, II=2, I=3 (best)
    """
    if division is None:
        return 0
    if division not in DIVISION_ORDER:
        raise ValueError(f"Unknown division: {division!r}. Expected one of {DIVISION_ORDER}")
    return DIVISION_ORDER.index(division)

def ladder_points(tier: str, division: str, lp: int)-> int:
    """Absolute position on the ranked ladder, expressed in LP.

    Riot's league_points restarts near zero on every promotion, so subtracting
    two raw values reports a tier climb as a large loss: Gold I 98 LP ->
    Platinum IV 4 LP looks like -94 LP when the player in fact gained 6. Mapping
    both ends onto one monotonic scale first makes the difference mean what
    people expect.

    Apex tiers all use the Master base, so a Grandmaster on 100 LP correctly
    outranks a Master on 90 rather than being pushed a whole tier above them.

    A division spans 100 points, which makes "GOLD IV 100 LP" and "GOLD III
    0 LP" score identically. That is deliberate: 100 LP is the promotion
    threshold, so crossing it is a zero-LP move, and keeping the divisions
    exactly 100 wide is what makes the reported delta equal the LP the player
    actually gained. Widening them to 101 would restore strict monotonicity at
    the cost of every number being wrong by one per division crossed.
    """
    if tier in APEX_TIERS:
        base = TIER_ORDER.index("MASTER") * LP_PER_TIER
        return base + (lp or 0)
    return (
        get_tier_index(tier) * LP_PER_TIER
        + get_division_index(division) * LP_PER_DIVISION
        + (lp or 0)
    )

def get_top_changes(changes: List[Dict[str, any]], n: int=5)-> List[Dict[str, any]]:
    """
    Get top N changes by absolute ladder movement.
    Returns a list of top changes sorted by absolute change (descending)
    """
    if not changes:
        return []

    for change in changes:
        change['absolute_change'] = abs(change.get('lp_change', 0))

    # Ties broken by name so the ordering is stable run to run.
    sorted_changes: list = sorted(
        changes,
        key=lambda x: (-x['absolute_change'], str(x['summ_id']).lower())
    )

    formatted_top = []
    for i, change in enumerate(sorted_changes[:n], 1):
        formatted_top.append({
            'rank': i,
            'summ_id': change['summ_id'],
            'queue': change['queue'],
            'tier': change['tier'],
            'lp': change['lp'],
            'change': change['change'],
            'lp_change': change.get('lp_change', 0),
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

    lp_change is movement in ladder points (see ladder_points), not the raw
    difference between two league_points values.
    """
    if old_tier is None:
        # Nothing to diff against. Report the current standing, and a change of
        # zero so a newly tracked player cannot dominate the top-changes list.
        return {
            "lp_change": 0,
            "tier_change": None,
            "division_change": None,
            "total_change": f"Now {format_tier_rank(new_tier, new_division)} ({new_lp or 0} LP)"
        }

    lp_change: int = (
        ladder_points(new_tier, new_division, new_lp)
        - ladder_points(old_tier, old_division, old_lp)
    )

    old_tier_idx: int = get_tier_index(old_tier)
    new_tier_idx: int = get_tier_index(new_tier)
    
    tier_change = None
    if new_tier_idx > old_tier_idx:
        tier_change = "PROMOTED"
    elif new_tier_idx < old_tier_idx:
        tier_change = "DEMOTED"
    
    division_change = None
    division_change_type = None
    if old_tier == new_tier and old_division and new_division: # Skips division comparison if elo is MASTER and above
        old_div_idx = get_division_index(old_division)
        new_div_idx = get_division_index(new_division)
        
        if new_div_idx > old_div_idx:
            # Higher index = better division (promotion within tier)
            division_change = f"{old_division} → {new_division}"
            division_change_type = "PROMOTED"
        elif new_div_idx < old_div_idx:
            # Lower index = worse division (demotion within tier)
            division_change = f"{old_division} → {new_division}"
            division_change_type = "DEMOTED"
        
    change_parts = []
    
    if lp_change != 0:
        change_parts.append(f"{lp_change:+} LP")
    
    # Handle tier changes (takes priority over division changes)
    if tier_change:
        if tier_change == "PROMOTED":
            change_parts.append(f"PROMOTED from {old_tier} to {new_tier}")
        else:
            change_parts.append(f"DEMOTED from {old_tier} to {new_tier}")
        
    # Handle division changes (only if no tier change)
    elif division_change:
        if division_change_type == "PROMOTED":
            change_parts.append(f"Promoted to Division {division_change}")
        else:
            change_parts.append(f"Demoted to Division {division_change}")
    
    # The two guards that used to sit here -- rewriting the message when LP rose
    # but the division fell, and vice versa -- are gone. They papered over the
    # raw-LP subtraction. Ladder points are monotonic, so a promotion cannot
    # produce a negative change and a demotion cannot produce a positive one.

    # If no changes detected, just show current tier/division
    if not change_parts:
        change_parts.append(f"No change - {format_tier_rank(new_tier, new_division)}")
    
    return {
        "lp_change": lp_change,
        "tier_change": tier_change,
        "division_change": division_change,
        "total_change": " - ".join(change_parts)
    }

def fetch_players(db_connection: object)-> pd.DataFrame:
    with db_connection.connect() as connection:
        df = pd.read_sql("""
            SELECT summ_id, puuid
            FROM public.players
            WHERE puuid IS NOT NULL
        """, connection)
        return df

def fetch_previous_elo(db_connection: object)-> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with db_connection.connect() as connection:
        # Fetch the last two scans from elo_history
        query = """
        SELECT
            p.summ_id,
            eh.queue_type,
            eh.tier,
            eh.rank,
            eh.league_points,
            eh.wins,
            eh.losses,
            eh.timestamp,
            ROW_NUMBER() OVER (PARTITION BY eh.player_key, eh.queue_type ORDER BY eh.timestamp DESC) as scan_number
        FROM public.elo_history eh
        JOIN public.players p ON eh.player_key = p.id
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

def process_queue_changes(
    summ_id: str,
    current_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    queue_name: str
) -> List[Dict[str, any]]:
    """
    Process ELO changes for a specific queue type and summoner.
    
    Args:
        summ_id: Summoner ID to process
        current_df: Current scan data for the queue
        previous_df: Previous scan data for the queue
        queue_name: Display name for the queue (e.g., "Solo/Duo Queue")
        
    Returns:
        List containing change data if there are changes, empty list otherwise
    """
    if current_df.empty:
        return []
    
    current_data = current_df[current_df['summ_id'] == summ_id]
    if current_data.empty:
        return []
    
    previous_data = previous_df[previous_df['summ_id'] == summ_id]
    if previous_data.empty:
        return []
    
    # Extract current and previous values
    current_row = current_data.iloc[0]
    previous_row = previous_data.iloc[0]
    
    change_info = calculate_elo_change(
        old_tier=previous_row['tier'],
        old_division=previous_row['rank'],
        old_lp=previous_row['league_points'],
        new_tier=current_row['tier'],
        new_division=current_row['rank'],
        new_lp=current_row['league_points']
    )
    
    # Skip players who did not actually move. The previous check compared the
    # message against "GOLD I" while the message reads "No change - GOLD I", so
    # it never matched and unchanged players were reported every run.
    if (
        change_info["lp_change"] == 0
        and change_info["tier_change"] is None
        and change_info["division_change"] is None
    ):
        return []

    return [{
        "summ_id": summ_id,
        "queue": queue_name,
        "tier": format_tier_rank(current_row['tier'], current_row['rank']),
        "lp": current_row['league_points'],
        "lp_change": change_info["lp_change"],
        "change": change_info["total_change"]
    }]

# -----------------------------

def get_queue_data() -> Tuple[pd.DataFrame, Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]]:
    """
    Fetch and organize queue data for processing.
    
    Returns:
        Tuple of (puuid_df, queue_data_dict) where queue_data_dict contains
        current and previous dataframes for each queue type
    """
    puuid_df = fetch_players(engine)
    if puuid_df.empty:
        return puuid_df, {}
    
    current_solo, current_flex, previous_solo, previous_flex = fetch_previous_elo(engine)
    
    queue_data = {
        "Solo/Duo Queue": (current_solo, previous_solo),
        "Flex Queue": (current_flex, previous_flex)
    }
    
    return puuid_df, queue_data





def track_elo_changes() -> List[Dict[str, any]]:
    """
    Track ELO changes for all summoners across all queue types.
    
    Returns:
        List of dictionaries containing change information for summoners with changes
    """
    logger.info("Starting ELO change tracking")
    puuid_df, queue_data = get_queue_data()
    
    if puuid_df.empty:
        logger.warning("No PUUID data found")
        return []
    
    if not queue_data:
        logger.warning("No queue data available")
        return []
    
    all_changes = []
    
    for _, row in puuid_df.iterrows():
        summ_id = row['summ_id']
        
        for queue_name, (current_df, previous_df) in queue_data.items():
            changes = process_queue_changes(summ_id, current_df, previous_df, queue_name)
            all_changes.extend(changes)
    
    logger.info(f"Found {len(all_changes)} ELO changes")
    return all_changes

def fetch_winrate()-> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
    wr_solo = []
    wr_flex = []
    with engine.connect() as connection:
        query:str = """
        WITH latest_scans AS (
            SELECT
                p.summ_id,
                eh.queue_type,
                eh.tier,
                eh.rank,
                eh.league_points,
                eh.wins,
                eh.losses,
                eh.timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY eh.player_key, eh.queue_type
                    ORDER BY eh.timestamp DESC
                ) AS scan_number
            FROM public.elo_history eh
            JOIN public.players p
                ON eh.player_key = p.id
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
            COALESCE(
                ROUND(((wins::numeric / NULLIF(wins + losses, 0)) * 100)::numeric, 2),
                0
            ) AS win_rate,
            timestamp
        FROM filtered_scans
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
    """
    Format ELO changes with improved sorting logic
    """
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
        
        # Sort changes by tier (ascending) and division (descending within tier)
        # This will show IRON IV first, then IRON III, II, I, then BRONZE IV, etc.
        queue_changes.sort(
            key=lambda x: (
                get_tier_index(x['tier'].split()[0]),  # Tier priority
                -get_division_index(x['tier'].split()[1]) if len(x['tier'].split()) > 1 else 0,  # Division priority (negative for desc)
                -x['lp']  # LP as tiebreaker (higher LP first)
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
                "lp_change": int(item["lp_change"]),
                "absolute_change": int(item["absolute_change"])
            }
        else:
            converted = {
                "summ_id": str(item["summ_id"]),
                "queue": item["queue"],
                "tier": item["tier"],
                "lp": int(item["lp"]),
                "lp_change": int(item["lp_change"]),
                "change": item["change"]
            }
        result.append(converted)
    return result

def main()->None:
    logger.info("Starting ELO tracker main process")
    changes = track_elo_changes()

    wr_solo, wr_flex = fetch_winrate()
    
    if changes:
        logger.info("Processing ELO changes for output")
        # Format message for WhatsApp bot
        message = format_elo_changes_message(changes)
        
        python_changes = convert_to_python_types(changes)
        
        top_changes = get_top_changes(changes, 5)
        python_top_changes = convert_to_python_types(top_changes, is_top_changes=True)
        
        date_str, timestamp = get_current_date_time()
    
        data_dir, daily_dir = create_daily_directory("elo_changes")
        latest_path = os.path.join(data_dir, "latest.json")
        
        # Save message to file in daily directory
        filename = f"elo_changes_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        try:
            write_snapshot(file_path, latest_path, {
                "message": message,
                "timestamp": timestamp,
                "changes": python_changes,
                "top_changes": python_top_changes
            })
            logger.info(f"ELO changes saved to {file_path} and mirrored to latest.json")
        except Exception as e:
            logger.error(f"Failed to save ELO changes data: {e}", exc_info=True)
    else:
        logger.info("No ELO changes detected")

    if wr_solo:
        logger.info("Processing solo/duo winrate data")
        message = format_winrate_message(wr_solo, queue_type="Solo/Duo")
        _, timestamp = get_current_date_time()
        data_dir, daily_dir = create_daily_directory("winrate/solo")
        latest_path = os.path.join(data_dir, "latest.json")
        filename = f"winrate_solo_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        try:
            write_snapshot(file_path, latest_path, {
                "message": message,
                "timestamp": timestamp,
                "changes": wr_solo
            })
            logger.info(f"Solo winrate saved to {file_path} and mirrored to latest.json")
        except Exception as e:
            logger.error(f"Failed to save solo winrate data: {e}", exc_info=True)
    else:
        logger.warning("No solo/duo winrate data available")

    if wr_flex:
        logger.info("Processing flex winrate data")
        message = format_winrate_message(wr_flex, queue_type="Flex")
        _, timestamp = get_current_date_time()
        data_dir, daily_dir = create_daily_directory("winrate/flex")
        latest_path = os.path.join(data_dir, "latest.json")
        
        filename = f"winrate_flex_{timestamp}.json"
        file_path = os.path.join(daily_dir, filename)
        
        try:
            write_snapshot(file_path, latest_path, {
                "message": message,
                "timestamp": timestamp,
                "changes": wr_flex
            })
            logger.info(f"Flex winrate saved to {file_path} and mirrored to latest.json")
        except Exception as e:
            logger.error(f"Failed to save flex winrate data: {e}", exc_info=True)
    else:
        logger.warning("No flex winrate data available")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        raise
