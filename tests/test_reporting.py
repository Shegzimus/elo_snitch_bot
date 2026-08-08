"""Ranking and message assembly: get_top_changes, process_queue_changes, formatters."""

import pandas as pd
import pytest

from elo_tracker import (
    convert_to_python_types,
    format_elo_changes_message,
    format_tier_rank,
    format_winrate_message,
    get_top_changes,
    process_queue_changes,
)


def change(summ_id, lp_change, tier="GOLD II", lp=50, queue="Solo/Duo Queue"):
    return {
        "summ_id": summ_id,
        "queue": queue,
        "tier": tier,
        "lp": lp,
        "lp_change": lp_change,
        "change": f"{lp_change:+} LP",
    }


# --- top changes -------------------------------------------------------------

def test_top_changes_ranks_by_magnitude_not_raw_lp():
    """A promotion must outrank a small in-division loss.

    Under the old string-parsing ranking, the promoted player carried a raw
    "-94 LP" and wrongly took the top slot by magnitude.
    """
    changes = [
        change("promoted", 6),
        change("big_loser", -80),
        change("small_gain", 12),
    ]

    top = get_top_changes(changes, n=3)

    assert [c["summ_id"] for c in top] == ["big_loser", "small_gain", "promoted"]
    assert [c["rank"] for c in top] == [1, 2, 3]


def test_top_changes_respects_n():
    changes = [change(f"p{i}", i) for i in range(1, 11)]
    assert len(get_top_changes(changes, n=5)) == 5


def test_top_changes_handles_empty_input():
    assert get_top_changes([], n=5) == []


def test_top_changes_fewer_than_n():
    assert len(get_top_changes([change("solo", 5)], n=5)) == 1


def test_top_changes_ordering_is_stable_for_ties():
    """Equal magnitudes must not reorder run to run."""
    changes = [change("Zeta", 30), change("alpha", -30), change("Mid", 30)]

    first = [c["summ_id"] for c in get_top_changes(list(changes), n=3)]
    second = [c["summ_id"] for c in get_top_changes(list(reversed(changes)), n=3)]

    assert first == second


def test_absolute_change_is_the_magnitude():
    top = get_top_changes([change("x", -42)], n=1)
    assert top[0]["absolute_change"] == 42
    assert top[0]["lp_change"] == -42


# --- process_queue_changes ---------------------------------------------------

def frame(summ_id, tier, rank, lp):
    return pd.DataFrame([{
        "summ_id": summ_id, "tier": tier, "rank": rank, "league_points": lp,
    }])


def test_unchanged_players_are_omitted():
    """The old check compared against "GOLD I" while the message read
    "No change - GOLD I", so unchanged players were reported every run."""
    current = frame("steady", "GOLD", "I", 50)
    previous = frame("steady", "GOLD", "I", 50)

    assert process_queue_changes("steady", current, previous, "Solo/Duo Queue") == []


def test_promotion_is_reported_with_a_positive_delta():
    current = frame("climber", "PLATINUM", "IV", 4)
    previous = frame("climber", "GOLD", "I", 98)

    result = process_queue_changes("climber", current, previous, "Solo/Duo Queue")

    assert len(result) == 1
    assert result[0]["lp_change"] == 6
    assert result[0]["tier"] == "PLATINUM IV"
    assert result[0]["queue"] == "Solo/Duo Queue"


def test_missing_previous_scan_yields_nothing():
    current = frame("newbie", "GOLD", "I", 50)
    previous = pd.DataFrame(columns=["summ_id", "tier", "rank", "league_points"])

    assert process_queue_changes("newbie", current, previous, "Solo/Duo Queue") == []


def test_empty_current_frame_yields_nothing():
    empty = pd.DataFrame(columns=["summ_id", "tier", "rank", "league_points"])
    assert process_queue_changes("ghost", empty, empty, "Solo/Duo Queue") == []


def test_player_absent_from_current_scan_yields_nothing():
    current = frame("someone_else", "GOLD", "I", 50)
    previous = frame("missing", "GOLD", "I", 40)

    assert process_queue_changes("missing", current, previous, "Solo/Duo Queue") == []


# --- formatting --------------------------------------------------------------

def test_format_tier_rank_omits_empty_division():
    assert format_tier_rank("GOLD", "II") == "GOLD II"
    assert format_tier_rank("MASTER", None) == "MASTER"
    assert format_tier_rank("MASTER", "") == "MASTER"


def test_elo_message_groups_by_queue_and_sorts_by_rank():
    changes = [
        change("plat_player", 10, tier="PLATINUM IV", lp=4),
        change("iron_player", -5, tier="IRON IV", lp=10),
        change("flex_player", 20, tier="GOLD I", lp=80, queue="Flex Queue"),
    ]

    message = format_elo_changes_message(changes)

    assert "*ELO CHANGES UPDATE*" in message
    assert "*Solo/Duo Queue:*" in message
    assert "*Flex Queue:*" in message
    # Lowest rank first within a queue.
    assert message.index("iron_player") < message.index("plat_player")


def test_elo_message_handles_apex_tier_without_a_division():
    """Sorting splits "MASTER" on whitespace; a missing division must not crash."""
    message = format_elo_changes_message([change("apex", 40, tier="MASTER", lp=300)])
    assert "apex" in message


def test_winrate_message_empty_case():
    assert "No win rate data available" in format_winrate_message([], "Flex")


def test_winrate_message_lists_players():
    data = [{
        "summ_id": "player", "tier": "GOLD", "rank": "II",
        "wins": 12, "losses": 8, "total_games": 20, "win_rate": 60.0,
    }]

    message = format_winrate_message(data, queue_type="Solo/Duo")

    assert "*Solo/Duo Queue Win Rates:*" in message
    assert "player - GOLD II (60.0% | 12W-8L)" in message


# --- serialisation -----------------------------------------------------------

def test_convert_to_python_types_produces_json_safe_scalars():
    import json

    rows = [{
        "summ_id": "p", "queue": "Solo/Duo Queue", "tier": "GOLD II",
        "lp": pd.array([50])[0], "lp_change": pd.array([6])[0], "change": "+6 LP",
    }]

    converted = convert_to_python_types(rows)

    assert isinstance(converted[0]["lp"], int)
    assert isinstance(converted[0]["lp_change"], int)
    json.dumps(converted)  # must not raise


def test_convert_to_python_types_top_changes_shape():
    import json

    top = get_top_changes([change("p", 6)], n=1)
    converted = convert_to_python_types(top, is_top_changes=True)

    assert converted[0]["rank"] == 1
    assert converted[0]["absolute_change"] == 6
    json.dumps(converted)
