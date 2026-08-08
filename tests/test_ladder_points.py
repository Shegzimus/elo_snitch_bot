"""Exhaustive checks on the ranked ladder scale.

The ladder is small enough to enumerate completely -- 7 divisioned tiers x 4
divisions x 101 LP values, plus the apex tiers -- so these tests do not sample.
If ladder_points is ever monotonic-broken for any reachable rank, every one of
these fails.
"""

import itertools

import pytest

from elo_tracker import (
    APEX_TIERS,
    DIVISION_ORDER,
    LP_PER_DIVISION,
    LP_PER_TIER,
    TIER_ORDER,
    get_division_index,
    get_tier_index,
    ladder_points,
)

DIVISIONED_TIERS = [t for t in TIER_ORDER if t not in APEX_TIERS]


def every_rank_in_ascending_order():
    """All reachable ranks, worst to best.

    Divisions ascend IV -> I, LP ascends 0 -> 100 within a division.
    """
    for tier in DIVISIONED_TIERS:
        for division in DIVISION_ORDER:          # IV, III, II, I
            for lp in range(0, LP_PER_DIVISION):  # 0..99
                yield (tier, division, lp)
    # Apex is one continuous pool; 0..2000 LP covers Challenger comfortably.
    for lp in range(0, 2001):
        yield ("MASTER", None, lp)


ALL_RANKS = list(every_rank_in_ascending_order())


def test_ladder_is_strictly_increasing_across_every_reachable_rank():
    """The core invariant: a better rank always scores higher. Full sweep."""
    points = [ladder_points(t, d, lp) for t, d, lp in ALL_RANKS]

    for i in range(1, len(points)):
        prev_rank, curr_rank = ALL_RANKS[i - 1], ALL_RANKS[i]
        assert points[i] > points[i - 1], (
            f"ladder not increasing: {prev_rank} -> {curr_rank} "
            f"scored {points[i - 1]} -> {points[i]}"
        )


def test_no_two_distinct_ranks_share_a_score():
    points = [ladder_points(t, d, lp) for t, d, lp in ALL_RANKS]
    assert len(set(points)) == len(points)


@pytest.mark.parametrize("tier", DIVISIONED_TIERS)
def test_promotion_out_of_a_tier_always_gains(tier):
    """Division I 99 LP -> next tier IV 0 LP must be a gain, not a 99 LP loss.

    This is the exact shape of the bug: raw subtraction reports -99.
    """
    index = TIER_ORDER.index(tier)
    if index + 1 >= len(TIER_ORDER):
        pytest.skip("no tier above")
    next_tier = TIER_ORDER[index + 1]
    next_division = None if next_tier in APEX_TIERS else "IV"

    before = ladder_points(tier, "I", 99)
    after = ladder_points(next_tier, next_division, 0)
    assert after > before


def test_apex_tiers_share_one_lp_pool():
    """Grandmaster is a cutoff, not a tier above Master in LP terms.

    Without this, a Master on 600 LP would outrank a Grandmaster on 100.
    """
    assert ladder_points("MASTER", None, 500) == ladder_points("GRANDMASTER", None, 500)
    assert ladder_points("GRANDMASTER", None, 500) == ladder_points("CHALLENGER", None, 500)
    assert ladder_points("GRANDMASTER", None, 100) > ladder_points("MASTER", None, 90)


def test_diamond_i_promotes_into_master():
    assert ladder_points("MASTER", None, 0) > ladder_points("DIAMOND", "I", 99)


def test_tier_and_division_arithmetic():
    assert ladder_points("IRON", "IV", 0) == 0
    assert ladder_points("IRON", "III", 0) == LP_PER_DIVISION
    assert ladder_points("BRONZE", "IV", 0) == LP_PER_TIER
    assert ladder_points("GOLD", "I", 98) == 3 * LP_PER_TIER + 3 * LP_PER_DIVISION + 98


def test_none_lp_is_treated_as_zero():
    assert ladder_points("GOLD", "II", None) == ladder_points("GOLD", "II", 0)


def test_apex_ignores_any_division_value():
    """Riot sends rank "I" for apex entries; it must not shift the score."""
    for tier, division in itertools.product(sorted(APEX_TIERS), [None, "I", "IV"]):
        assert ladder_points(tier, division, 250) == ladder_points("MASTER", None, 250)


def test_unknown_tier_raises_rather_than_scoring_silently():
    with pytest.raises(ValueError, match="Unknown tier"):
        ladder_points("WOOD", "IV", 0)
    with pytest.raises(ValueError, match="Unknown tier"):
        get_tier_index("UNRANKED")


def test_unknown_division_raises():
    with pytest.raises(ValueError, match="Unknown division"):
        ladder_points("GOLD", "V", 0)
    with pytest.raises(ValueError, match="Unknown division"):
        get_division_index("0")
