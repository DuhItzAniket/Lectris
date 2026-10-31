r"""Punctuation rules: spaces around punctuation, quotes, dashes and ellipses.

``RULES`` lists them in the recommended order. ``ellipsis`` comes first, so that a spaced
ellipsis is one mark by the time ``spacing`` looks at the dots; ``spacing`` comes last.
"""

import re
from typing import Final, Literal

from lectris.edits import Revision, substitute

_SPACING: Final = "punctuation.spacing"
_QUOTES: Final = "punctuation.quotes"
_DASHES: Final = "punctuation.dashes"
_ELLIPSIS: Final = "punctuation.ellipsis"

_OPENERS: Final = "([{"
_CLOSERS: Final = ")]}"
_LOW_MARKS: Final = ",."
_HIGH_MARKS: Final = ";:!?"
_NUMBER_MARKS: Final = ".,:"
_DOTS: Final = ".\u2026"
_OPENING_QUOTES: Final = "\"'\u2018\u201a\u201c\u201e\u00ab\u2039"
# What may follow a mark whose space is removed: punctuation that closes a word.
_WORD_END: Final = ",.;:!?)]}\"'\u2019\u201d\u00bb\u203a\u2026"
_WORD_START: Final = _OPENERS + _OPENING_QUOTES
_BRACKET: Final = re.compile(r"[(\[{)\]}]")
# A run of spaces is matched only from its first character and never given back, so a long run
# costs linear time.
_SPACE_BY_MARK: Final = re.compile(r"(?<=[(\[{])[ \t]++|(?<![ \t])[ \t]++(?=[,.;:!?)\]}])")
_DIGIT_AFTER: Final = re.compile(r"[ \t]*+\d")
_DOT_AFTER: Final = re.compile("[ \t]*+[.\u2026]")

_TO_STRAIGHT: Final = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
}
_TYPOGRAPHIC_QUOTES: Final = re.compile("[\u2018\u2019\u201a\u201b\u201c-\u201f\u2032\u2033]+")
_STRAIGHT_QUOTE: Final = re.compile("['\"]")
_OPENING_CONTEXT: Final = "([{\u2018\u201c\u00ab\u2039\u2013\u2014"
_LEFT_SINGLE: Final = "\u2018"
_RIGHT_SINGLE: Final = "\u2019"
_LEFT_DOUBLE: Final = "\u201c"
_RIGHT_DOUBLE: Final = "\u201d"

_DASH_VARIANT: Final = re.compile(r"[\u2010\u2011]|(?<=\d)\u2012(?=\d)")

_ELLIPSIS_CHARACTER: Final = "\u2026"
_SPACED_DOTS: Final = (
    r"(?<![.\u2026])(?<![.\u2026][ \u00a0\u202f])"
    r"\.[ \u00a0\u202f]\.[ \u00a0\u202f]\.(?![ \u00a0\u202f]?[.\u2026])"
)
_TO_THREE_DOTS: Final = re.compile(rf"\u2026|{_SPACED_DOTS}")
_TO_CHARACTER: Final = re.compile(rf"(?<![.\u2026])\.\.\.(?![.\u2026])|{_SPACED_DOTS}")


def spacing(text: str, /, *, high_punctuation: bool = False) -> Revision:
    r"""Remove the spaces OCR puts before closing punctuation and after opening brackets.

    Removed: spaces and tabs before ``,`` ``.`` ``)`` ``]`` ``}`` and after ``(`` ``[`` ``{``.
    With ``high_punctuation=True``, also those before ``;`` ``:`` ``!`` ``?``, which are kept
    by default because French typography puts a space there (``Pourquoi ?``). One edit is
    recorded per run of spaces.

    Evidence needed: before a mark, a character that is not whitespace or an opening bracket
    right before the space, and the mark ending a word, that is, followed by whitespace, the end
    of the text or more closing punctuation. After an opening bracket, the bracket starting a
    word (after whitespace, the start of the text, another opening bracket or an opening quote)
    and text that is not a closing bracket after the space. Before a closing bracket, also its
    opening bracket starting a word, when the text has one.

    Left alone: line breaks; numbers and times (``3 . 14``, ``1 , 2``, ``10 : 30``), which are
    for ``numbers`` to judge; dots of an ellipsis (``. . .``, ``wait ...``); a mark joined to
    the next word (``the .gitignore file``; in ``a ,b`` the space may belong after the comma);
    empty brackets (``[ ]``); and brackets inside a word (``f( x )``).

    >>> spacing("Paris , Lyon ( and Nice ) .").text
    'Paris, Lyon (and Nice).'
    """
    marks = _CLOSERS + _LOW_MARKS + (_HIGH_MARKS if high_punctuation else "")
    openers = _bracket_pairs(text)

    def remove(match: "re.Match[str]") -> str | None:
        start, end = match.span()
        if _after_opener(text, start, end) or _before_mark(text, start, end, marks, openers):
            return ""
        return None

    return substitute(text, _SPACE_BY_MARK, remove, _SPACING)


def _bracket_pairs(text: str) -> dict[int, int]:
    """For each closing bracket that has one, the position of its opening bracket."""
    open_positions: dict[str, list[int]] = {opener: [] for opener in _OPENERS}
    pairs: dict[int, int] = {}
    for match in _BRACKET.finditer(text):
        bracket = match.group()
        if bracket in _OPENERS:
            open_positions[bracket].append(match.start())
        else:
            waiting = open_positions[_OPENERS[_CLOSERS.index(bracket)]]
            if waiting:
                pairs[match.start()] = waiting.pop()
    return pairs


def _ends_word(text: str, position: int) -> bool:
    """Whether a word ends at ``position``: the end, whitespace, or closing punctuation."""
    return position == len(text) or text[position].isspace() or text[position] in _WORD_END


def _starts_word(text: str, opener: int) -> bool:
    """Whether the opening bracket at ``opener`` starts a word."""
    return opener == 0 or text[opener - 1].isspace() or text[opener - 1] in _WORD_START


def _after_opener(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` follows an opening bracket that starts a word."""
    opener = start - 1
    if opener < 0 or text[opener] not in _OPENERS or not _starts_word(text, opener):
        return False
    return end < len(text) and not text[end].isspace() and text[end] not in _CLOSERS


def _before_mark(text: str, start: int, end: int, marks: str, openers: dict[int, int]) -> bool:
    """Whether ``text[start:end]`` sits between a word and a mark in ``marks`` that ends it."""
    if start == 0 or end == len(text) or text[end] not in marks:
        return False
    previous, mark = text[start - 1], text[end]
    if previous.isspace() or previous in _OPENERS:
        return False
    if mark in _CLOSERS:
        opener = openers.get(end)
        return (opener is None or _starts_word(text, opener)) and _ends_word(text, end + 1)
    in_number = (
        mark in _NUMBER_MARKS
        and previous.isdecimal()
        and _DIGIT_AFTER.match(text, end + 1) is not None
    )
    in_dots = mark == "." and (previous in _DOTS or _DOT_AFTER.match(text, end + 1) is not None)
    return not in_number and not in_dots and _ends_word(text, end + 1)


def quotes(text: str, /, *, style: Literal["straight", "curly"] = "straight") -> Revision:
    r"""Make quotation marks straight (``'`` and ``"``) or curly.

    ``style="straight"``: the curly quotes U+2018, U+2019, U+201C and U+201D, the low quotes
    U+201A and U+201E, the reversed quotes U+201B and U+201F, and the primes U+2032 and U+2033
    become ``'`` or ``"``. One edit is recorded per run of adjacent quotes.

    ``style="curly"``: each straight quote becomes curly by its context. It opens (U+2018 or
    U+201C) at the start of the text or after whitespace, an opening bracket, an opening quote
    or a dash, and closes (U+2019 or U+201D) after anything else, so the apostrophe of
    ``don't`` becomes U+2019. A single quote that opens before a digit is an elision (``'90s``)
    and becomes U+2019 too. One edit is recorded per quote. The context cannot tell an elision
    before a letter (``'tis``) from an opening quote, which it is taken to be.

    Left alone in both styles: guillemets (``«`` ``»`` and the single U+2039 and U+203A), the
    quotation marks of French, German and other languages; and U+02BC MODIFIER LETTER
    APOSTROPHE, a letter in some orthographies. The curly style also leaves a straight quote
    after a digit, which is a prime for feet, inches, minutes or seconds (``5'10"``), and one
    with whitespace or an edge of the text on both sides, which neither opens nor closes
    anything.

    >>> quotes("\u201cIt\u2019s \u201ahere\u2018\u201d").text
    '"It\'s \'here\'"'
    >>> quotes('"Don\'t," she said.', style="curly").text == "\u201cDon\u2019t,\u201d she said."
    True
    """
    if style == "straight":
        return substitute(
            text,
            _TYPOGRAPHIC_QUOTES,
            lambda match: "".join(_TO_STRAIGHT[quote] for quote in match.group()),
            _QUOTES,
        )
    if style == "curly":
        return _curly_quotes(text)
    raise ValueError(f"no quote style {style!r}; the styles are 'straight' and 'curly'")


def _curly_quotes(text: str) -> Revision:
    chosen: dict[int, str] = {}

    def curl(match: "re.Match[str]") -> str | None:
        position = match.start()
        previous = chosen.get(position - 1, text[position - 1]) if position else None
        following = text[position + 1] if position + 1 < len(text) else None
        curly = _curly(match.group(), previous, following)
        if curly is not None:
            chosen[position] = curly
        return curly

    return substitute(text, _STRAIGHT_QUOTE, curl, _QUOTES)


def _curly(quote: str, previous: str | None, following: str | None) -> str | None:
    """The curly form of a straight quote between ``previous`` and ``following``, if any."""
    if previous is not None and previous.isdecimal():
        return None
    opens = previous is None or previous.isspace() or previous in _OPENING_CONTEXT
    if opens and (following is None or following.isspace()):
        return None
    if quote == '"':
        return _LEFT_DOUBLE if opens else _RIGHT_DOUBLE
    if opens and not (following is not None and following.isdecimal()):
        return _LEFT_SINGLE
    return _RIGHT_SINGLE


def dashes(text: str, /) -> Revision:
    r"""Replace the hyphen variants by the hyphen-minus ``-``.

    U+2010 HYPHEN and U+2011 NON-BREAKING HYPHEN become ``-`` wherever they are. U+2012 FIGURE
    DASH becomes ``-`` between two digits, where it joins the groups of a number such as a
    telephone number. One edit is recorded per character.

    Left alone: the en dash U+2013 (number ranges) and the em dash U+2014 (breaks in a
    sentence), which carry meaning a hyphen does not; U+2212 MINUS SIGN; a figure dash that is
    not between digits; and ``--``, which may stand for a dash or be literal (command options).

    >>> dashes("well\u2010known, 555\u20120199").text
    'well-known, 555-0199'
    """
    return substitute(text, _DASH_VARIANT, "-", _DASHES)


def ellipsis(text: str, /, *, style: Literal["three-dots", "character"] = "three-dots") -> Revision:
    r"""Write each ellipsis as three dots or as the one character ``…`` (U+2026).

    ``style="three-dots"``: every ``…`` becomes ``...``. ``style="character"``: ``...`` becomes
    ``…``. In both styles a spaced ellipsis, three dots with one space, no-break space or narrow
    no-break space between each (``. . .``, as some typesetting and much OCR has it), becomes
    the chosen form. One edit is recorded per ellipsis.

    Left alone: runs of two dots, or of four or more (leaders in a table of contents, a period
    and an ellipsis), with or without spaces, since the dots alone do not say what they are.

    >>> ellipsis("Wait . . . what\u2026").text
    'Wait ... what...'
    """
    if style == "three-dots":
        return substitute(text, _TO_THREE_DOTS, "...", _ELLIPSIS)
    if style == "character":
        return substitute(text, _TO_CHARACTER, _ELLIPSIS_CHARACTER, _ELLIPSIS)
    raise ValueError(f"no ellipsis style {style!r}; the styles are 'three-dots' and 'character'")


RULES: Final = (ellipsis, dashes, quotes, spacing)
