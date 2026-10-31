"""Layout: words to lines, columns, reading order and paragraphs.

Layout steps work on boxes. ``arrange`` splits lines whose words lie on several visual lines
(``lines``), puts a page's lines in reading order (``order``) and groups them into paragraphs
(``paragraphs``); ``columns`` finds a page's column ranges, and ``geometry`` holds the
measurements they share. Every function returns new values; nothing is changed in place.
"""

import math

from lectris.layout.geometry import deskew as turn_back
from lectris.layout.geometry import skew
from lectris.layout.lines import group_words
from lectris.layout.order import reading_order_indices
from lectris.layout.paragraphs import group
from lectris.model import Box, Document, Line, Page, Word, union_of

__all__ = ["arrange", "arrange_document"]


def arrange(
    page: Page,
    *,
    min_gap: float = 1.0,
    max_spanning: float = 0.25,
    trim: float = 0.25,
    spacing: float = 1.5,
    min_overlap: float = 0.5,
    indent: float = 0.5,
    deskew: bool = True,
) -> Page:
    """The page with its lines in reading order and grouped into paragraphs.

    1. *Visual lines.* A line whose words all have boxes is checked with
       ``lines.group_words(words, max_gap=math.inf)``, on copies of its words' boxes turned back
       by the page's skew (with ``deskew``; see ``geometry.skew``): when its words lie on more
       than one visual line, it is replaced by those lines, from top to bottom, each with its
       words (the input's own) from left to right and no confidence of its own (the words keep
       theirs). Only the words' heights separate them, so a wide gap inside a line does not split
       it, and turning the boxes back keeps a skewed line whole however few words it has. A line
       that lies on one visual line is kept as it is; if it has no box, it is given the union of
       its words'.
    2. *Order.* The lines are put in reading order by ``order.reading_order`` (``min_gap``,
       ``max_spanning``, ``trim``, ``deskew``).
    3. *Paragraphs.* They are grouped by ``paragraphs.group`` (``spacing``, ``min_overlap``,
       ``indent``, ``deskew``), with each line's source being the block the page put it in: the
       blocks the input gave can be split into paragraphs, and their lines reordered, but lines
       from two of them never end up in one block.

    The options are documented where they are used. The new page keeps the page's width, height
    and number. A page with no lines, or with a line that has no box (and no word boxes to give
    it one), is returned as it is: without boxes, the blocks the input gave are the only evidence
    of its structure.
    """
    angle = skew(page.lines) if deskew else 0.0
    lines: list[Line] = []
    sources: list[int] = []
    for number, block in enumerate(page.blocks):
        for line in block.lines:
            parts = _visual_lines(line, angle)
            lines += parts
            sources += [number] * len(parts)
    if not lines or any(line.box is None for line in lines):
        return page
    positions = reading_order_indices(
        lines, min_gap=min_gap, max_spanning=max_spanning, trim=trim, deskew=deskew
    )
    blocks = group(
        [lines[i] for i in positions],
        spacing=spacing,
        min_overlap=min_overlap,
        indent=indent,
        sources=[sources[i] for i in positions],
        deskew=deskew,
    )
    return Page(blocks, width=page.width, height=page.height, number=page.number)


def arrange_document(
    document: Document,
    *,
    min_gap: float = 1.0,
    max_spanning: float = 0.25,
    trim: float = 0.25,
    spacing: float = 1.5,
    min_overlap: float = 0.5,
    indent: float = 0.5,
    deskew: bool = True,
) -> Document:
    """The document with each page arranged by ``arrange``, with the same options."""
    return Document(
        tuple(
            arrange(
                page,
                min_gap=min_gap,
                max_spanning=max_spanning,
                trim=trim,
                spacing=spacing,
                min_overlap=min_overlap,
                indent=indent,
                deskew=deskew,
            )
            for page in document.pages
        )
    )


def _visual_lines(line: Line, angle: float) -> list[Line]:
    """The line, or the visual lines its words lie on (with the page turned back by ``angle``)
    when they lie on more than one."""
    boxes: list[Box] = [word.box for word in line.words if word.box is not None]
    if not boxes or len(boxes) != len(line.words):
        return [line]
    copies = [
        Word(word.text, turn_back(box, angle)) for word, box in zip(line.words, boxes, strict=True)
    ]
    originals = {id(copy): word for copy, word in zip(copies, line.words, strict=True)}
    parts = group_words(copies, max_gap=math.inf)
    if len(parts) > 1:
        result: list[Line] = []
        for part in parts:
            words = tuple(originals[id(copy)] for copy in part.words)
            result.append(Line(words, box=union_of(word.box for word in words)))
        return result
    if line.box is None:
        return [Line(line.words, box=union_of(boxes), confidence=line.confidence)]
    return [line]
