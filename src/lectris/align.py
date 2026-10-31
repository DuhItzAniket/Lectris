"""Alignment: a minimum-edit (Levenshtein) alignment of two sequences, of characters or words.

``align`` pairs a reference with a hypothesis (usually a transcription with OCR output) as a
list of operations, one per element: ``equal``, ``substitute``, ``insert`` (an element only the
hypothesis has) or ``delete`` (an element only the reference has). The number of operations that
are not ``equal`` is the Levenshtein distance; every operation costs 1.

Several alignments are often equally short; ``align`` picks one deterministically:

1. Elements the two sequences share at the start and at the end are aligned as ``equal``.
2. Between them, the alignment is traced back from the end, and at each step the first of these
   that still leads to a minimum-cost alignment is taken: pair the two current elements
   (``equal`` or ``substitute``), then ``delete`` the reference element, then ``insert`` the
   hypothesis element.

So ``"ab"`` against ``"ba"`` is two substitutions, not a deletion and an insertion. The work is
proportional to the length times the distance (a band around the diagonal, widened until it
holds the distance), so long texts with few errors align quickly.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

type OpKind = Literal["equal", "substitute", "insert", "delete"]

KINDS: Final[tuple[OpKind, ...]] = ("equal", "substitute", "insert", "delete")

_PAIR: Final = 1
_DELETE: Final = 2
_INSERT: Final = 3


@dataclass(frozen=True, slots=True)
class Op:
    """One step of an alignment: a reference element, a hypothesis element, or both.

    ``equal`` and ``substitute`` hold one element of each (the same, and different);
    ``insert`` has ``reference == ""`` and ``delete`` has ``hypothesis == ""``.
    """

    kind: OpKind
    reference: str
    hypothesis: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"an op's kind is one of {', '.join(KINDS)}, not {self.kind!r}")
        valid = {
            "equal": self.reference == self.hypothesis,
            "substitute": self.reference != self.hypothesis,
            "insert": self.reference == "",
            "delete": self.hypothesis == "",
        }[self.kind]
        if not valid:
            raise ValueError(
                f"{self.reference!r} and {self.hypothesis!r} cannot make a {self.kind!r} op"
            )


def align(reference: Sequence[str], hypothesis: Sequence[str]) -> tuple[Op, ...]:
    """A minimum-edit alignment of two sequences of strings, one ``Op`` per element.

    Pass two ``str`` to align characters, or two lists of words to align words. Elements are
    compared with ``==``. The module describes which alignment is chosen when several are
    equally short.
    """
    n, m = len(reference), len(hypothesis)
    prefix = 0
    while prefix < min(n, m) and reference[prefix] == hypothesis[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(n, m) - prefix and reference[n - 1 - suffix] == hypothesis[m - 1 - suffix]:
        suffix += 1
    middle = _align_middle(reference[prefix : n - suffix], hypothesis[prefix : m - suffix])
    return (
        *(Op("equal", element, element) for element in reference[:prefix]),
        *middle,
        *(Op("equal", element, element) for element in reference[n - suffix :]),
    )


def align_chars(reference: str, hypothesis: str) -> tuple[Op, ...]:
    """The character alignment of two texts: one ``Op`` per character."""
    return align(reference, hypothesis)


def align_words(reference: str, hypothesis: str) -> tuple[Op, ...]:
    """The word alignment of two texts, whose words are their whitespace-separated pieces."""
    return align(reference.split(), hypothesis.split())


def _align_middle(reference: Sequence[str], hypothesis: Sequence[str]) -> list[Op]:
    if not reference:
        return [Op("insert", "", element) for element in hypothesis]
    if not hypothesis:
        return [Op("delete", element, "") for element in reference]
    bound = max(abs(len(hypothesis) - len(reference)), 1)
    while (ops := _align_banded(reference, hypothesis, bound)) is None:
        bound *= 2
    return ops


def _align_banded(
    reference: Sequence[str], hypothesis: Sequence[str], bound: int
) -> list[Op] | None:
    """The alignment if the distance is at most ``bound``, else ``None``.

    Only cells ``(i, j)`` with ``|j - i| + |delta - (j - i)| <= bound`` are computed, where
    ``delta = len(hypothesis) - len(reference)``: an alignment through any other cell costs more
    than ``bound``. When the distance is at most ``bound``, every minimum-cost alignment lies in
    the band, so the costs on them and the steps chosen are those of the full table.
    """
    n, m = len(reference), len(hypothesis)
    delta = m - n
    slack = (bound - abs(delta)) // 2
    low, high = min(0, delta) - slack, max(0, delta) + slack
    starts = [0]
    steps = [bytearray([0, *([_INSERT] * min(m, high))])]
    previous = list(range(min(m, high) + 1))
    previous_start = 0
    for i in range(1, n + 1):
        element = reference[i - 1]
        start, stop = max(0, i + low), min(m, i + high)
        costs = [0] * (stop - start + 1)
        row = bytearray(stop - start + 1)
        width = len(previous)
        for j in range(start, stop + 1):
            best, step = n + m + 1, 0
            above = j - previous_start
            if 0 < above <= width:
                best, step = previous[above - 1] + (element != hypothesis[j - 1]), _PAIR
            if 0 <= above < width and previous[above] + 1 < best:
                best, step = previous[above] + 1, _DELETE
            if j > start and costs[j - 1 - start] + 1 < best:
                best, step = costs[j - 1 - start] + 1, _INSERT
            costs[j - start] = best
            row[j - start] = step
        starts.append(start)
        steps.append(row)
        previous, previous_start = costs, start
    if previous[m - previous_start] > bound:
        return None
    ops: list[Op] = []
    i, j = n, m
    while i or j:
        step = steps[i][j - starts[i]]
        if step == _PAIR:
            before, after = reference[i - 1], hypothesis[j - 1]
            ops.append(Op("equal" if before == after else "substitute", before, after))
            i, j = i - 1, j - 1
        elif step == _DELETE:
            ops.append(Op("delete", reference[i - 1], ""))
            i -= 1
        else:
            ops.append(Op("insert", "", hypothesis[j - 1]))
            j -= 1
    ops.reverse()
    return ops
