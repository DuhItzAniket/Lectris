"""Paragraphs: consecutive lines in reading order grouped into blocks."""

import math
import re
from collections.abc import Sequence
from itertools import pairwise

from lectris.layout.columns import assign, detect
from lectris.layout.geometry import deskew as turn_back
from lectris.layout.geometry import horizontal_overlap, median, median_height, skew
from lectris.model import Block, Box, Line, union_of

_SENTENCE_END = frozenset(".!?:…")
# Quotes and brackets: straight, curly and guillemets. Curly quotes and the hyphen bullet are
# written as escapes: they are easy to mistake for other characters.
_CLOSING = "\"')]\u201d\u2019»"
_OPENING = "\"'([\u201c\u2018\u201e«¿¡"
_BULLETS = frozenset("•◦▪▫‣\u2043●○■□►▸")
_ENUMERATOR = re.compile(r"\(?(?:\d{1,3}|[a-zA-Z]|[ivxlc]{1,6}|[IVXLC]{1,6})[.)]")


def group(
    lines: Sequence[Line],
    *,
    spacing: float = 1.5,
    min_overlap: float = 0.5,
    indent: float = 0.5,
    sources: Sequence[int] | None = None,
    deskew: bool = True,
) -> tuple[Block, ...]:
    """Group lines that are in reading order into blocks, one per paragraph.

    Consecutive lines stay in one block until one of these starts a new block at a line:

    0. *Source.* With ``sources``, one number per line (such as the index of the block the input
       put it in), a line whose number differs from the previous line's: lines the input kept
       apart are never merged.
    1. *Column change.* The line's ``x`` range overlaps the previous line's by less than
       ``min_overlap`` of the narrower one, or its middle is not below the previous line's middle.
    2. *Vertical gap.* The distance from the previous line exceeds ``spacing`` times the line
       spacing. The distance between two lines is the larger of the distances between their
       tops and between their bottoms, so a heading in larger type is set apart both from the
       line before it and from the line after it. The line spacing is the median of the smaller
       half of the distances between consecutive lines in one column, over all the lines given
       (the smallest distance when there are fewer than four): paragraph breaks, headings and a
       footer far below the text give the larger distances, and do not raise the estimate even
       on a short page where they are most of the distances.
    3. *Indent.* The line starts more than ``indent`` median line heights to the right of the
       previous line and of the block's leftmost line, and either the block already has two
       lines or the previous line is short (below). This starts both an indented first line and
       a block quote. The condition on the block keeps the second line of a hanging indent (a
       list item whose wrapped lines are indented) in its block.
    4. *Outdent.* The block has two lines or more and the line starts more than ``indent``
       median line heights to the left of the block's lines after the first: the end of a block
       quote, or the next item of a list with hanging indents.
    5. *End of a sentence.* The previous line is short, ends with ``. ! ? :`` or ``…`` (closing
       quotes and brackets after it allowed), and the line starts with an uppercase letter
       (opening quotes and brackets before it allowed).
    6. *List item.* The line starts with a bullet (``•``, ``◦``, ``▪``, ``●``, ``■`` and the
       like); or the previous line is short and the line's first word is an enumerator such as
       ``1.``, ``2)``, ``(a)`` or ``iv.``.

    A line is *short* when the space it leaves before its column's right edge would have held the
    next line's first word and a space: a typesetter does not end a paragraph's line early when
    the next word fits. The right edge is that of the line's column as ``columns.detect`` finds
    it among the lines given (with its defaults), and no less than the rightmost end among the
    block's lines and the next line; for a line across columns, only the latter. The word's width
    is its box's, or the next line's average character width times its length.

    With ``deskew`` (the default), the rules measure the boxes turned back by the page's skew
    (see ``geometry.skew`` and ``geometry.deskew``), so that the lines lower down a skewed column
    do not seem indented, outdented or short.

    A line without a box breaks no rule and is never broken from: a run of consecutive lines
    without boxes forms one block, and the start or end of such a run starts a block. A block's
    box is the union of its lines' boxes (``None`` when none has one).
    """
    if not (math.isfinite(spacing) and spacing > 0):
        raise ValueError(f"spacing is a finite number > 0, not {spacing!r}")
    if not 0 <= min_overlap <= 1:
        raise ValueError(f"min_overlap is a share in [0, 1], not {min_overlap!r}")
    if not (math.isfinite(indent) and indent >= 0):
        raise ValueError(f"indent is a finite number >= 0, not {indent!r}")
    if sources is not None and len(sources) != len(lines):
        raise ValueError(f"sources has {len(sources)} numbers for {len(lines)} lines")
    if not lines:
        return ()
    angle = skew(lines) if deskew else 0.0
    measured = [
        line if line.box is None else Line(line.words, box=turn_back(line.box, angle))
        for line in lines
    ]
    rules = _Rules(measured, spacing=spacing, min_overlap=min_overlap, indent=indent)
    starts = [0]
    for index in range(1, len(lines)):
        if (sources is not None and sources[index] != sources[index - 1]) or rules.starts_block(
            measured, starts[-1], index
        ):
            starts.append(index)
    ends = [*starts[1:], len(lines)]
    return tuple(_block(lines[start:end]) for start, end in zip(starts, ends, strict=True))


class _Rules:
    """The paragraph-break tests, with the page's measurements."""

    def __init__(
        self, lines: Sequence[Line], *, spacing: float, min_overlap: float, indent: float
    ) -> None:
        self.min_overlap = min_overlap
        self.margin = indent * median_height(lines)
        distances = [
            _distance(a.box, b.box)
            for a, b in pairwise(lines)
            if a.box is not None and b.box is not None and self._same_column(a.box, b.box)
        ]
        self.max_distance = spacing * _line_spacing(distances) if distances else math.inf
        columns = detect(lines)
        self.edges = [columns[i][1] if i >= 0 else -math.inf for i in assign(lines, columns)]

    def _same_column(self, previous: Box, box: Box) -> bool:
        return (
            horizontal_overlap(previous, box) >= self.min_overlap
            and box.center[1] > previous.center[1]
        )

    def starts_block(self, lines: Sequence[Line], start: int, index: int) -> bool:
        """Whether ``lines[index]`` starts a new block after the block ``lines[start:index]``."""
        previous, line = lines[index - 1], lines[index]
        if previous.box is None or line.box is None:
            return (previous.box is None) != (line.box is None)
        last, box = previous.box, line.box
        if not self._same_column(last, box) or _distance(last, box) > self.max_distance:
            return True
        boxes = [member.box for member in lines[start:index] if member.box is not None]
        right = max(self.edges[index - 1], box.x1, *(b.x1 for b in boxes))
        short = _leaves_room(right, last, line)
        if (
            box.x0 > last.x0 + self.margin
            and box.x0 > min(b.x0 for b in boxes) + self.margin
            and (len(boxes) > 1 or short)
        ):
            return True
        if len(boxes) > 1 and box.x0 < min(b.x0 for b in boxes[1:]) - self.margin:
            return True
        if _starts_with_bullet(line.text):
            return True
        return short and (
            (_ends_sentence(previous.text) and _starts_uppercase(line.text))
            or _starts_with_enumerator(line)
        )


def _line_spacing(distances: list[float]) -> float:
    """The median of the smaller half of the distances (the smallest of fewer than four)."""
    ordered = sorted(distances)
    return median(ordered[: max(1, len(ordered) // 2)])


def _distance(previous: Box, box: Box) -> float:
    return max(box.y0 - previous.y0, box.y1 - previous.y1)


def _leaves_room(right: float, previous: Box, line: Line) -> bool:
    """Whether the next line's first word and a space fit between ``previous`` and ``right``."""
    if line.box is None or not line.words or not line.text:
        return False
    character = line.box.width / len(line.text)
    first = line.words[0]
    word = first.box.width if first.box is not None else len(first.text) * character
    return right - previous.x1 > word + character


def _ends_sentence(text: str) -> bool:
    stripped = text.rstrip().rstrip(_CLOSING)
    return bool(stripped) and stripped[-1] in _SENTENCE_END


def _starts_uppercase(text: str) -> bool:
    stripped = text.lstrip().lstrip(_OPENING)
    return bool(stripped) and stripped[0].isupper()


def _starts_with_bullet(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0] in _BULLETS


def _starts_with_enumerator(line: Line) -> bool:
    return bool(line.words) and _ENUMERATOR.fullmatch(line.words[0].text) is not None


def _block(lines: Sequence[Line]) -> Block:
    return Block(tuple(lines), box=union_of(line.box for line in lines))
