r"""Unicode rules: canonical normalisation, ligatures, invisible characters, compatibility forms.

``RULES`` lists them in the recommended order: invisible characters first, then compatibility
forms and ligatures, and NFC last, because replacing or removing a character can leave a base
letter next to a combining mark that only then composes (``"\uff21\u0301"`` becomes
``"A\u0301"``, which NFC turns into ``"\u00c1"``).
"""

import functools
import re
import unicodedata
from typing import Final

from lectris.edits import Edit, Revision, revise, substitute, unchanged

_NFC: Final = "unicode.nfc"
_LIGATURES: Final = "unicode.ligatures"
_INVISIBLE: Final = "unicode.invisible"
_COMPATIBILITY: Final = "unicode.compatibility"

# Every character below U+0300 is a starter, and none composes with a character before it.
_FIRST_COMBINING: Final = 0x0300

_LIGATURE_LETTERS: Final = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "\u017ft",
    "\ufb06": "st",
}
_LIGATURE: Final = re.compile("[\ufb00-\ufb06]")

_SOFT_HYPHEN: Final = "\u00ad"
_JOINERS: Final = frozenset("\u200c\u200d")
_INVISIBLE_CHARACTER: Final = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")
_FORMAT: Final = "Cf"
_SYMBOL: Final = "So"
_SCRIPT_NEUTRAL_NAMES: Final = ("LATIN ", "FULLWIDTH LATIN ", "COMBINING ")

_FULLWIDTH_OFFSET: Final = 0xFEE0
_FULLWIDTH_FIRST: Final = "\uff01"
_FULLWIDTH_LAST: Final = "\uff5e"
# Unicode's space separators (category Zs) other than U+0020 and U+1680 OGHAM SPACE MARK.
_SPACES: Final = "\u00a0\u2000-\u200a\u202f\u205f\u3000"
_COMPATIBILITY_FORM: Final = re.compile(f"[\uff01-\uff5e{_SPACES}]+")


def nfc(text: str, /) -> Revision:
    r"""Normalise the text to Unicode NFC, with one edit per character sequence that changes.

    A sequence is a starter (a character of combining class 0) with the combining marks after
    it, joined to its neighbours where NFC composes across them (Hangul jamo, some Indic vowel
    signs). Typical edits compose a letter and a combining accent into one character, put
    stacked marks in canonical order, and replace singletons such as U+212B ANGSTROM SIGN by
    their canonical equivalent. NFC changes how text is encoded, never how it reads, so the rule
    needs no further evidence. It applies no compatibility mappings (see ``compatibility``).

    >>> [(edit.start, edit.end) for edit in nfc("cafe\u0301 cre\u0300me").edits]
    [(3, 5), (8, 10)]
    """
    if unicodedata.is_normalized("NFC", text):
        return unchanged(text)
    edits: list[Edit] = []
    for start, end in _nfc_sequences(text):
        before = text[start:end]
        after = unicodedata.normalize("NFC", before)
        if after != before:
            edits.append(Edit(_NFC, start, end, before, after))
    return revise(text, edits)


@functools.lru_cache(maxsize=4096)
def _begins_sequence(character: str) -> bool:
    """Whether a character starts a sequence: a starter whose decomposition starts with one.

    U+0F73, U+0F75 and U+0F81 are starters that decompose into combining marks only; they
    belong to the sequence before them.
    """
    if ord(character) < _FIRST_COMBINING:
        return True
    first = unicodedata.normalize("NFD", character)[0]
    return unicodedata.combining(character) == 0 and unicodedata.combining(first) == 0


def _nfc_sequences(text: str) -> list[tuple[int, int]]:
    """The spans NFC can normalise one at a time, covering ``text`` from start to end.

    Each candidate begins with a starter and runs to the next. NFC composes across a boundary
    only between the candidate's first starter and the starter right before it, so a candidate
    joins the span before it exactly when normalising the two together differs from
    normalising them apart.
    """
    starts = [0] + [i for i in range(1, len(text)) if _begins_sequence(text[i])]
    ends = [*starts[1:], len(text)]
    spans: list[tuple[int, int]] = []
    span_start, span_end = starts[0], ends[0]
    for start, end in zip(starts[1:], ends[1:], strict=True):
        if ord(text[start]) >= _FIRST_COMBINING:
            together = unicodedata.normalize("NFC", text[span_start:end])
            apart = unicodedata.normalize("NFC", text[span_start:start]) + unicodedata.normalize(
                "NFC", text[start:end]
            )
            if together != apart:
                span_end = end
                continue
        spans.append((span_start, span_end))
        span_start, span_end = start, end
    spans.append((span_start, span_end))
    return spans


def ligatures(text: str, /) -> Revision:
    r"""Replace the Latin typographic ligatures U+FB00 to U+FB06 by the letters they join.

    ``ﬀ ﬁ ﬂ ﬃ ﬄ ﬆ`` become ``ff fi fl ffi ffl st``. U+FB05 becomes U+017F LATIN SMALL LETTER
    LONG S and ``t``, as Unicode decomposes it: whether to modernise a long s is a spelling
    decision, not a ligature's. A ligature character is its own evidence; one edit is recorded
    per ligature.

    Left alone: ``Æ æ Œ œ``, which are letters in Danish, Norwegian, French and other languages,
    and ``Ĳ ĳ``, which Dutch treats as one letter in places (``Ĳsselmeer``).

    >>> ligatures("\ufb01nal of\ufb01ce").text
    'final office'
    """
    return substitute(text, _LIGATURE, lambda match: _LIGATURE_LETTERS[match.group()], _LIGATURES)


def invisible(text: str, /) -> Revision:
    r"""Remove invisible formatting characters that OCR and PDF text layers leave in words.

    Removed: U+200B ZERO WIDTH SPACE, U+2060 WORD JOINER, U+FEFF (byte order mark, or zero width
    no-break space), U+00AD SOFT HYPHEN, and U+200C ZERO WIDTH NON-JOINER and U+200D ZERO WIDTH
    JOINER where they do not shape the text. One edit is recorded per run of adjacent changes.

    A soft hyphen that ends a line (only spaces, tabs and characters this rule removes follow
    it before the ``"\n"``) marks where a word was hyphenated, the strongest evidence there
    is: it is kept for ``hyphenation.join``, which always rejoins the word there. Of several
    soft hyphens at a line end, only the last is kept. One with no text on the next line to
    rejoin (at the end of the block, or before a blank line) is removed.

    A joiner is kept when the nearest character on either side that is not a format character
    is a letter or mark of a script other than Latin (fullwidth Latin letters count as Latin),
    or a symbol such as an emoji: Arabic, Persian and Indic spelling and emoji sequences depend
    on joiners.

    Left alone: the direction marks U+200E and U+200F and the other bidirectional controls
    (U+061C, U+202A to U+202E, U+2066 to U+2069), which decide how mixed-direction text is
    displayed; and the other format characters (Arabic number signs, tag characters in emoji
    flags, invisible mathematical operators), which carry meaning.

    >>> invisible("co\u200boperate\nexam\u00ad\nple").text
    'cooperate\nexam\xad\nple'
    """
    positions = [match.start() for match in _INVISIBLE_CHARACTER.finditer(text)]
    if not positions:
        return unchanged(text)
    shaping = _shaping_joiners(text, [p for p in positions if text[p] in _JOINERS])
    replacements: dict[int, str] = {}
    for position in positions:
        if position not in shaping and text[position] != _SOFT_HYPHEN:
            replacements[position] = ""
    for position in positions:
        if text[position] == _SOFT_HYPHEN:
            end = _line_end(text, position, replacements)
            if end is None or not _next_line_has_text(text, end):
                replacements[position] = ""
    return revise(text, _runs(text, replacements, _INVISIBLE))


def _shaping_joiners(text: str, joiners: list[int]) -> set[int]:
    """The joiners (positions in text order) whose neighbour on either side is text they shape.

    A joiner's neighbours are the nearest characters before and after it that are not format
    characters.
    """
    before = _nearest_visible(text, joiners, -1)
    after = _nearest_visible(text, joiners[::-1], 1)[::-1]
    return {
        position
        for position, left, right in zip(joiners, before, after, strict=True)
        if (left is not None and _shaped_by_joiners(left))
        or (right is not None and _shaped_by_joiners(right))
    }


def _nearest_visible(text: str, joiners: list[int], step: int) -> list[str | None]:
    """For each joiner in the order given, the nearest character ``step`` by ``step`` from it
    that is not a format character, or ``None`` at the edge of the text.

    A scan stops at the joiner before it in the same direction and takes that joiner's answer
    when only format characters lie between, so each character is looked at once: a long run
    of joiners costs linear time, not quadratic.
    """
    found: list[str | None] = []
    stop = -1 if step < 0 else len(text)
    for position in joiners:
        index = position + step
        while index != stop and unicodedata.category(text[index]) == _FORMAT:
            index += step
        if index != stop:
            found.append(text[index])
        else:
            found.append(found[-1] if found else None)
        stop = position
    return found


def _shaped_by_joiners(character: str) -> bool:
    """A symbol (emoji), or a letter or mark that is neither Latin (fullwidth Latin included)
    nor a generic diacritic."""
    category = unicodedata.category(character)
    if category == _SYMBOL:
        return True
    if category[0] not in "LM":
        return False
    return not unicodedata.name(character, "").startswith(_SCRIPT_NEUTRAL_NAMES)


def _next_line_has_text(text: str, end: int) -> bool:
    """Whether the line after the line break at ``end`` has a visible character: something to
    rejoin a hyphenated word with. Whitespace and format characters do not count."""
    if end >= len(text):
        return False
    following = text.find("\n", end + 1)
    line = text[end + 1 :] if following == -1 else text[end + 1 : following]
    return any(not char.isspace() and unicodedata.category(char) != _FORMAT for char in line)


def _line_end(text: str, position: int, replacements: dict[int, str]) -> int | None:
    """Where the line of ``position`` ends (its line break, or the end of the text) when only
    spaces, tabs and removed characters follow it there; ``None`` when anything else does.

    Another soft hyphen does not count as removed, so only the last one at a line end is kept.
    """
    after = position + 1
    while after < len(text) and (
        text[after] in " \t" or (replacements.get(after) == "" and text[after] != _SOFT_HYPHEN)
    ):
        after += 1
    return after if after == len(text) or text[after] == "\n" else None


def _runs(text: str, replacements: dict[int, str], rule: str) -> list[Edit]:
    """One edit per run of adjacent single-character replacements."""
    runs: list[list[int]] = []
    for position in sorted(replacements):
        if runs and runs[-1][-1] + 1 == position:
            runs[-1].append(position)
        else:
            runs.append([position])
    return [
        Edit(
            rule,
            run[0],
            run[-1] + 1,
            text[run[0] : run[-1] + 1],
            "".join(replacements[position] for position in run),
        )
        for run in runs
    ]


def compatibility(text: str, /) -> Revision:
    r"""Replace fullwidth ASCII forms and Unicode spaces by their plain ASCII equivalents.

    The fullwidth forms U+FF01 to U+FF5E become the ASCII characters they are wide versions of
    (``"\uff21\uff42\uff43\uff11"`` becomes ``"Abc1"``). The space separators other than
    U+0020 (U+00A0 NO-BREAK SPACE, the spaces U+2000 to U+200A, U+202F NARROW NO-BREAK SPACE,
    U+205F MEDIUM MATHEMATICAL SPACE, U+3000 IDEOGRAPHIC SPACE) become one ``" "`` each: the
    output is plain text, where the width and the no-break property of a space have no effect.
    One edit is recorded per run of adjacent changes.

    This is a deliberately small part of NFKC. Full NFKC would also turn ``x²`` into ``x2``,
    ``½`` into three characters, ``ª`` into ``a`` and ``™`` into ``TM``: changes to what the
    text says, not to how it is encoded. Ligatures have their own rule, and the ellipsis ``…``
    is ``punctuation.ellipsis``'s.

    Left alone: U+1680 OGHAM SPACE MARK, which is visible in Ogham; tabs and line breaks
    (``whitespace``); zero-width characters (``invisible``). In Chinese and Japanese text
    fullwidth punctuation and the ideographic space are the norm, so the rule is meant for
    Latin-script text.

    >>> compatibility("\uff08\uff41\uff09 10\u00a0km").text
    '(a) 10 km'
    """
    return substitute(text, _COMPATIBILITY_FORM, _plain_forms, _COMPATIBILITY)


def _plain_forms(match: "re.Match[str]") -> str:
    return "".join(
        chr(ord(character) - _FULLWIDTH_OFFSET)
        if _FULLWIDTH_FIRST <= character <= _FULLWIDTH_LAST
        else " "
        for character in match.group()
    )


RULES: Final = (invisible, compatibility, ligatures, nfc)
