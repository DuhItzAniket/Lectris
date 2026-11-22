"""Edits: how every text rule records what it changed.

A rule returns a ``Revision``: its output text, and the edits that turn its input into that
output. ``start`` and ``end`` are offsets in the input; edits are sorted and do not overlap, and
``apply_edits(input, revision.edits) == revision.text`` always holds. ``OffsetMap`` maps a span
of a revision's output, or of the output of several revisions in turn, back to the input.

A proposer suggests ``Candidate`` edits instead; ``lectris.decide`` turns each into a
``Decision`` and the accepted ones into the revision's edits.
"""

import re
from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Edit:
    """One change: ``input[start:end]`` (``before``) replaced by ``after``, by ``rule``."""

    rule: str
    start: int
    end: int
    before: str
    after: str

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end:
            raise ValueError(f"an edit needs 0 <= start <= end, not {self.start}..{self.end}")
        if len(self.before) != self.end - self.start:
            raise ValueError(
                f"'before' is {len(self.before)} characters, the span {self.end - self.start}"
            )
        if self.before == self.after:
            raise ValueError(
                f"an edit changes something; {self.rule} replaced {self.before!r} with itself"
            )


@dataclass(frozen=True, slots=True)
class Candidate:
    """An edit a proposer suggests, with the evidence it found, before anything decides on it.

    The span, ``before`` and ``after`` follow ``Edit``'s rules. ``features`` are named numbers
    the decision layer reads, sorted by name, each name once (``feature`` reads one).
    """

    rule: str
    start: int
    end: int
    before: str
    after: str
    features: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        self.edit()  # the same checks as an edit's
        names = [name for name, _ in self.features]
        if names != sorted(set(names)):
            raise ValueError(f"a candidate's features are sorted by name, each once: {names}")

    def edit(self) -> Edit:
        """The edit this candidate would make."""
        return Edit(self.rule, self.start, self.end, self.before, self.after)

    def feature(self, name: str, default: float = 0.0) -> float:
        """The value of the feature ``name``, or ``default`` if the candidate has none."""
        for key, value in self.features:
            if key == name:
                return value
        return default


@dataclass(frozen=True, slots=True)
class Decision:
    """What the decision layer made of a candidate: accepted or not, and why.

    ``probability`` is the candidate's chance of being right and ``threshold`` the bar it had to
    reach, when the policy has them; ``reason`` says in words why it was accepted or declined.
    """

    candidate: Candidate
    accepted: bool
    reason: str
    probability: float | None = None
    threshold: float | None = None


@dataclass(frozen=True, slots=True)
class Revision:
    """A rule's output: the new text, and the edits from the rule's input to it.

    A proposer's revision also keeps its ``decisions``: one per candidate, accepted or declined.
    Its accepted candidates are its edits.
    """

    text: str
    edits: tuple[Edit, ...] = ()
    decisions: tuple[Decision, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.edits)


@dataclass(frozen=True, slots=True)
class _Stage:
    """One revision's edits, laid out for mapping its output offsets back to its input."""

    out_starts: tuple[int, ...]
    out_ends: tuple[int, ...]
    in_starts: tuple[int, ...]
    in_ends: tuple[int, ...]
    shifts: tuple[int, ...]  # shifts[k]: output length minus input length of the first k edits

    @classmethod
    def of(cls, edits: Iterable[Edit]) -> "_Stage":
        ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
        out_starts, out_ends, shifts = [], [], [0]
        position = 0
        for edit in ordered:
            if edit.start < position:
                raise ValueError(f"edits overlap or are out of order at offset {edit.start}")
            position = edit.end
            start = edit.start + shifts[-1]
            out_starts.append(start)
            out_ends.append(start + len(edit.after))
            shifts.append(shifts[-1] + len(edit.after) - len(edit.before))
        return cls(
            tuple(out_starts),
            tuple(out_ends),
            tuple(edit.start for edit in ordered),
            tuple(edit.end for edit in ordered),
            tuple(shifts),
        )

    def origin(self, offset: int) -> tuple[int, int]:
        """The input span the output character at ``offset`` came from (see ``OffsetMap``)."""
        before = bisect_right(self.out_ends, offset)  # edits wholly before the character
        if before < len(self.out_starts) and self.out_starts[before] <= offset:
            return self.in_starts[before], self.in_ends[before]  # an edit wrote it
        kept = offset - self.shifts[before]
        return kept, kept + 1

    def source(self, start: int, end: int) -> tuple[int, int]:
        if start == end:
            position = self.origin(start)[0]
            return position, position
        return self.origin(start)[0], self.origin(end - 1)[1]


@dataclass(frozen=True, slots=True)
class OffsetMap:
    """Where a span of a text came from, through one or more revisions.

    ``OffsetMap.from_edits(revision.edits)`` maps the revision's output back to its input, and
    ``first.then(second)`` maps the output of a later revision back to the input of the first,
    across both. ``source(start, end)`` gives the smallest span of the input that the output span
    came from:

    - a character an edit left alone comes from its own place, so text no edit touched maps
      exactly: ``output[start:end] == input[slice(*source(start, end))]`` for such a span;
    - a character an edit wrote comes from the whole span the edit replaced, so a span that
      reaches into an edit's text covers all of what the edit replaced (an insertion's characters
      come from the empty span where it was inserted);
    - an empty span (a position) maps to where the character at that position came from, and the
      end of the output to the end of the input.

    Offsets are not checked against the text's length: past the end, they map as if the text
    went on unchanged.

    >>> revision = substitute("1O5 apples", "O", "0", "confusables.in_numbers")
    >>> offsets = OffsetMap.from_edits(revision.edits)
    >>> offsets.source(4, 10), offsets.source(0, 3)
    ((4, 10), (0, 3))
    """

    stages: tuple[_Stage, ...] = ()

    @classmethod
    def from_edits(cls, edits: Iterable[Edit]) -> "OffsetMap":
        """The map from a revision's output back to its input, given its edits.

        The edits must not overlap (they may come in any order); ``ValueError`` otherwise.
        """
        return cls((_Stage.of(edits),))

    def then(self, later: "OffsetMap") -> "OffsetMap":
        """The map from ``later``'s output back to this map's input: ``later`` applies after."""
        return OffsetMap(self.stages + later.stages)

    def source(self, start: int, end: int | None = None) -> tuple[int, int]:
        """The input span the output span ``[start, end)`` came from; ``end`` defaults to
        ``start`` (a position). ``ValueError`` unless ``0 <= start <= end``."""
        stop = start if end is None else end
        if not 0 <= start <= stop:
            raise ValueError(f"a span needs 0 <= start <= end, not {start}..{stop}")
        for stage in reversed(self.stages):
            start, stop = stage.source(start, stop)
        return start, stop


def unchanged(text: str) -> Revision:
    """The revision of a rule that changed nothing."""
    return Revision(text)


def apply_edits(text: str, edits: Iterable[Edit]) -> str:
    """``text`` with the edits applied. They must be sorted, not overlap, and match ``text``."""
    pieces: list[str] = []
    position = 0
    for edit in edits:
        if edit.start < position:
            raise ValueError(f"edits overlap or are out of order at offset {edit.start}")
        if text[edit.start : edit.end] != edit.before:
            raise ValueError(
                f"{edit.rule} expected {edit.before!r} at {edit.start}, "
                f"found {text[edit.start : edit.end]!r}"
            )
        pieces.append(text[position : edit.start])
        pieces.append(edit.after)
        position = edit.end
    pieces.append(text[position:])
    return "".join(pieces)


def revise(text: str, edits: Iterable[Edit]) -> Revision:
    """The revision that applies ``edits`` (in any order) to ``text``."""
    ordered = tuple(sorted(edits, key=lambda edit: (edit.start, edit.end)))
    return Revision(apply_edits(text, ordered), ordered)


def substitute(
    text: str,
    pattern: "re.Pattern[str] | str",
    replace: "str | Callable[[re.Match[str]], str | None]",
    rule: str,
) -> Revision:
    """Replace each match of ``pattern``, recording one edit per match that changes the text.

    ``replace`` is a string (expanded like ``re.sub``'s, so ``\\1`` works) or a function of the
    match. A function returning ``None`` leaves that match as it was: the way to decline a match
    the pattern found but the evidence does not support.
    """
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    edits: list[Edit] = []
    for match in compiled.finditer(text):
        after = match.expand(replace) if isinstance(replace, str) else replace(match)
        before = match.group(0)
        if after is None or after == before:
            continue
        edits.append(Edit(rule, match.start(), match.end(), before, after))
    return revise(text, edits)
