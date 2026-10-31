"""Quality: does a line of OCR output read as language, or is it noise?

OCR engines turn scanner specks, ruled lines and pictures into lines such as ``~~~ ,,, ' |||``,
``.:;:.:;`` or ``lllllllll``. These heuristics look at the shape of the characters, not at any
language's words, so they need no dictionary.

``features(text)`` measures the text. Only visible characters count: letters, numbers,
punctuation and symbols (Unicode categories L, N, P and S). Whitespace, combining marks and
format or control characters are left out, so ``"é"`` counts once whether it is composed or
decomposed. Tokens are the whitespace-separated pieces that hold a visible character.

A *leader* (one punctuation or symbol character repeated, with or without spaces between, as in
the dot leaders of a table of contents ``.......`` or ``. . . .``, or a rule ``______``) is
measured as that character once, so that it weighs as one mark next to the words beside it.

``score(text)`` is 1 minus the sum of six penalties, never below 0. Each penalty grows linearly
from 0 where its measure is at *start* to its full weight where the measure is at *end*, and
stays there beyond; it applies only when its condition holds:

=================  ===========================  ==================  ===========  ======
penalty            measure                      condition           start → end  weight
=================  ===========================  ==================  ===========  ======
symbols            ``symbol_ratio``                                 0.6 → 0.85   1.0
repeated letter    the run / ``length``         see below           0.3 → 0.9    0.7
single characters  ``single_char_ratio``        3 or more tokens    0.5 → 1      0.6
thin glyphs        ``thin_glyph_ratio``         3 or more tokens    0.75 → 1     0.3
no vowels          ``vowel_ratio``              6 or more letters   0.15 → 0     0.3
case switches      ``case_switches / letters``                      0.15 → 0.4   0.4
=================  ===========================  ==================  ===========  ======

Only the first two can make a line noise (a score below the default threshold of 0.35) on their
own: a line of only punctuation or symbols scores 0, and so does ``lllllllll``. Each of the
others has a weight of at most 0.6, so it needs another penalty's evidence; this is what keeps
short lines that are real text:

- A line of one-character tokens is often real: a formula (``V = I R``, ``x = y + z``), an
  abbreviation (``R & D``), a table row (``| a | b |``), column labels (``A B C D``). So only
  lowercase letters and punctuation that is not an operator count as single characters
  (``single_char_tokens``), and their penalty alone leaves a score of 0.4.
- Specks and dust are small and narrow, so OCR reads them as the narrowest glyphs: ``. , : ;``,
  apostrophes, ``! |``, ``i l I 1``. A line of many tokens made almost only of these is the
  second sign. ``i i i ! l ; :`` has both and scores 0.1; ``x y z`` has only the first and
  scores 0.4; the ratio ``1 : 1`` has only the second and scores 0.7.
- A letter repeated is noise when it is a thin one (``i``, ``l``: specks read as ``lllllllll``
  or ``IIIIIIII``) in a run of 4 or more (``longest_thin_run``), or any letter in a run of 10
  or more (``longest_run``). Shorter runs of other letters are interjections (``Mmmm``,
  ``Zzzz``, ``Ahhhh``), not noise.
- Lists of acronyms (``BBC NBC CNN``) have no vowels and names such as ``LaTeX`` switch case.

``digit_ratio`` and ``mean_token_length`` are measured for callers but not used by the score.

The vowel penalty assumes Latin script (the vowels are ``a e i o u y`` with any diacritic, and
``æ œ ø``); text in another script loses at most its 0.3.
"""

import unicodedata
from dataclasses import dataclass
from functools import cache
from typing import Final

_LATIN_VOWELS: Final = frozenset("aeiouyæœø")

#: One-character tokens that are content in formulas, abbreviations and table rows.
OPERATORS: Final = frozenset(
    "=<>+-*/&|"
    "\N{NOT EQUAL TO}\N{LESS-THAN OR EQUAL TO}\N{GREATER-THAN OR EQUAL TO}"
    "\N{MINUS SIGN}\N{PLUS-MINUS SIGN}\N{MULTIPLICATION SIGN}\N{DIVISION SIGN}"
)

#: The narrow glyphs OCR reads specks and dust as.
THIN_GLYPHS: Final = frozenset(
    ".,:;'`!|iIl1\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}\N{BROKEN BAR}"
)

# The conditions of the score's penalties (see the table above).
_MIN_TOKENS: Final = 3
_THIN_RUN_MIN_LENGTH: Final = 4
_RUN_MIN_LENGTH: Final = 10
_THIN_LETTERS: Final = frozenset("il")
_VOWEL_MIN_LETTERS: Final = 6


@dataclass(frozen=True, slots=True)
class Features:
    """What ``features`` measured in a text. Counts are of visible characters and tokens, with
    each leader counted as one symbol and one token.

    - ``letters``, ``digits`` (any Unicode number character) and ``symbols`` (punctuation and
      symbols) add up to ``length``.
    - ``vowels``: letters that are Latin vowels, with or without diacritics.
    - ``single_char_tokens``: tokens of one character that is a lowercase letter, or punctuation
      or a symbol other than one of ``OPERATORS``. Digits (list numbers, table cells, page
      numbers), capitals (``V = I R``, ``A B C D``) and operators are content when they stand
      alone; lone lowercase letters and marks rarely are.
    - ``thin_glyphs``: characters in ``THIN_GLYPHS``.
    - ``longest_run``: the longest run of one letter repeated inside a token, ignoring case.
      Runs of digits (``1000000``) and of symbols (leaders) are not counted.
    - ``longest_thin_run``: the same for the thin letters ``i`` and ``l`` only.
    - ``case_switches``: places inside a token where a lowercase letter is followed directly by
      an uppercase one.
    """

    length: int
    letters: int
    digits: int
    symbols: int
    tokens: int
    vowels: int
    single_char_tokens: int
    thin_glyphs: int
    longest_run: int
    longest_thin_run: int
    case_switches: int

    @property
    def letter_ratio(self) -> float:
        return self.letters / self.length if self.length else 0.0

    @property
    def digit_ratio(self) -> float:
        return self.digits / self.length if self.length else 0.0

    @property
    def symbol_ratio(self) -> float:
        return self.symbols / self.length if self.length else 0.0

    @property
    def vowel_ratio(self) -> float:
        """Vowels among letters; 0 when there are no letters."""
        return self.vowels / self.letters if self.letters else 0.0

    @property
    def mean_token_length(self) -> float:
        return self.length / self.tokens if self.tokens else 0.0

    @property
    def single_char_ratio(self) -> float:
        """The share of tokens in ``single_char_tokens``."""
        return self.single_char_tokens / self.tokens if self.tokens else 0.0

    @property
    def thin_glyph_ratio(self) -> float:
        return self.thin_glyphs / self.length if self.length else 0.0


@cache
def _kind(char: str) -> str:
    # "L" letter, "N" number, "S" punctuation or symbol, "" not visible.
    category = unicodedata.category(char)[0]
    if category in "LN":
        return category
    return "S" if category in "PS" else ""


@cache
def _is_vowel(letter: str) -> bool:
    lower = letter.lower()
    return lower in _LATIN_VOWELS or unicodedata.normalize("NFD", lower)[0] in _LATIN_VOWELS


def _tokens(text: str) -> list[str]:
    """The visible characters of each token, with leaders collapsed to one character."""
    tokens: list[str] = []
    for piece in text.split():
        token: list[str] = []
        for char in piece:
            kind = _kind(char)
            if not kind or (kind == "S" and token and token[-1] == char):
                continue
            token.append(char)
        if not token:
            continue
        if len(token) == 1 and _kind(token[0]) == "S" and tokens and tokens[-1] == token[0]:
            continue
        tokens.append("".join(token))
    return tokens


def _is_single_char(token: str) -> bool:
    if len(token) != 1:
        return False
    kind = _kind(token)
    return token.islower() if kind == "L" else kind == "S" and token not in OPERATORS


def features(text: str) -> Features:
    """Measure ``text``: character classes, tokens, repeated letters, vowels and case switches."""
    letters = digits = symbols = vowels = single = thin = longest = longest_thin = switches = 0
    tokens = _tokens(text)
    for token in tokens:
        single += _is_single_char(token)
        run = thin_run = 0
        previous = ""
        for char in token:
            thin += char in THIN_GLYPHS
            kind = _kind(char)
            if kind == "L":
                letters += 1
                vowels += _is_vowel(char)
                run = run + 1 if previous.lower() == char.lower() else 1
                longest = max(longest, run)
                if char.lower() in _THIN_LETTERS:
                    thin_run = thin_run + 1 if previous.lower() == char.lower() else 1
                    longest_thin = max(longest_thin, thin_run)
                else:
                    thin_run = 0
                switches += previous.islower() and char.isupper()
            elif kind == "N":
                digits += 1
            else:
                symbols += 1
            previous = char
    return Features(
        length=letters + digits + symbols,
        letters=letters,
        digits=digits,
        symbols=symbols,
        tokens=len(tokens),
        vowels=vowels,
        single_char_tokens=single,
        thin_glyphs=thin,
        longest_run=longest,
        longest_thin_run=longest_thin,
        case_switches=switches,
    )


def _ramp(value: float, start: float, end: float) -> float:
    """0 at ``start``, 1 at ``end``, linear between and flat beyond; ``end`` may be below."""
    share = (value - start) / (end - start)
    return min(max(share, 0.0), 1.0)


def score(text: str) -> float:
    """How much ``text`` looks like language, from 0 (noise) to 1; the module explains the formula.

    Text with no visible character scores 1: there is nothing in it that is noise (blank lines
    are the whitespace rules' business).
    """
    measured = features(text)
    if not measured.length:
        return 1.0
    penalty = 1.0 * _ramp(measured.symbol_ratio, 0.6, 0.85)
    run = 0
    if measured.longest_run >= _RUN_MIN_LENGTH:
        run = measured.longest_run
    elif measured.longest_thin_run >= _THIN_RUN_MIN_LENGTH:
        run = measured.longest_thin_run
    if run:
        penalty += 0.7 * _ramp(run / measured.length, 0.3, 0.9)
    if measured.tokens >= _MIN_TOKENS:
        penalty += 0.6 * _ramp(measured.single_char_ratio, 0.5, 1.0)
        penalty += 0.3 * _ramp(measured.thin_glyph_ratio, 0.75, 1.0)
    if measured.letters >= _VOWEL_MIN_LETTERS:
        penalty += 0.3 * _ramp(measured.vowel_ratio, 0.15, 0.0)
    if measured.letters:
        penalty += 0.4 * _ramp(measured.case_switches / measured.letters, 0.15, 0.4)
    return max(0.0, 1.0 - penalty)


def is_noise(text: str, *, threshold: float = 0.35) -> bool:
    """Whether ``text`` scores below ``threshold``.

    With the default threshold a line of only punctuation or symbols is noise, and a blank line
    is not. Raises ``ValueError`` if ``threshold`` is not in ``[0, 1]``.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"a threshold is between 0 and 1, not {threshold!r}")
    return score(text) < threshold
