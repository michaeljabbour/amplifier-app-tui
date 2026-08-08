"""tests for kernel/fuzzy.py — subsequence matching + scoring."""

from __future__ import annotations

from amplifier_app_tui.kernel.fuzzy import fuzzy_indices, fuzzy_score


def test_subsequence_match_returns_leftmost_offsets() -> None:
    assert fuzzy_indices("ldg", "/ledger") == (1, 3, 4)
    # Leftmost-greedy: the first 'a' wins even when a later one exists.
    assert fuzzy_indices("a", "alpha") == (0,)


def test_match_is_case_insensitive() -> None:
    assert fuzzy_indices("LDG", "/Ledger") == (1, 3, 4)
    assert fuzzy_indices("fuzzy", "FuZzY") == (0, 1, 2, 3, 4)


def test_empty_pattern_matches_everything_at_empty_indices() -> None:
    assert fuzzy_indices("", "anything") == ()
    assert fuzzy_indices("", "") == ()


def test_non_subsequence_returns_none() -> None:
    assert fuzzy_indices("zzz", "alphabet") is None
    # Order matters: 'g' never follows 'd' here.
    assert fuzzy_indices("dg", "gd") is None


def test_score_prefers_start_of_text() -> None:
    early = fuzzy_score("ab", "ab--")
    late = fuzzy_score("ab", "--ab")
    assert early is not None and late is not None
    assert early > late


def test_score_prefers_consecutive_runs() -> None:
    run = fuzzy_score("mod", "mode")
    scattered = fuzzy_score("mod", "mxoxd")
    assert run is not None and scattered is not None
    assert run > scattered


def test_score_rewards_word_boundary_hits() -> None:
    boundary = fuzzy_score("n", "foo-name")
    interior = fuzzy_score("n", "fooname")
    assert boundary is not None and interior is not None
    assert boundary > interior


def test_score_penalizes_gaps_monotonically() -> None:
    tight = fuzzy_score("ab", "axxb")
    loose = fuzzy_score("ab", "axxxxb")
    assert tight is not None and loose is not None
    assert tight > loose


def test_score_returns_none_for_non_match_and_zero_for_empty() -> None:
    assert fuzzy_score("zzz", "abc") is None
    assert fuzzy_score("", "abc") == 0.0


def test_score_accepts_precomputed_indices() -> None:
    indices = fuzzy_indices("md", "mode")
    assert indices is not None
    assert fuzzy_score("md", "mode", indices) == fuzzy_score("md", "mode")
