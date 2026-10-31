"""Read Tesseract's TSV output.

The first line is the header Tesseract writes::

    level page_num block_num par_num line_num word_num left top width height conf text

(tab-separated), and every other line is a row for one element. ``level`` says which: 1 a page,
2 a block, 3 a paragraph, 4 a line, 5 a word. ``left``, ``top``, ``width`` and ``height`` are
its box.

Words are grouped by ``(page_num, block_num, par_num, line_num)``, and Tesseract's paragraphs
are LECTRIS's blocks. Pages, blocks and lines keep the order in which they first appear. A
``conf`` from 0 to 100 becomes a confidence over 100, and -1 means none: Tesseract writes -1 on
the rows that are structure, not words, so its lines have no confidence. Rows of levels 1, 3
and 4 give the boxes of pages, blocks and lines, and are optional: without them a line or block
takes the union of its words' boxes, and a page has no size. Blank lines are skipped, and a row
whose ``text`` field is missing is read as a row with empty text.
"""

import re
from dataclasses import dataclass, field

from lectris.errors import FormatError
from lectris.io._common import (
    make_block,
    make_box,
    make_line,
    make_word,
    parse_integer,
    parse_number,
    parse_percentage,
    strip_bom,
)
from lectris.model import Block, Box, Document, Page, Word

HEADER = (
    "level",
    "page_num",
    "block_num",
    "par_num",
    "line_num",
    "word_num",
    "left",
    "top",
    "width",
    "height",
    "conf",
    "text",
)
"""The column names of Tesseract's TSV, in order."""

_PAGE, _BLOCK, _PARAGRAPH, _LINE, _WORD = 1, 2, 3, 4, 5
_NO_CONFIDENCE = -1.0
_LINE_BREAK = re.compile(r"\r\n?|\n")


@dataclass(slots=True)
class _LineParts:
    box: Box | None = None
    confidence: float | None = None
    words: list[Word] = field(default_factory=list)


@dataclass(slots=True)
class _BlockParts:
    box: Box | None = None
    lines: dict[int, _LineParts] = field(default_factory=dict)


@dataclass(slots=True)
class _PageParts:
    width: float | None = None
    height: float | None = None
    blocks: dict[tuple[int, int], _BlockParts] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Row:
    level: int
    page: int
    block: int
    paragraph: int
    line: int
    box: Box
    confidence: float | None
    text: str


def parse(content: str) -> Document:
    """Read Tesseract's TSV output.

    Raises ``FormatError`` if the first line is not Tesseract's header, or a row does not have
    the header's columns, a number where the header expects one, a ``level`` from 1 to 5, or a
    ``conf`` that is -1 or from 0 to 100.
    """
    rows = _LINE_BREAK.split(strip_bom(content))
    if tuple(rows[0].rstrip().split("\t")) != HEADER:
        raise FormatError(
            f"the first line is not Tesseract's TSV header ({' '.join(HEADER)}): {rows[0][:80]!r}"
        )
    pages: dict[int, _PageParts] = {}
    for number, text in enumerate(rows[1:], start=2):
        if text.strip():
            _add(pages, _row(text, number))
    return Document(tuple(_page(number, parts) for number, parts in pages.items()))


def _row(text: str, number: int) -> _Row:
    fields = text.split("\t")
    if len(fields) == len(HEADER) - 1:
        fields.append("")
    if len(fields) != len(HEADER):
        raise FormatError(f"line {number} has {len(fields)} fields, not {len(HEADER)}")
    values = dict(zip(HEADER, fields, strict=True))

    def whole(name: str) -> int:
        return parse_integer(values[name].strip(), f"line {number}: {name}")

    def decimal(name: str) -> float:
        return parse_number(values[name].strip(), f"line {number}: {name}")

    level = whole("level")
    if not _PAGE <= level <= _WORD:
        raise FormatError(f"line {number}: level is {level}; it must be from 1 to 5")
    whole("word_num")  # checked like every column, though words keep the order of their rows
    left, top = decimal("left"), decimal("top")
    box = make_box(left, top, left + decimal("width"), top + decimal("height"), f"line {number}")
    conf, what = values["conf"].strip(), f"line {number}: conf"
    confidence = (
        None if parse_number(conf, what) == _NO_CONFIDENCE else parse_percentage(conf, what)
    )
    return _Row(
        level,
        whole("page_num"),
        whole("block_num"),
        whole("par_num"),
        whole("line_num"),
        box,
        confidence,
        values["text"],
    )


def _add(pages: dict[int, _PageParts], row: _Row) -> None:
    """Add the row to the structure it belongs to, creating what does not exist yet."""
    page = pages.setdefault(row.page, _PageParts())
    if row.level == _PAGE:
        page.width, page.height = row.box.width, row.box.height
        return
    if row.level == _BLOCK:
        return
    block = page.blocks.setdefault((row.block, row.paragraph), _BlockParts())
    if row.level == _PARAGRAPH:
        block.box = row.box
        return
    line = block.lines.setdefault(row.line, _LineParts())
    if row.level == _LINE:
        line.box, line.confidence = row.box, row.confidence
        return
    word = make_word(row.text, row.box, row.confidence)
    if word is not None:
        line.words.append(word)


def _page(number: int, parts: _PageParts) -> Page:
    blocks = (_block(block) for block in parts.blocks.values())
    return Page(
        tuple(block for block in blocks if block is not None),
        width=parts.width,
        height=parts.height,
        number=number,
    )


def _block(parts: _BlockParts) -> Block | None:
    lines = (make_line(line.words, line.box, line.confidence) for line in parts.lines.values())
    return make_block((line for line in lines if line is not None), parts.box)
