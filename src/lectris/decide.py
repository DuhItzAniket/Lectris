"""The decision layer: which candidate edits are accepted, and why (architecture §11).

``decide(text, candidates, policy)`` judges each candidate under a policy, resolves overlaps
between those that pass, and returns the revision of ``text`` that makes the accepted ones, with
a ``Decision`` for every candidate.

Policies:

- ``PARITY`` (``Parity()``): accepts exactly the candidates a LECTRIS v0.1 rule would have
  applied, those whose feature ``v01`` is 1. It is the default, so output is v0.1's
  (ADR-0006).
- ``Threshold(score, threshold)``: accepts the candidates whose ``score`` (a probability that the
  edit is right) is at least ``threshold``. It promises nothing about harm; the risk-controlled
  policy of Phase 7 chooses its threshold with a guarantee.

Overlaps. Candidates that pass may overlap (two readings of one token). The accepted set is the
one, among sets of candidates that do not overlap, that maximises the expected number of
characters changed rightly, the sum of ``probability * size`` (``size`` is the longer of
``before`` and ``after``, at least 1; under ``PARITY`` the probability is 1). It is found by
weighted interval scheduling. A tie leaves the text as it was. Two candidates overlap when their
spans share a character, when both insert at one place, or when one inserts inside the other's
span; an insertion at the edge of another candidate's span does not overlap it.
"""

from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final, Protocol

from lectris.edits import Candidate, Decision, Revision, revise


class Policy(Protocol):
    """How candidates are judged: whether each one passes, its probability and the bar."""

    def judge(self, candidate: Candidate) -> tuple[bool, float | None, float | None, str]:
        """``(passes, probability, threshold, reason)`` for ``candidate``."""
        ...


@dataclass(frozen=True, slots=True)
class Parity:
    """Accepts the candidates whose feature ``v01`` is 1: what LECTRIS v0.1 applied."""

    def judge(self, candidate: Candidate) -> tuple[bool, float | None, float | None, str]:
        if candidate.feature("v01") == 1.0:
            return True, None, None, "the v0.1 rule applies it"
        return False, None, None, "the v0.1 rule declines it"


PARITY: Final = Parity()
"""The default policy: v0.1's behaviour."""


@dataclass(frozen=True, slots=True)
class Guarantee:
    """What a risk-controlled policy promises, and for which engine.

    With probability at least ``1 - delta`` over the calibration pages, the expected harm rate on
    new pages like them, from ``engine``'s ``model``, is at most ``alpha`` (ADR-0002, ADR-0008).
    ``threshold`` is ``None`` when no threshold could be certified: then no guess is accepted.
    """

    alpha: float
    delta: float
    threshold: float | None
    engine: str
    model: str


@dataclass(frozen=True, slots=True)
class Threshold:
    """Accepts the candidates whose ``score`` is at least ``threshold``, both in ``[0, 1]``.

    A risk-controlled threshold (``lectris.models.pack.ModelPack.policy``) carries its
    ``guarantee``.
    """

    score: Callable[[Candidate], float]
    threshold: float
    guarantee: Guarantee | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 1:
            raise ValueError(f"a threshold is between 0 and 1, not {self.threshold!r}")

    def judge(self, candidate: Candidate) -> tuple[bool, float | None, float | None, str]:
        probability = self.score(candidate)
        if not 0 <= probability <= 1:
            raise ValueError(f"a score is a probability in [0, 1], not {probability!r}")
        if probability >= self.threshold:
            return True, probability, self.threshold, "its probability reaches the threshold"
        return False, probability, self.threshold, "its probability is below the threshold"


def decide(text: str, candidates: Iterable[Candidate], policy: Policy = PARITY) -> Revision:
    """The revision of ``text`` that makes the candidates ``policy`` accepts (module docs).

    Every candidate gets a ``Decision``, in the order of their spans. Raises ``ValueError`` if a
    candidate's ``before`` is not what ``text`` holds at its span.
    """
    ordered = sorted(candidates, key=_order)
    judged: list[tuple[Candidate, bool, float | None, float | None, str]] = []
    for candidate in ordered:
        if text[candidate.start : candidate.end] != candidate.before:
            raise ValueError(
                f"{candidate.rule} expected {candidate.before!r} at {candidate.start}, "
                f"found {text[candidate.start : candidate.end]!r}"
            )
        judged.append((candidate, *policy.judge(candidate)))
    passing = [(candidate, probability) for candidate, ok, probability, _, _ in judged if ok]
    accepted = _best_set(passing)
    decisions: list[Decision] = []
    for candidate, ok, probability, threshold, reason in judged:
        if ok and id(candidate) not in accepted:
            decisions.append(
                Decision(candidate, False, "it overlaps a better candidate", probability, threshold)
            )
        else:
            decisions.append(Decision(candidate, ok, reason, probability, threshold))
    edits = (decision.candidate.edit() for decision in decisions if decision.accepted)
    revision = revise(text, edits)
    return Revision(revision.text, revision.edits, tuple(decisions))


def _order(candidate: Candidate) -> tuple[int, int, str, str]:
    return candidate.start, candidate.end, candidate.rule, candidate.after


def _interval(candidate: Candidate) -> tuple[int, int]:
    """The candidate's place on a doubled scale, as a half-open interval: there, overlapping
    (as the module documents it) is plain interval overlap."""
    if candidate.start == candidate.end:
        return 2 * candidate.start, 2 * candidate.start + 1
    return 2 * candidate.start + 1, 2 * candidate.end


def _best_set(passing: list[tuple[Candidate, float | None]]) -> set[int]:
    """The ids of the non-overlapping candidates with the largest total ``probability * size``,
    by weighted interval scheduling; a tie keeps the smaller set (the text as it was)."""
    items = sorted(
        ((_interval(candidate), candidate, 1.0 if p is None else p) for candidate, p in passing),
        key=lambda item: (item[0][1], item[0][0], _order(item[1])),
    )
    ends = [interval[1] for interval, _, _ in items]
    best = [0.0]  # best[k]: the best total of the first k items
    take: list[bool] = []
    previous: list[int] = []
    for k, ((start, _), candidate, probability) in enumerate(items):
        before = bisect_right(ends, start, 0, k)  # items wholly before this one
        weight = probability * max(len(candidate.before), len(candidate.after), 1)
        with_it = weight + best[before]
        take.append(with_it > best[k])
        previous.append(before)
        best.append(with_it if take[k] else best[k])
    chosen: set[int] = set()
    k = len(items)
    while k > 0:
        if take[k - 1]:
            chosen.add(id(items[k - 1][1]))
            k = previous[k - 1]
        else:
            k -= 1
    return chosen
