"""A character n-gram language model: interpolated modified Kneser-Ney (Chen and Goodman, 1999).

``CharLM.fit(texts, order=5)`` counts the character n-grams of the texts, each text padded at
its start with ``order - 1`` boundary marks (``BOUNDARY``, a character that does not occur in
text). The probability of a character after a context of ``order - 1`` characters is

    P(c | h) = max(N(h c) - D(N(h c)), 0) / N(h .) + gamma(h) * P(c | h')

where ``h'`` drops the first character of ``h``, the counts ``N`` are raw counts at the highest
order and continuation counts (how many different characters precede the n-gram) below it,
``D`` is one of three discounts per order (for counts 1, 2 and 3 or more, estimated from the
counts of counts), and ``gamma(h)`` gives the discounted mass to the lower order. A context never
seen falls back to the lower order; the lowest order interpolates with a uniform distribution
over the characters seen plus one, so an unseen character has a probability above zero.

``prune`` drops the highest-order n-grams seen once, which keeps a model small; the
discounts are those of the full counts. ``logprob`` and ``score`` give natural logarithms.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

BOUNDARY: Final = "\x02"
"""The mark that pads the start of a text: a control character that text does not hold."""

_LEVELS: Final = 3  # discounts for counts 1, 2 and 3 or more


@dataclass(slots=True)
class _Order:
    """The counts of one order: for each context, its characters' counts."""

    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    discounts: tuple[float, float, float] = (0.5, 0.5, 0.5)
    # per context: total, and how many characters were seen 1, 2, 3+ times
    stats: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)

    def finish(self) -> None:
        self.stats = {}
        for context, following in self.counts.items():
            total = sum(following.values())
            ones = sum(1 for count in following.values() if count == 1)
            twos = sum(1 for count in following.values() if count == 2)  # noqa: PLR2004
            self.stats[context] = (total, ones, twos, len(following) - ones - twos)


class CharLM:
    """A character n-gram model; build one with ``fit`` or ``from_data``."""

    __slots__ = ("_orders", "_vocabulary", "order")

    def __init__(self, order: int, orders: list[_Order], vocabulary: frozenset[str]) -> None:
        self.order = order
        self._orders = orders  # _orders[k]: contexts of length k
        self._vocabulary = vocabulary

    @classmethod
    def fit(cls, texts: Iterable[str], *, order: int = 5, prune: bool = False) -> "CharLM":
        """The model of ``texts``; ``order`` is the n-gram length (2 or more)."""
        if order < 2:  # noqa: PLR2004 - a bigram is the least that has a context
            raise ValueError(f"the order is 2 or more, not {order}")
        highest: dict[str, Counter[str]] = {}
        vocabulary: set[str] = set()
        pad = BOUNDARY * (order - 1)
        for text in texts:
            if BOUNDARY in text:
                raise ValueError("a text holds the boundary mark")
            vocabulary.update(text)
            padded = pad + text
            for i in range(order - 1, len(padded)):
                highest.setdefault(padded[i - order + 1 : i], Counter())[padded[i]] += 1
        orders = [_Order() for _ in range(order)]
        orders[order - 1].counts = {h: dict(c) for h, c in highest.items()}
        # Continuation counts: N1+(. h c), the number of different characters before h c.
        for k in range(order - 2, -1, -1):
            seen: dict[str, Counter[str]] = {}
            for context, following in orders[k + 1].counts.items():
                shorter = context[1:]
                for char in following:
                    seen.setdefault(shorter, Counter())[char] += 1
            orders[k].counts = {h: dict(c) for h, c in seen.items()}
        for level in orders:
            level.discounts = _discounts(level.counts)
            if prune and level is orders[-1]:
                level.counts = {
                    h: kept
                    for h, f in level.counts.items()
                    if (kept := {c: n for c, n in f.items() if n > 1})
                }
            level.finish()
        return cls(order, orders, frozenset(vocabulary))

    def prob(self, char: str, context: str) -> float:
        """P(``char`` | the last ``order - 1`` characters of ``context``, padded at the start)."""
        history = (BOUNDARY * (self.order - 1) + context)[-(self.order - 1) :]
        probability = 1.0 / (len(self._vocabulary) + 1)
        for k in range(self.order):
            level = self._orders[k]
            h = history[len(history) - k :] if k else ""
            stats = level.stats.get(h)
            if stats is None:
                continue
            total, ones, twos, more = stats
            d1, d2, d3 = level.discounts
            count = level.counts[h].get(char, 0)
            discount = 0.0 if count == 0 else (d1, d2, d3)[min(count, _LEVELS) - 1]
            gamma = (d1 * ones + d2 * twos + d3 * more) / total
            probability = max(count - discount, 0.0) / total + gamma * probability
        return probability

    def logprob(self, char: str, context: str) -> float:
        """The natural logarithm of ``prob``."""
        return math.log(self.prob(char, context))

    def score(self, text: str, context: str = "") -> float:
        """The log probability of ``text`` following ``context`` (natural logarithm)."""
        total = 0.0
        history = context
        for char in text:
            total += self.logprob(char, history)
            history = (history + char)[-(self.order - 1) :]
        return total

    def perplexity(self, texts: Iterable[str]) -> float:
        """The per-character perplexity of ``texts``, each from the start of a text."""
        total, chars = 0.0, 0
        for text in texts:
            total += self.score(text)
            chars += len(text)
        return math.exp(-total / chars) if chars else math.inf

    @property
    def size(self) -> int:
        """How many n-gram counts the model holds."""
        return sum(len(f) for level in self._orders for f in level.counts.values())

    def to_data(self) -> dict[str, Any]:
        """The model as JSON-ready data; ``from_data`` reads it back."""
        return {
            "order": self.order,
            "vocabulary": "".join(sorted(self._vocabulary)),
            "orders": [
                {
                    "discounts": list(level.discounts),
                    "counts": {h: dict(sorted(f.items())) for h, f in sorted(level.counts.items())},
                }
                for level in self._orders
            ],
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "CharLM":
        """The model ``to_data`` wrote."""
        orders = []
        for item in data["orders"]:
            level = _Order(
                {h: dict(f) for h, f in item["counts"].items()},
                (
                    float(item["discounts"][0]),
                    float(item["discounts"][1]),
                    float(item["discounts"][2]),
                ),
            )
            level.finish()
            orders.append(level)
        return cls(int(data["order"]), orders, frozenset(data["vocabulary"]))


def _discounts(counts: Mapping[str, Mapping[str, int]]) -> tuple[float, float, float]:
    """Modified Kneser-Ney discounts D1, D2, D3+ from the counts of counts (Chen and Goodman)."""
    of = Counter(count for following in counts.values() for count in following.values())
    n1, n2, n3, n4 = of[1], of[2], of[3], of[4]
    if not (n1 and n2 and n3 and n4):
        return (0.5, 0.75, 0.9)  # too few counts to estimate: a small model's usual values
    y = n1 / (n1 + 2 * n2)
    return (
        max(0.0, 1 - 2 * y * n2 / n1),
        max(0.0, 2 - 3 * y * n3 / n2),
        max(0.0, 3 - 4 * y * n4 / n3),
    )
