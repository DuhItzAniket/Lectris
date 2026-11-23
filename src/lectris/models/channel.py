"""What an engine confuses: a channel model P(observed | intended) over short substrings.

``Channel.fit(pairs)`` reads pairs of (intended, observed) texts, a ground-truth line and the OCR
line matched with it, aligns each pair character by character (``lectris.align``), and groups
each run of differences into an *error*: the intended and the observed substrings it covers.
Errors of up to ``MAX_SPAN`` characters on each side are counted as confusions (``m`` read as
``rn``, ``l`` as ``1``, a lost space); longer runs are counted character by character. Each
intended character that was read as itself counts as a match.

The probability of reading ``intended`` as ``observed`` (both up to ``MAX_SPAN`` characters, not
both empty) is additively smoothed over the model's observed forms:

    (count(intended, observed) + alpha) / (occurrences(intended) + alpha * K)

where ``K`` is the number of different observed forms the model has seen, plus one for any
other. An intended string never seen in training reads as each form with probability ``1 / K``,
and a confusion never seen has ``alpha`` in its numerator only. The probability of an insertion
(``intended`` empty) is per intended character. ``log_likelihood(intended, observed)`` aligns
the two and sums the logarithms of its matches and errors: the evidence a candidate edit gets
from the channel.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any, Final

from lectris.align import Op, align_chars

MAX_SPAN: Final = 2
"""The longest intended or observed substring a confusion is counted for."""


def errors(intended: str, observed: str) -> list[tuple[str, str]]:
    """The aligned pair as a list of ``(intended, observed)`` pieces: one per match, one per run
    of differences of up to ``MAX_SPAN`` characters on each side, and one per character of a
    longer run."""
    pieces: list[tuple[str, str]] = []
    run: list[Op] = []
    for op in (*align_chars(intended, observed), None):
        if op is not None and op.kind != "equal":
            run.append(op)
            continue
        if run:
            left = "".join(o.reference for o in run)
            right = "".join(o.hypothesis for o in run)
            if len(left) <= MAX_SPAN and len(right) <= MAX_SPAN:
                pieces.append((left, right))
            else:
                pieces.extend((o.reference, o.hypothesis) for o in run)
            run = []
        if op is not None:
            pieces.append((op.reference, op.hypothesis))
    return pieces


class Channel:
    """A fitted channel model; build one with ``fit`` or ``from_data``."""

    __slots__ = ("_alpha", "_chars", "_confusions", "_forms", "_occurrences")

    def __init__(
        self,
        confusions: Mapping[tuple[str, str], int],
        occurrences: Mapping[str, int],
        chars: int,
        alpha: float = 0.5,
    ) -> None:
        self._confusions = dict(confusions)
        self._occurrences = dict(occurrences)
        self._chars = chars
        self._alpha = alpha
        self._forms = len({observed for _, observed in self._confusions}) + 1

    @classmethod
    def fit(cls, pairs: Iterable[tuple[str, str]], *, alpha: float = 0.5) -> "Channel":
        """The channel of ``(intended, observed)`` pairs."""
        confusions: Counter[tuple[str, str]] = Counter()
        occurrences: Counter[str] = Counter()
        chars = 0
        for intended, observed in pairs:
            chars += len(intended)
            for width in range(1, MAX_SPAN + 1):
                occurrences.update(
                    intended[i : i + width] for i in range(len(intended) - width + 1)
                )
            confusions.update(errors(intended, observed))
        return cls(confusions, occurrences, chars, alpha)

    def prob(self, intended: str, observed: str) -> float:
        """P(``observed`` is read where ``intended`` is written)."""
        count = self._confusions.get((intended, observed), 0)
        # An insertion (nothing intended) is counted per intended character.
        base = self._occurrences.get(intended, 0) if intended else self._chars
        return (count + self._alpha) / (base + self._alpha * self._forms)

    def log_likelihood(self, intended: str, observed: str) -> float:
        """log P(``observed`` | ``intended``), the sum over the aligned pieces (natural log)."""
        return sum(math.log(self.prob(a, b)) for a, b in errors(intended, observed))

    def top(self, count: int = 20) -> list[tuple[str, str, int]]:
        """The most frequent confusions (not matches), as ``(intended, observed, count)``."""
        found = [(a, b, n) for (a, b), n in self._confusions.items() if a != b]
        return sorted(found, key=lambda item: (-item[2], item[0], item[1]))[:count]

    def to_data(self) -> dict[str, Any]:
        """The model as JSON-ready data; ``from_data`` reads it back."""
        return {
            "alpha": self._alpha,
            "chars": self._chars,
            "confusions": [[a, b, n] for (a, b), n in sorted(self._confusions.items())],
            "occurrences": dict(sorted(self._occurrences.items())),
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "Channel":
        """The model ``to_data`` wrote."""
        return cls(
            {(str(a), str(b)): int(n) for a, b, n in data["confusions"]},
            {str(k): int(v) for k, v in data["occurrences"].items()},
            int(data["chars"]),
            float(data["alpha"]),
        )


def uniform_log_likelihood(intended: str, observed: str, error_rate: float, alphabet: int) -> float:
    """log P(``observed`` | ``intended``) under a uniform-cost model, the baseline a channel must
    beat: each aligned character is read right with probability ``1 - error_rate``, and each
    error, whatever it is, has probability ``error_rate / alphabet``."""
    total = 0.0
    for op in align_chars(intended, observed):
        if op.kind == "equal":
            total += math.log(1 - error_rate)
        else:
            total += math.log(error_rate / alphabet)
    return total
