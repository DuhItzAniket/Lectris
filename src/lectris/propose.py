"""Proposers: rules that guess, and so suggest candidate edits instead of making them (ADR-0001).

A text rule is a **transform** when its change is right wherever its pattern matches (Unicode,
whitespace, unwrapping, punctuation style), and a **proposer** when it guesses. LECTRIS v0.1's
guessing rules are proposers: ``PROPOSERS`` names them. ``candidates(revision)`` turns what one
of them returned into candidates, each carrying the feature ``v01 = 1``, which says the v0.1
rule, with its own conditions, applies it; ``lectris.decide.PARITY`` accepts exactly those.

Later phases add candidates the v0.1 rules decline (``v01 = 0``), with features that let a
calibrated decision accept some of them (architecture §9).
"""

from typing import Final

from lectris.edits import Candidate, Revision

PROPOSERS: Final = frozenset(
    {
        "confusables.in_numbers",
        "confusables.in_words",
        "numbers.separators",
        "punctuation.spacing",
        "hyphenation.join",
        "noise.drop_lines",
    }
)
"""The ids of the text rules that guess, and so propose: v0.1's repairs."""

V01: Final = "v01"
"""The feature that marks a candidate the v0.1 rule applies (1) or declines (0)."""


def candidates(revision: Revision) -> tuple[Candidate, ...]:
    """The v0.1 rule's edits in ``revision`` as candidates it applies (``v01 = 1``)."""
    return tuple(
        Candidate(edit.rule, edit.start, edit.end, edit.before, edit.after, ((V01, 1.0),))
        for edit in revision.edits
    )
