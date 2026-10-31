r"""Unwrapping: a paragraph's lines joined into one line.

The rule does not judge whether a hyphen at the end of a line only split a word: that is
``hyphenation.join``'s question, and the built-in profiles run it first. This rule treats every
line-end hyphen attached to a word as one de-hyphenation kept, the hyphen of a compound
(``well-\nknown``), and joins it without a space; run alone on ``exam-\nple``, it gives
``exam-ple``. A suspended hyphen (``pre-\nand post-war``) keeps its space.
"""

import itertools
import re
from typing import Final

from lectris.edits import Edit, Revision, revise
from lectris.text.lexis import CONJUNCTIONS, LINE_END_HYPHENS, SECTION_BREAK

_JOIN_LINES: Final = "unwrap.join_lines"

_DASHES: Final = "\u2013\u2014"
# How a line-end mark is written once its lines are joined, with nothing after it (the word
# goes on) or with a space after it. The marks not listed stay as they are.
_TIGHT_FORM: Final = {"\u00ad": "", "\u00ac": "-", "\u2e17": "-"}
_SPACED_FORM: Final = {"\u00ad": "-", "\u00ac": "-", "\u2e17": "-"}
_LIST_ITEM: Final = re.compile(
    r"[ \t]*+(?:[-*\u2010\u2013\u2014\u2022\u2023\u2043\u25aa\u25cf\u25e6\u00b7]"
    r"|\d{1,3}[.)]|[A-Za-z]\)|\((?:\d{1,3}|[A-Za-z]|[ivxIVX]{1,4})\))[ \t]"
)
_FIRST_WORD: Final = re.compile(r"(\w++)(?=\s|\Z)")
_SPACES: Final = " \t"


def join_lines(text: str, /) -> Revision:
    r"""Join the lines of a paragraph into one line.

    Each line break, with the spaces and tabs around it, becomes one space, except after a
    line-end hyphen (``lexis.LINE_END_HYPHENS``: ``-``, U+2010, U+2011, the soft hyphen U+00AD,
    and the not sign U+00AC and double oblique hyphen U+2E17 that Fraktur type and some OCR
    engines use) or a dash (U+2013, U+2014):

    - when the hyphen or dash is attached to a word and the next line starts with a letter or
      digit, the lines are joined with nothing between them: ``well-\nknown`` gives
      ``well-known``, and ``1914\u2013\n1918`` gives ``1914\u20131918``;
    - when the next line starts with a conjunction followed by a space (``lexis.CONJUNCTIONS``),
      the hyphen is suspended and the space stays: ``pre-\nand post-war`` gives
      ``pre- and post-war``.

    A not sign or double oblique hyphen is written ``-``, the hyphen's form inside a line. A soft
    hyphen marks a split word, so joined tight it is removed (``exam\u00ad\nple`` gives
    ``example``); with a space after it, it is written ``-``.

    The line break is kept, with no edit, next to a blank line, which separates paragraphs;
    before a line that starts a list item (``- ``, ``* ``, ``• ``, ``1. ``, ``2) ``, ``a) ``,
    ``(iv) ``); and on both sides of a section break (``* * *``, ``lexis.SECTION_BREAK``). A
    hyphen or dash with a space before it is punctuation, not part of a word, and is followed by
    a space. One edit is recorded per line break joined, the rewritten hyphen included.

    The rule expects one paragraph: lines it should not join (headings, verse, addresses) belong
    in blocks of their own. It is idempotent: the line breaks it leaves are the kept ones.

    >>> join_lines("A well-\nknown fact\nabout pre-\nand post-war prices:\n- rents").text
    'A well-known fact about pre- and post-war prices:\n- rents'
    """
    lines = text.split("\n")
    edits: list[Edit] = []
    line_start = 0
    for current, following in itertools.pairwise(lines):
        line_break = line_start + len(current)
        line_start = line_break + 1
        left, right = current.rstrip(_SPACES), following.lstrip(_SPACES)
        if _keeps_break(current, left, following, right):
            continue
        start = line_break - (len(current) - len(left))
        end = line_start + (len(following) - len(right))
        mark, joint = _joint(left, right)
        if mark is not None:
            start -= 1
        edits.append(Edit(_JOIN_LINES, start, end, text[start:end], (mark or "") + joint))
    return revise(text, edits)


def _keeps_break(current: str, left: str, following: str, right: str) -> bool:
    """Whether the line break between ``current`` and ``following`` stays: next to a blank
    line, before a list item, or next to a section break."""
    return (
        not left
        or not right
        or _LIST_ITEM.match(following) is not None
        or SECTION_BREAK.fullmatch(current) is not None
        or SECTION_BREAK.fullmatch(following) is not None
    )


def _joint(left: str, right: str) -> tuple[str | None, str]:
    """How ``left`` joins ``right``: the new form of the mark that ends ``left`` (``None`` to
    keep it as it is) and what follows it, ``""`` or ``" "``."""
    mark = left[-1]
    hyphen = mark in LINE_END_HYPHENS
    if not hyphen and mark not in _DASHES:
        return None, " "
    attached = len(left) > 1 and left[-2].isalnum() and right[0].isalnum()
    word = _FIRST_WORD.match(right)
    suspended = hyphen and word is not None and word.group(1).lower() in CONJUNCTIONS
    if attached and not suspended:
        return _TIGHT_FORM.get(mark), ""
    return _SPACED_FORM.get(mark), " "


RULES: Final = (join_lines,)
