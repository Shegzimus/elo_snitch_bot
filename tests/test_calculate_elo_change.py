"""Behaviour of calculate_elo_change, including the regressions from production.

The sign of lp_change is the thing that killed the project: promotions were
reported as large LP losses, so the WhatsApp report was nonsense on exactly the
events people cared about most.
"""

import itertools

import pytest

from elo_tracker import (
    APEX_TIERS,
    DIVISION_ORDER,
    TIER_ORDER,
    calculate_elo_change,
    ladder_points,
)

DIVISIONED_TIERS = [t for t in TIER_ORDER if t not in APEX_TIERS]


# --- the production regressions, verbatim from data/elo_changes ---------------

@pytest.mark.parametrize(
    "name, old, new, expected_lp_change, expected_tier_change",
    [
        # Real before/after rows from elo_history, solo queue. The "reported"
        # strings are what the broken build actually posted to WhatsApp.
        # reported: "-94 LP - PROMOTED from GOLD to PLATINUM"
        ("Sadme17", ("GOLD", "IV", 98), ("PLATINUM", "IV", 4), 306, "PROMOTED"),
        # reported: "-65 LP - PROMOTED from DIAMOND to MASTER"
        ("AJsBigBackClock", ("DIAMOND", "I", 71), ("MASTER", None, 6), 35, "PROMOTED"),
        # reported: "-46 LP" despite climbing two divisions
        ("TK SavageMummy", ("PLATINUM", "IV", 65), ("PLATINUM", "II", 19), 154, None),
    ],
)
def test_known_production_regressions_now_report_gains(
    name, old, new, expected_lp_change, expected_tier_change
):
    result = calculate_elo_change(old[0], old[1], old[2], new[0], new[1], new[2])

    assert result["lp_change"] == expected_lp_change, name
    assert result["lp_change"] > 0, f"{name}: climbing must not report a loss"
    assert result["tier_change"] == expected_tier_change
    assert result["total_change"].startswith("+")


def test_the_exact_shape_of_the_bug():
    """Sadme17: raw subtraction gives -94, the ladder gives +306."""
    result = calculate_elo_change("GOLD", "IV", 98, "PLATINUM", "IV", 4)
    naive = 4 - 98

    assert naive == -94
    assert result["lp_change"] == 306
    assert "-94" not in result["total_change"]


# --- sign invariants ---------------------------------------------------------

def test_every_single_tier_promotion_reports_a_gain():
    """Sweep every tier boundary at the worst possible LP reset (99 -> 0)."""
    for index, tier in enumerate(TIER_ORDER[:-1]):
        if tier in APEX_TIERS:
            continue
        next_tier = TIER_ORDER[index + 1]
        next_division = None if next_tier in APEX_TIERS else "IV"

        result = calculate_elo_change(tier, "I", 99, next_tier, next_division, 0)

        assert result["lp_change"] > 0, f"{tier} -> {next_tier} reported a loss"
        assert result["tier_change"] == "PROMOTED"


def test_every_single_tier_demotion_reports_a_loss():
    for index, tier in enumerate(TIER_ORDER[:-1]):
        if tier in APEX_TIERS:
            continue
        next_tier = TIER_ORDER[index + 1]
        next_division = None if next_tier in APEX_TIERS else "IV"

        result = calculate_elo_change(next_tier, next_division, 0, tier, "I", 99)

        assert result["lp_change"] < 0, f"{next_tier} -> {tier} reported a gain"
        assert result["tier_change"] == "DEMOTED"


def test_every_division_promotion_within_every_tier_reports_a_gain():
    for tier in DIVISIONED_TIERS:
        for lower, higher in zip(DIVISION_ORDER, DIVISION_ORDER[1:]):
            result = calculate_elo_change(tier, lower, 99, tier, higher, 0)

            assert result["lp_change"] > 0, f"{tier} {lower} -> {higher} reported a loss"
            assert result["division_change"] == f"{lower} → {higher}"
            assert result["tier_change"] is None


def test_lp_100_is_the_promotion_threshold_not_a_distinct_rank():
    """Deliberate: divisions are exactly 100 wide so deltas equal real LP.

    "GOLD IV 100" and "GOLD III 0" are the same ladder position -- reaching 100
    promotes you, so crossing that line is a zero-LP move. Widening divisions to
    101 would make this strictly increasing but put every reported number out by
    one per division crossed.
    """
    result = calculate_elo_change("GOLD", "IV", 100, "GOLD", "III", 0)

    assert result["lp_change"] == 0
    assert result["division_change"] == "IV → III"


def test_sign_always_agrees_with_ladder_movement_across_many_pairs():
    """The invariant that must never break: sign(lp_change) == sign(ladder delta)."""
    sample = [
        (tier, division, lp)
        for tier in DIVISIONED_TIERS
        for division in DIVISION_ORDER
        for lp in (0, 50, 100)
    ] + [("MASTER", None, lp) for lp in (0, 300, 1200)]

    for old, new in itertools.product(sample, repeat=2):
        result = calculate_elo_change(old[0], old[1], old[2], new[0], new[1], new[2])
        expected = ladder_points(*new) - ladder_points(*old)

        assert result["lp_change"] == expected, f"{old} -> {new}"


# --- message content ---------------------------------------------------------

def test_no_movement_is_reported_as_no_change():
    result = calculate_elo_change("GOLD", "II", 50, "GOLD", "II", 50)

    assert result["lp_change"] == 0
    assert result["tier_change"] is None
    assert result["division_change"] is None
    assert result["total_change"] == "No change - GOLD II"


def test_plain_lp_gain_within_a_division():
    result = calculate_elo_change("SILVER", "III", 20, "SILVER", "III", 45)

    assert result["lp_change"] == 25
    assert result["total_change"] == "+25 LP"


def test_plain_lp_loss_within_a_division():
    result = calculate_elo_change("SILVER", "III", 45, "SILVER", "III", 20)

    assert result["lp_change"] == -25
    assert result["total_change"] == "-25 LP"


def test_promotion_message_names_both_tiers():
    result = calculate_elo_change("GOLD", "I", 98, "PLATINUM", "IV", 4)
    assert result["total_change"] == "+6 LP - PROMOTED from GOLD to PLATINUM"


def test_division_promotion_message():
    result = calculate_elo_change("GOLD", "III", 95, "GOLD", "II", 10)
    assert "Promoted to Division III → II" in result["total_change"]
    assert result["total_change"].startswith("+")


def test_division_demotion_message():
    result = calculate_elo_change("GOLD", "II", 10, "GOLD", "III", 95)
    assert "Demoted to Division II → III" in result["total_change"]
    assert result["total_change"].startswith("-")


def test_apex_lp_movement_is_a_plain_lp_change():
    result = calculate_elo_change("MASTER", None, 100, "MASTER", None, 350)

    assert result["lp_change"] == 250
    assert result["tier_change"] is None
    assert result["total_change"] == "+250 LP"


def test_master_to_grandmaster_is_not_a_phantom_tier_jump():
    """Crossing the GM cutoff on the same LP must not invent a huge gain."""
    result = calculate_elo_change("MASTER", None, 500, "GRANDMASTER", None, 500)

    assert result["lp_change"] == 0
    assert result["tier_change"] == "PROMOTED"
    assert "PROMOTED from MASTER to GRANDMASTER" in result["total_change"]


# --- edge cases --------------------------------------------------------------

def test_first_time_tracking_reports_zero_change():
    """A newly tracked player must not dominate the top-changes leaderboard."""
    result = calculate_elo_change(None, None, None, "GOLD", "II", 40)

    assert result["lp_change"] == 0
    assert result["tier_change"] is None
    assert result["total_change"] == "Now GOLD II (40 LP)"


def test_none_lp_values_do_not_crash():
    result = calculate_elo_change("GOLD", "II", None, "GOLD", "II", None)
    assert result["lp_change"] == 0


def test_apex_demotion_back_into_diamond():
    result = calculate_elo_change("MASTER", None, 0, "DIAMOND", "I", 75)

    assert result["lp_change"] < 0
    assert result["tier_change"] == "DEMOTED"
