"""Confusables: letters OCR read inside numbers, and digits it read inside words.

Some letters and digits look alike in print: ``O`` and ``0``, ``l``, ``I`` and ``1``, ``S`` and
``5``, ``B`` and ``8``. OCR swaps them, and the context usually shows which was meant: a letter in
the middle of a number is a digit, a digit in the middle of a word is a letter. These rules make
that repair only where the context is unambiguous, and leave codes and identifiers that mix
letters and digits on purpose (``B12``, ``12B34``, ``A4``, ``mp3``, ``x86``) alone.
"""

import itertools
import re
from typing import Final

from lectris.edits import Revision, substitute
from lectris.lexicon import Lexicon

IN_NUMBERS: Final = "confusables.in_numbers"
IN_WORDS: Final = "confusables.in_words"

_LETTER_TO_DIGIT: Final = str.maketrans("OolI", "0011")
# Digits and look-alike letters, with single "." or "," between them, not attached to another
# letter, digit or underscore.
_NUMBER: Final = re.compile(r"(?<!\w)[0-9OolI](?:[.,]?[0-9OolI])*(?!\w)")
_DIGITS: Final = re.compile(r"[0-9]")
_LEADING_ZERO: Final = re.compile(r"O[.,][0-9]")
# The real digits a number needs before its letters are read as digits.
_MIN_DIGITS: Final = 2
# The letters a word needs before its digits are read as letters, and the most digits it holds.
_MIN_LETTERS: Final = 3
_MAX_DIGITS: Final = 4

# The letters each digit may stand for in lower case, and in capitals.
_DIGIT_TO_LOWER: Final = {"0": ("o",), "1": ("l", "i"), "5": ("s",)}
_DIGIT_TO_UPPER: Final = {"0": "O", "1": "I", "5": "S", "8": "B"}
# A word: letters and digits, with apostrophes inside (don't), not attached to an underscore.
_WORD: Final = re.compile(r"(?<!\w)[^\W_]+(?:['\N{RIGHT SINGLE QUOTATION MARK}][^\W_]+)*(?!\w)")


def _leading_zero(token: str) -> bool:
    """Whether ``token`` starts with an ``O`` read for the zero before a decimal separator, as in
    ``O.5`` or ``O,75``: an ``O`` followed by ``.`` or ``,`` and a real digit."""
    return _LEADING_ZERO.match(token) is not None


def _number(match: re.Match[str]) -> str | None:
    token = match.group(0)
    number = token.translate(_LETTER_TO_DIGIT)
    leading_zero = _leading_zero(token)
    if number == token or not (token[0].isdigit() or leading_zero):
        return None
    if not (token[-1].isdigit() or token[-1] == "O"):
        return None
    if len(_DIGITS.findall(token)) < (1 if leading_zero else _MIN_DIGITS):
        return None
    return number


def in_numbers(text: str, /) -> Revision:
    """Turn the letters inside a number that look like digits into those digits.

    ``O`` and ``o`` become ``0``, ``l`` and ``I`` become ``1``: ``"1O5"`` becomes ``"105"``,
    ``"2,5OO"`` becomes ``"2,500"``. A token is changed, all of its letters at once, only when it
    is clearly a number:

    - it is a run of digits, those letters, and ``.`` or ``,`` between them, not attached to any
      other letter, digit or underscore (a sign, currency symbol or ``%`` around it is fine);
    - it starts with a real digit, so a code such as ``I95`` or ``l23`` is left alone; or it
      starts with an ``O`` read for the zero before a decimal separator, an ``O`` followed by
      ``.`` or ``,`` and a real digit: ``"O.5"`` becomes ``"0.5"``, ``"O,75"`` becomes
      ``"0,75"``, while ``O5``, ``O.K.``, ``Oslo`` and ``O'Brien`` are left alone;
    - it ends with a real digit or with ``O``, so ``50l`` (litres) and ``10o`` (a degree sign
      read as ``o``) are left alone;
    - it has at least two real digits, or one after a leading ``O.``.

    ``S`` and ``B`` are left alone even between digits, although OCR also reads ``5`` and ``8``
    as them: part numbers, serials and postcodes use them (``12B34``, ``10S20``, ``0B1``).
    Tokens with any other letter (``A4``, ``COVID-19``'s ``COVID``, ``0x1F``) never match, and
    neither does ``|``, which is also a table rule (``12|34``). The rule is idempotent.

    >>> in_numbers("a total of 2,5OO in 2O24").text
    'a total of 2,500 in 2024'
    """
    return substitute(text, _NUMBER, _number, IN_NUMBERS)


def _options(token: str, position: int, upper: bool) -> tuple[str, ...]:
    """The letters the digit at ``position`` in ``token`` may stand for, given the case."""
    digit = token[position]
    capital = _DIGIT_TO_UPPER.get(digit)
    if upper:
        return (capital,) if capital else ()
    lower = _DIGIT_TO_LOWER.get(digit, ())
    if position == 0 and capital:
        return (*lower, capital)
    return lower


def _o_between_letters(token: str, position: int) -> bool:
    """Whether ``token[position]`` is a ``0`` between two letters, one of them lowercase."""
    if token[position] != "0" or not 0 < position < len(token) - 1:
        return False
    left, right = token[position - 1], token[position + 1]
    return left.isalpha() and right.isalpha() and (left.islower() or right.islower())


def _word(match: re.Match[str], lexicon: Lexicon | None) -> str | None:
    token = match.group(0)
    digits = [position for position, char in enumerate(token) if char.isdigit()]
    letters = [char for char in token if char.isalpha()]
    if (
        not digits
        or len(digits) > _MAX_DIGITS
        or len(letters) < _MIN_LETTERS
        or any(token[p] not in _DIGIT_TO_UPPER for p in digits)
    ):
        return None
    if lexicon is None:
        if all(_o_between_letters(token, p) for p in digits):
            return token.replace("0", "o")
        return None
    if token in lexicon:
        return None
    upper = all(char.isupper() for char in letters)
    choices = [_options(token, p, upper) for p in digits]
    # Readings by lexicon entry: in a case-insensitive lexicon two readings that differ only in
    # case are one entry, and the first (lowercase) reading stands for it.
    readings: dict[str, tuple[str, int]] = {}
    for chosen in itertools.product(*choices):
        candidate = list(token)
        for position, letter in zip(digits, chosen, strict=True):
            candidate[position] = letter
        word = "".join(candidate)
        entry = word if lexicon.case_sensitive else word.lower()
        if word in lexicon and entry not in readings:
            readings[entry] = (word, lexicon.frequency(word))
    ranked = sorted(readings.values(), key=lambda reading: -reading[1])
    if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
        return None
    return ranked[0][0]


def in_words(text: str, /, *, lexicon: Lexicon | None = None) -> Revision:
    """Turn the digits inside a word that look like letters into those letters.

    ``0`` becomes ``o``, ``1`` becomes ``l`` or ``i``, ``5`` becomes ``s``; in a word in capitals
    they become ``O``, ``I`` and ``S``, and ``8`` becomes ``B``. ``"w0rd"`` becomes ``"word"``,
    ``"s1mple"`` ``"simple"`` and ``"B0STON"`` ``"BOSTON"``. A digit at the start of a word in
    lower case may stand for either case, and the lexicon decides: ``"1ike"`` is ``"like"``,
    ``"8oston"`` is ``"Boston"``. When readings differ only in case and the lexicon ignores
    case, the lowercase one is taken (``"0xford"`` becomes ``"oxford"``, ``"1ndia"``
    ``"india"``); a case-sensitive lexicon can choose the capital.

    A token is a run of letters and digits (apostrophes inside allowed), not attached to an
    underscore. It is changed, all its digits at once, only if it has at least three letters, at
    most four digits, and every digit in it is one of ``0``, ``1``, ``5``, ``8`` that can become
    a letter there, and:

    - with a ``lexicon``: the token is not in it and a reading is. When several readings are,
      the one with the highest count wins; on a tie the token is left alone;
    - without a lexicon: every digit is ``0`` with a letter on each side, at least one of them
      lowercase, and it becomes ``o`` (``"c0mputer"``, ``"McD0nald"``). A ``1`` may be ``l`` or
      ``i`` (``"s1mple"``) and a ``0`` between capitals may belong to a code (``"KX0QZ"``), so
      those need a lexicon, as do the other digits.

    Left alone: tokens with other digits (``mp3``, ``h264``, ``x86``, ``4th``, ``B2B``), fewer
    than three letters (``1st``, ``2D``, ``10th``), identifiers with underscores, and anything
    a lexicon does not confirm. Without a lexicon, a name that puts ``0`` between letters on
    purpose is changed; use a lexicon on such text. The rule is idempotent.

    >>> in_words("the c0mputer is 0n").text
    'the computer is 0n'
    """
    return substitute(text, _WORD, lambda match: _word(match, lexicon), IN_WORDS)


RULES: Final = (in_numbers, in_words)
