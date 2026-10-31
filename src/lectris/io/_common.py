"""What the readers share: decoding, numbers, boxes, confidences, and building the model.

Every reader builds words, lines and blocks the same way:

- a word's text is stripped, and a run of whitespace inside it that holds a tab or a line break
  becomes one space, so a word never spans lines; a word left empty is dropped;
- a line without words, and a block without lines, are dropped;
- a line's or a block's box is the one the format gives, or else the union of its parts' boxes.
"""

import codecs
import math
import re
from collections.abc import Iterable
from decimal import Decimal

from lectris.errors import FormatError
from lectris.model import Block, Box, Line, Word, union_of

# UTF-32 LE comes before UTF-16 LE: its byte order mark starts with UTF-16 LE's.
_BYTE_ORDER_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_INTEGER = re.compile(r"[+-]?[0-9]+")
_PERCENT = 100
_BREAK = re.compile(r"\s*[\t\n\v\f\r\x1c-\x1e\x85\u2028\u2029]\s*")


def decode(data: bytes, *, errors: str = "strict") -> str:
    """``data`` as text: UTF-8, or UTF-16 or UTF-32 when a byte order mark says so.

    The byte order mark is dropped. Bytes that are not valid in the encoding raise
    ``FormatError`` (with ``errors="strict"``, the default).
    """
    encoding, start = "utf-8", 0
    for mark, name in _BYTE_ORDER_MARKS:
        if data.startswith(mark):
            encoding, start = name, len(mark)
            break
    try:
        return data[start:].decode(encoding, errors)
    except UnicodeDecodeError as error:
        position = start + error.start
        raise FormatError(
            f"the input is not valid {encoding.upper()}: {error.reason} at byte {position}"
        ) from None


def strip_bom(text: str) -> str:
    """``text`` without a leading byte order mark."""
    return text.removeprefix("\ufeff")


def parse_number(text: str, what: str) -> float:
    """``text`` read as a finite decimal number; ``what`` names it in the error."""
    if _NUMBER.fullmatch(text) is None:
        raise FormatError(f"{what} is not a number: {text!r}")
    value = float(text)
    if not math.isfinite(value):
        raise FormatError(f"{what} is out of range: {text!r}")
    return value


def parse_integer(text: str, what: str) -> int:
    """``text`` read as a whole number; ``what`` names it in the error."""
    if _INTEGER.fullmatch(text) is None:
        raise FormatError(f"{what} is not a whole number: {text!r}")
    try:
        return int(text)
    except ValueError:  # more digits than int() accepts
        raise FormatError(f"{what} is out of range: {text[:20]!r}...") from None


def make_box(x0: float, y0: float, x1: float, y1: float, what: str) -> Box:
    """``Box(x0, y0, x1, y1)``, or ``FormatError`` naming ``what`` if it is not a valid box."""
    try:
        return Box(float(x0), float(y0), float(x1), float(y1))
    except (ValueError, OverflowError) as error:
        raise FormatError(f"{what}: {error}") from None


def parse_confidence(text: str, what: str) -> float:
    """``text``, a number from 0 to 1, as a confidence."""
    value = parse_number(text, what)
    if not 0 <= value <= 1:
        raise FormatError(f"{what} is {text!r}; it must be from 0 to 1")
    return value


def parse_percentage(text: str, what: str) -> float:
    """``text``, a number from 0 to 100, as a confidence from 0 to 1.

    The division by 100 is decimal, so ``"71.9"`` gives ``0.719``, not ``0.7190000000000001``.
    """
    value = parse_number(text, what)
    if not 0 <= value <= _PERCENT:
        raise FormatError(f"{what} is {text!r}; it must be from 0 to 100")
    return float(Decimal(text).scaleb(-2))


def word_text(raw: str) -> str:
    """``raw`` stripped, with each whitespace run that holds a tab or line break made one space."""
    return _BREAK.sub(" ", raw.strip())


def make_word(raw: str, box: Box | None = None, confidence: float | None = None) -> Word | None:
    """The word with text ``raw`` (see ``word_text``), or ``None`` if that text is empty."""
    text = word_text(raw)
    return Word(text, box, confidence) if text else None


def make_line(
    words: Iterable[Word], box: Box | None = None, confidence: float | None = None
) -> Line | None:
    """A line of ``words``, boxed by ``box`` or else by its words; ``None`` if it has no words."""
    kept = tuple(words)
    if not kept:
        return None
    return Line(kept, box if box is not None else union_of(word.box for word in kept), confidence)


def make_block(lines: Iterable[Line], box: Box | None = None) -> Block | None:
    """A block of ``lines``, boxed by ``box`` or else by its lines; ``None`` if it has no lines."""
    kept = tuple(lines)
    if not kept:
        return None
    return Block(kept, box if box is not None else union_of(line.box for line in kept))
