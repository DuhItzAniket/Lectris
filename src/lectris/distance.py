"""Edit distances between strings, including one weighted for the confusions OCR makes.

``levenshtein`` and ``damerau_levenshtein`` count edits of one character. ``ocr_distance`` also
lets a character or short sequence turn into another at a cost below 1 when the two look alike in
print (``rn`` and ``m``, ``0`` and ``O``), so ``"modern"`` is nearer to ``"rnodern"`` than to
``"modest"``.
"""

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

_SIMILAR: Final = 0.25
_ALIKE: Final = 0.5


def _symmetric(pairs: Mapping[tuple[str, str], float]) -> Mapping[tuple[str, str], float]:
    table: dict[tuple[str, str], float] = {}
    for (first, second), cost in pairs.items():
        table[first, second] = cost
        table[second, first] = cost
    return MappingProxyType(table)


OCR_COSTS: Final[Mapping[tuple[str, str], float]] = _symmetric(
    {
        # Glyphs that many print fonts draw alike, or nearly so.
        ("0", "O"): _SIMILAR,
        ("1", "l"): _SIMILAR,
        ("1", "I"): _SIMILAR,
        ("l", "I"): _SIMILAR,
        ("rn", "m"): _SIMILAR,
        ("vv", "w"): _SIMILAR,
        ("VV", "W"): _SIMILAR,
        # Glyphs that are alike but differ in size, a stroke, a serif or a gap.
        ("0", "o"): _ALIKE,
        ("5", "S"): _ALIKE,
        ("8", "B"): _ALIKE,
        ("2", "Z"): _ALIKE,
        ("6", "b"): _ALIKE,
        ("e", "c"): _ALIKE,
        ("u", "n"): _ALIKE,
        ("cl", "d"): _ALIKE,
        ("li", "h"): _ALIKE,
        ("|", "l"): _ALIKE,
        ("|", "I"): _ALIKE,
        ("|", "1"): _ALIKE,
    }
)
"""The substitution costs ``ocr_distance`` uses by default: ``(seen, meant) -> cost``.

The table is symmetric: each pair is listed in both directions with the same cost. Pairs that
many fonts draw almost identically cost 0.25: ``0``/``O``, ``1``/``l``/``I``, ``rn``/``m`` and
``vv``/``w`` (``VV``/``W``). Pairs that are alike but differ in size, a stroke, a serif or a gap
cost 0.5: ``0``/``o``, ``5``/``S``, ``8``/``B``, ``2``/``Z``, ``6``/``b``, ``e``/``c``,
``u``/``n``, ``cl``/``d``, ``li``/``h``, and ``|`` with ``l``, ``I`` and ``1``. Any other
substitution costs 1.

The costs are heuristics chosen from glyph shapes, not measured from OCR output. Pass your own
table to ``ocr_distance`` when you have confusion counts for your engine and fonts.
"""


def levenshtein(a: str, b: str) -> int:
    """The Levenshtein distance: the fewest insertions, deletions and substitutions of one
    character that turn ``a`` into ``b``.

    It is a metric. Time is ``O(len(a) * len(b))``.

    >>> levenshtein("kitten", "sitting")
    3
    """
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (char_a != char_b),
                )
            )
        previous = current
    return previous[-1]


def damerau_levenshtein(a: str, b: str) -> int:
    """The optimal string alignment distance: Levenshtein's edits plus the transposition of two
    adjacent characters, each costing 1.

    This is the restricted Damerau-Levenshtein distance: no character is edited after it has
    been transposed, so ``"ca"`` to ``"abc"`` costs 3 here (the unrestricted distance is 2), and
    the triangle inequality does not always hold. Time is ``O(len(a) * len(b))``.

    >>> damerau_levenshtein("form", "from")
    1
    """
    before: list[int] = []
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i]
        for j in range(1, len(b) + 1):
            distance = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (a[i - 1] != b[j - 1]),
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                distance = min(distance, before[j - 2] + 1)
            current.append(distance)
        before, previous = previous, current
    return previous[-1]


# The weighted programme below is shared with lectris.lexicon, whose suggestions run it over many
# words with a common prefix. A table entry seen from the programme: the length of its span in
# the first string, its span in the second string, that span's length, and its cost.
type _Span = tuple[int, str, int, float]


class _CostIndex:
    """A substitution table arranged for the dynamic programme, indexed by its first strings."""

    __slots__ = ("by_source", "longest_source", "longest_target", "target_prefixes")

    def __init__(self, costs: Mapping[tuple[str, str], float]) -> None:
        by_source: dict[str, list[tuple[str, float]]] = {}
        for key, cost in costs.items():
            source, target = key
            if not source or not target or source == target:
                raise ValueError(
                    f"a cost is for two different non-empty strings, not {source!r} and {target!r}"
                )
            if not (math.isfinite(cost) and cost >= 0):
                raise ValueError(
                    f"a cost is a finite number of at least 0, not {cost!r} for {key!r}"
                )
            by_source.setdefault(source, []).append((target, float(cost)))
        self.by_source = {source: tuple(found) for source, found in by_source.items()}
        self.longest_source = max(map(len, by_source), default=0)
        self.longest_target = max(
            (len(target) for found in by_source.values() for target, _ in found), default=1
        )
        # The beginnings of second strings longer than one character: a row of the programme can
        # be stepped over only by an entry whose second string starts with what that row ends in.
        self.target_prefixes = frozenset(
            target[:length]
            for found in by_source.values()
            for target, _ in found
            for length in range(1, len(target))
        )

    def spans(self, a: str) -> list[tuple[_Span, ...]]:
        """For each position ``i`` in ``a`` (``0`` to ``len(a)``), the table entries whose first
        string ends there."""
        result: list[tuple[_Span, ...]] = [()]
        for end in range(1, len(a) + 1):
            found: list[_Span] = []
            for length in range(1, min(self.longest_source, end) + 1):
                for target, cost in self.by_source.get(a[end - length : end], ()):
                    found.append((length, target, len(target), cost))
            result.append(tuple(found))
        return result


_OCR_INDEX: Final = _CostIndex(OCR_COSTS)


def _cost_index(costs: Mapping[tuple[str, str], float]) -> _CostIndex:
    return _OCR_INDEX if costs is OCR_COSTS else _CostIndex(costs)


def _first_row(a: str) -> list[float]:
    return [float(i) for i in range(len(a) + 1)]


def _next_row(
    a: str, spans: Sequence[tuple[_Span, ...]], rows: Sequence[list[float]], b: str, j: int
) -> list[float]:
    """Row ``j`` of the weighted programme: the cost from each prefix of ``a`` to ``b[:j]``.

    ``rows[-1]`` is row ``j - 1``, ``rows[-2]`` row ``j - 2``, and so on: at least as many rows
    as the table's longest second string, or all of them when ``j`` is smaller.
    """
    previous = rows[-1]
    char = b[j - 1]
    row = [previous[0] + 1.0]
    for i in range(1, len(a) + 1):
        diagonal = previous[i - 1] if a[i - 1] == char else previous[i - 1] + 1.0
        best = min(previous[i] + 1.0, row[i - 1] + 1.0, diagonal)
        for length, target, target_length, weight in spans[i]:
            if target_length <= j and b[j - target_length : j] == target:
                best = min(best, rows[-target_length][i - length] + weight)
        row.append(best)
    return row


def ocr_distance(a: str, b: str, *, costs: Mapping[tuple[str, str], float] = OCR_COSTS) -> float:
    """A weighted edit distance where the substitutions OCR makes cost less than 1.

    Inserting, deleting or substituting one character costs 1, as in ``levenshtein``. In
    addition, a span ``x`` of ``a`` may become a span ``y`` of ``b`` at ``costs[(x, y)]``; the
    spans may be longer than one character (``("rn", "m")``). The result is the cheapest
    combination, so it is never more than ``levenshtein(a, b)``, and it is symmetric when the
    table is (``OCR_COSTS`` is). Each character takes part in at most one operation, so it is
    not a metric: confusions that share a character do not chain, and ``"ru"`` is 0.5 from
    ``"rn"``, which is 0.25 from ``"m"``, but 2 from ``"m"``.

    Time is ``O(len(a) * len(b) * k)``, where ``k`` is the number of table entries that can end
    at one position of ``a`` (a handful for ``OCR_COSTS``).

    Raises ``ValueError`` if a key of ``costs`` is not two different non-empty strings or a cost
    is negative or not finite.

    >>> ocr_distance("modern", "rnodern")
    0.25
    >>> levenshtein("modern", "rnodern")
    2
    """
    index = _cost_index(costs)
    spans = index.spans(a)
    rows = [_first_row(a)]
    for j in range(1, len(b) + 1):
        rows.append(_next_row(a, spans, rows, b, j))
        if len(rows) > index.longest_target:
            del rows[0]
    return rows[-1][-1]
