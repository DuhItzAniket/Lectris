"""Edits: how every text rule records what it changed.

A rule returns a ``Revision``: its output text, and the edits that turn its input into that
output. ``start`` and ``end`` are offsets in the input; edits are sorted and do not overlap, and
``apply_edits(input, revision.edits) == revision.text`` always holds.
"""

import re
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
class Revision:
    """A rule's output: the new text, and the edits from the rule's input to it."""

    text: str
    edits: tuple[Edit, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.edits)


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
