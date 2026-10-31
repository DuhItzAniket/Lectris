"""Synthetic pages for the layout tests: lines of words at given positions.

Every character is ``char_width`` wide and every word ``height`` tall, with one character's width
between words, unless a line is stretched to a given width as justified text is.
"""

import math
from collections.abc import Iterable, Sequence

from lectris.model import Block, Box, Line, Word, union_of

HEIGHT = 20.0
CHAR = 10.0
PITCH = 30.0


def make_line(
    text: str,
    x: float,
    y: float,
    *,
    height: float = HEIGHT,
    char_width: float = CHAR,
    width: float | None = None,
) -> Line:
    """A line of ``text`` whose first word starts at ``x`` and whose top is ``y``.

    With ``width``, the spaces between words are widened evenly so that the line is that wide.
    """
    parts = text.split()
    natural = (len(" ".join(parts))) * char_width
    space = char_width
    if width is not None and len(parts) > 1:
        space += (width - natural) / (len(parts) - 1)
    words: list[Word] = []
    cursor = x
    for part in parts:
        end = cursor + len(part) * char_width
        words.append(Word(part, Box(cursor, y, end, y + height)))
        cursor = end + space
    return Line(tuple(words), box=union_of(word.box for word in words))


def make_paragraph(
    rows: Sequence[str],
    *,
    x: float = 50,
    y: float = 100,
    indent: float = 0,
    width: float = 400,
    pitch: float = 30,
    height: float = HEIGHT,
    char_width: float = CHAR,
) -> list[Line]:
    """A justified paragraph: every line but the last is ``width`` wide; the first is indented."""
    lines = []
    for i, text in enumerate(rows):
        shift = indent if i == 0 else 0
        last = i == len(rows) - 1
        lines.append(
            make_line(
                text,
                x + shift,
                y + i * pitch,
                height=height,
                char_width=char_width,
                width=None if last else width - shift,
            )
        )
    return lines


def make_column(
    texts: Sequence[str],
    x: float,
    y: float,
    *,
    pitch: float = PITCH,
    width: float | None = None,
) -> list[Line]:
    """One line per text, starting at ``x``, the first at ``y`` and the next ``pitch`` lower."""
    return [make_line(text, x, y + i * pitch, width=width) for i, text in enumerate(texts)]


def scale_box(box: Box | None, factor: float) -> Box | None:
    if box is None:
        return None
    return Box(box.x0 * factor, box.y0 * factor, box.x1 * factor, box.y1 * factor)


def scale_word(word: Word, factor: float) -> Word:
    return Word(word.text, scale_box(word.box, factor), word.confidence)


def scale_line(line: Line, factor: float) -> Line:
    words = tuple(scale_word(word, factor) for word in line.words)
    return Line(words, scale_box(line.box, factor), line.confidence)


def texts(lines: Iterable[Line]) -> list[str]:
    return [line.text for line in lines]


def firsts(lines: Iterable[Line]) -> list[str]:
    """Each line's first word: the label the tests give their lines."""
    return [line.words[0].text for line in lines]


def block_texts(blocks: Iterable[Block]) -> list[list[str]]:
    return [texts(block.lines) for block in blocks]


def words_of(lines: Iterable[Line]) -> list[Word]:
    return [word for line in lines for word in line.words]


def scrambled[T](items: Sequence[T]) -> list[T]:
    """The items out of order, the same way every time: odd positions backwards, then even ones."""
    return [*items[1::2][::-1], *items[::2]]


def skew_box(box: Box, degrees: float, centre: tuple[float, float]) -> Box:
    """The bounds of the box turned by ``degrees`` about ``centre``, as a skewed scan shows it.

    A positive angle makes lines descend to the right.
    """
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    cx, cy = centre
    xs, ys = [], []
    for x, y in ((box.x0, box.y0), (box.x1, box.y0), (box.x0, box.y1), (box.x1, box.y1)):
        xs.append(cx + (x - cx) * cos - (y - cy) * sin)
        ys.append(cy + (x - cx) * sin + (y - cy) * cos)
    return Box(min(xs), min(ys), max(xs), max(ys))


def skew_line(line: Line, degrees: float, centre: tuple[float, float] = (0, 0)) -> Line:
    """The line as a skewed scan's OCR gives it: each word's box turned, the line's their union."""
    words = tuple(
        Word(word.text, None if word.box is None else skew_box(word.box, degrees, centre))
        for word in line.words
    )
    return Line(words, box=union_of(word.box for word in words), confidence=line.confidence)


def scan_column(
    label: str, x: float, y: float, rows: int, *, width: float, words: int
) -> list[Line]:
    """Justified lines as a 300 dpi scan of a book gives them: type 35 high, lines 45 apart.

    Each line is its label and a two-digit number (``label00``), then ``words`` four-letter words.
    """
    texts = [f"{label}{i:02d} " + " ".join(["word"] * words) for i in range(rows)]
    return [
        make_line(text, x, y + 45 * i, height=35, char_width=18, width=width)
        for i, text in enumerate(texts)
    ]
