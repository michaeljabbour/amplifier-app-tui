"""Fuzzy subsequence matching and scoring (pure, stdlib-only).

The matching primitive behind the picker strips' typist ergonomics: a
pattern matches a candidate when its characters appear **in order** in the
candidate (a subsequence), so ``/led`` still finds ``/ledger`` after a
typo-skipping abbreviation. Matching is case-insensitive (``casefold``).

Scoring favors the matches a typist means: candidates whose match starts
at the first character, runs of consecutive hits, and hits right after a
word boundary (``/``, ``-``, ``_``, space) outrank scattered ones, and
every gap character between two hits costs a point.
"""

from __future__ import annotations

_WORD_BREAKS = frozenset("/-_ .")

_RUN_BONUS = 15
_START_BONUS = 15
_BOUNDARY_BONUS = 6
_GAP_PENALTY = 1


def fuzzy_indices(pattern: str, text: str) -> tuple[int, ...] | None:
    """Leftmost-greedy subsequence match of *pattern* in *text*.

    Returns the matched offsets (ascending) or ``None`` when *pattern* is
    not a subsequence of *text*. Matching is case-insensitive. An empty
    pattern matches everything at ``()``.
    """
    if not pattern:
        return ()
    needle = pattern.casefold()
    hay = text.casefold()
    out: list[int] = []
    start = 0
    for ch in needle:
        idx = hay.find(ch, start)
        if idx == -1:
            return None
        out.append(idx)
        start = idx + 1
    return tuple(out)


def fuzzy_score(pattern: str, text: str, indices: tuple[int, ...] | None = None) -> float | None:
    """Score a subsequence match: higher is a tighter, earlier match.

    *indices* may be passed when the caller already ran
    :func:`fuzzy_indices`; it is recomputed otherwise. Returns ``None``
    when *pattern* does not match. An empty pattern scores ``0.0``.
    """
    if indices is None:
        indices = fuzzy_indices(pattern, text)
    if indices is None:
        return None
    if not indices:
        return 0.0
    hay = text.casefold()
    score = 0.0
    if indices[0] == 0:
        score += _START_BONUS
    for pos, idx in enumerate(indices):
        if pos:
            gap = idx - indices[pos - 1] - 1
            if gap == 0:
                score += _RUN_BONUS
            else:
                score -= gap * _GAP_PENALTY
        if idx > 0 and hay[idx - 1] in _WORD_BREAKS:
            score += _BOUNDARY_BONUS
    return score


__all__ = ["fuzzy_indices", "fuzzy_score"]
