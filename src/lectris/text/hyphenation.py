"""Hyphenation: join the words that typesetting split at a line end.

A word split by typesetting (``"infor-\\nmation"``) survives OCR as a fragment, a hyphen and a
line break. ``join`` puts the word back together where the evidence says the hyphen was only a
line break. A compound broken at its own hyphen (``"well-\\nknown"``) is kept as it is only
when a lexicon says so: without one it cannot be told from a split word.
"""

import re
from typing import Final

from lectris.edits import Edit, Revision, revise
from lectris.lexicon import Lexicon
from lectris.text.lexis import CLITICS, CONJUNCTIONS, LINE_END_HYPHENS

RULE: Final = "hyphenation.join"

_SOFT_HYPHEN: Final = "\N{SOFT HYPHEN}"
_MARKS: Final = "".join(re.escape(mark) for mark in sorted(LINE_END_HYPHENS))
_TOKEN: Final = re.compile(r"\S+")
# The last token of a line: anything that does not end in a letter, digit or hyphen, then the
# letters of the first part, then the line-end hyphen.
_FIRST_PART: Final = re.compile(
    rf"(?P<lead>(?:\S*[^\w{_MARKS}])?)(?P<first>[^\W\d_]+)(?P<hyphen>[{_MARKS}])"
)
# The first token of the next line: the letters of the second part, then whatever is attached.
_SECOND_PART: Final = re.compile(r"(?P<second>[^\W\d_]+)(?P<tail>\S*)")


def _evidence(first: str, second: str, hyphen: str, lexicon: Lexicon | None) -> bool:
    """Whether ``first`` + hyphen + line break + ``second`` is one word split by the line."""
    if hyphen == _SOFT_HYPHEN:
        return True
    if not second[0].islower():
        return False
    # A suspended hyphen before a conjunction, or a French clitic joined by a real hyphen.
    attached = second.lower() in CONJUNCTIONS or second.lower() in CLITICS
    if lexicon is not None:
        joined, compound = first + second, f"{first}-{second}"
        joined_known, compound_known = joined in lexicon, compound in lexicon
        if joined_known and compound_known:
            return lexicon.frequency(joined) > lexicon.frequency(compound)
        if joined_known or compound_known:
            return joined_known
        if first in lexicon and second in lexicon:
            return False
    return (
        not attached
        and len(first) > 1
        and not any(char.isupper() for char in first[1:])
        and not any(char.isupper() for char in second)
    )


def join(text: str, /, *, lexicon: Lexicon | None = None) -> Revision:
    """Join each word hyphenated across a line break, moving the break to after the word.

    ``"the infor-\\nmation is"`` becomes ``"the information\\nis"``. The text keeps its number
    of line breaks, so rules that read lines still see them; when the next line holds nothing
    but the rest of the word, the break moves before the joined word instead (``"the
    infor-\\nmation."`` becomes ``"the\\ninformation."``). Punctuation attached to the second
    part moves with it.

    A candidate is a line whose last token ends with letters and a line-end hyphen, where the
    letters are not attached to another letter, digit or hyphen, followed by a line whose first
    token starts with a letter and holds no hyphen. The line-end hyphens are those of
    ``lectris.text.lexis.LINE_END_HYPHENS``: ``-``, U+2010, U+2011, the soft hyphen U+00AD, and
    the ``¬`` and ``⸗`` that Fraktur and ALTO's ``HYP`` use. The mark is not kept in the joined
    word. The evidence to join:

    - a soft hyphen at a line end is a hyphenation point by definition: always joined;
    - otherwise the second part starts with a lowercase letter (``"Franco-\\nGerman"`` stays);
    - with a ``lexicon``: the joined word is in it and the hyphenated form is not, or both are
      and the joined word has the higher count. The hyphen stays if the hyphenated form is in it
      and the joined word is not (or has a count no higher), or if both parts are words and the
      joined word is not (``"self-\\naware"``). When the lexicon knows none of these, the rules
      without a lexicon decide;
    - without a lexicon, or when it knows none of the forms: the second part is not one of
      ``lexis.CONJUNCTIONS`` after a suspended hyphen (``"pre-\\nand post-war"``, ``"Ein-\\nund
      Ausgang"``) or ``lexis.CLITICS`` (``"fait-\\nil"``, ``"peut-\\nêtre"``), the first part
      has at least two letters (``"e-\\nmail"`` stays), and neither part has a capital letter
      after its first character (``"NATO-\\nled"`` stays). A lexicon that has the joined word
      overrides the conjunction and clitic lists (``"ner-\\nvous"`` with ``nervous``).

    Left alone: a hyphen inside a compound that already has one (``"state-of-the-\\nart"``,
    ``"mother-\\nin-law"``, ``"c'est-\\nà-dire"``), fragments with digits, all-capital words
    (``"INFOR-\\nMATION"``: the second part is not lowercase), anything across a blank line, and
    a word that is alone on both of its lines (joining it would leave an empty line). A word
    split over three lines is left as it is.

    Limits: without a lexicon a compound broken at its own hyphen (``"well-\\nknown"``,
    ``"long-\\nterm"``) cannot be told from a split word and is joined; pass a lexicon for text
    with many compounds. Without a lexicon, a word whose second part is spelled like a
    conjunction or clitic (``"ner-\\nvous"``) is not joined. The lexicon is consulted with the
    words as written, so a case-sensitive lexicon needs the capitalised forms of words that
    start sentences.

    The rule is idempotent and never changes the number of ``"\\n"``.

    >>> join("the infor-\\nmation is here").text
    'the information\\nis here'
    """
    lines = text.split("\n")
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    tokens = [
        [(match.start() + start, match.end() + start) for match in _TOKEN.finditer(line)]
        for line, start in zip(lines, starts, strict=True)
    ]
    edits: list[Edit] = []
    head_taken = [False] * len(lines)
    joined = [False] * len(lines)
    for k in range(len(lines) - 1):
        upper, lower = tokens[k], tokens[k + 1]
        if not upper or not lower:
            continue
        first = _FIRST_PART.fullmatch(text, *upper[-1])
        second = _SECOND_PART.fullmatch(text, *lower[0])
        if first is None or second is None:
            continue
        # A hyphen in the next line's token makes it part of a compound (in-law, à-dire).
        if any(char in LINE_END_HYPHENS for char in second["tail"]):
            continue
        if not _evidence(first["first"], second["second"], first["hyphen"], lexicon):
            continue
        remaining = len(upper) - head_taken[k]
        indent = text[starts[k + 1] : lower[0][0]]
        # A fragment alone on its line, under a line that still ends with a hyphen, is part of
        # a word split over three lines: moving the rest of the word up would expose that
        # hyphen to a second pass.
        above_open = k > 0 and not joined[k - 1] and lines[k - 1].rstrip()[-1:] in LINE_END_HYPHENS
        if len(lower) > 1 and not (remaining == 1 and above_open):
            start, end = first.start("hyphen"), lower[1][0]
            after = f"{second[0]}\n{indent}"
            head_taken[k + 1] = True
        elif remaining > 1 and text[upper[-2][1] - 1] not in LINE_END_HYPHENS:
            start, end = upper[-2][1], lower[0][0]
            after = f"\n{indent}{first['lead']}{first['first']}"
        else:
            continue
        edits.append(Edit(RULE, start, end, text[start:end], after))
        joined[k] = True
    return revise(text, edits)


RULES: Final = (join,)
