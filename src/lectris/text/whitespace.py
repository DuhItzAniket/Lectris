r"""Whitespace rules: line breaks, runs of spaces inside lines, and spaces at line ends.

``RULES`` lists them in the recommended order. ``line_breaks`` comes first, because the other two
recognise a line end only as ``"\n"``; ``collapse`` and ``trim`` touch different runs of spaces
and can run in either order.

The patterns match a run of spaces only from its first character (a lookbehind refuses the
others) and never give characters back (possessive quantifiers), so a long run costs linear time.
"""

import re
from typing import Final

from lectris.edits import Revision, substitute

_LINE_BREAKS: Final = "whitespace.line_breaks"
_COLLAPSE: Final = "whitespace.collapse"
_TRIM: Final = "whitespace.trim"

_PARAGRAPH_SEPARATOR: Final = "\u2029"
_LINE_BREAK: Final = re.compile("\r\n?|[\u2028\u2029]")
_INNER_RUN: Final = re.compile(r"(?<=\S)[ \t]{2,}+(?=\S)")
_EDGE_SPACE: Final = re.compile(
    r"\A[ \t\n]++|(?<![ \t\n])[ \t\n]++\Z|(?<![ \t])[ \t]++(?=\n)|(?<=\n)[ \t]++"
)


def line_breaks(text: str, /) -> Revision:
    r"""Make every line break ``"\n"``, and every paragraph separator a blank line.

    ``"\r\n"`` (Windows), a lone ``"\r"`` (classic Mac OS) and U+2028 LINE SEPARATOR each
    become one ``"\n"``. U+2029 PARAGRAPH SEPARATOR becomes ``"\n\n"``: a blank line, which is
    how plain text separates paragraphs. One edit is recorded per break.

    Left alone: U+0085 NEXT LINE, because text decoded as Latin-1 instead of Windows-1252 has it
    where an ellipsis was; form feeds, which plain-text input uses between pages; and vertical
    tabs.

    >>> line_breaks("one\r\ntwo\rthree\u2029four").text
    'one\ntwo\nthree\n\nfour'
    """
    return substitute(text, _LINE_BREAK, _plain_break, _LINE_BREAKS)


def _plain_break(match: "re.Match[str]") -> str:
    return "\n\n" if match.group() == _PARAGRAPH_SEPARATOR else "\n"


def collapse(text: str, /) -> Revision:
    r"""Replace each run of two or more spaces and tabs between two words by one space.

    The run must have a character that is not whitespace on both sides on the same line.
    One edit is recorded per run.

    Left alone: a single tab between words, which may separate the columns of a table; runs at
    the start or end of a line, which are ``trim``'s; line breaks; and runs next to other
    whitespace such as a no-break space (``unicode.compatibility`` turns those into spaces).

    >>> collapse("a  wide \t gap").text
    'a wide gap'
    """
    return substitute(text, _INNER_RUN, " ", _COLLAPSE)


def trim(text: str, /) -> Revision:
    r"""Remove the spaces and tabs at the start and end of each line, and the block's blank edges.

    Blank lines (empty or only spaces and tabs) at the start and end of the block are removed
    with their line breaks; a blank line between two lines with text stays, emptied. One edit is
    recorded per run removed. Indentation goes too, so text whose layout lives in its leading
    spaces (code, verse) should not use this rule.

    Left alone: every character other than a space, a tab, or a ``"\n"`` at a block edge.

    >>> trim("\n  first  \n second\n\n").text
    'first\nsecond'
    """
    return substitute(text, _EDGE_SPACE, "", _TRIM)


RULES: Final = (line_breaks, collapse, trim)
