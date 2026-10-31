"""Columns: ``x`` ranges of text, from the gaps in the horizontal projection of the lines' boxes."""

import math
from collections.abc import Sequence
from itertools import pairwise

from lectris.layout.geometry import gaps, median, span_overlap
from lectris.model import Line


def detect(
    lines: Sequence[Line], *, min_gap: float = 1.0, max_spanning: float = 0.25
) -> tuple[tuple[float, float], ...]:
    """The page's columns, as ``(x0, x1)`` ranges from left to right.

    Columns are separated by gutters. A gutter is a gap in the horizontal projection of the lines'
    boxes (see ``geometry.gaps``):

    - at least ``min_gap`` times the median line height wide;
    - crossed at any point by at most ``max_spanning`` of the lines (rounded down), so that a
      title, a footer or a heading across the columns does not close it. With the default, a
      quarter, a two-column page needs at least four lines to tolerate one line across;
    - with at least one line entirely to its left and one entirely to its right.

    The page is cut at the middle of each gutter. A column's range runs from the leftmost start to
    the rightmost end of the lines that lie between two cuts; lines that cross a cut belong to no
    column, and a stretch between cuts that holds no whole line gives no column. A page without a
    gutter has one column, the extent of its lines. Lines without boxes are ignored; when no line
    has a box the result is ``()``.
    """
    if not (math.isfinite(min_gap) and min_gap >= 0):
        raise ValueError(f"min_gap is a finite number >= 0, not {min_gap!r}")
    if not 0 <= max_spanning < 1:
        raise ValueError(f"max_spanning is a share in [0, 1), not {max_spanning!r}")
    boxes = [line.box for line in lines if line.box is not None]
    if not boxes:
        return ()
    height = median(box.height for box in boxes)
    gutters = gaps(
        ((box.x0, box.x1) for box in boxes),
        min_width=min_gap * height,
        max_cover=math.floor(max_spanning * len(boxes)),
    )
    cuts = [-math.inf, *((a + b) / 2 for a, b in gutters), math.inf]
    columns: list[tuple[float, float]] = []
    for low, high in pairwise(cuts):
        inside = [box for box in boxes if low <= box.x0 and box.x1 <= high and box.x0 < high]
        if inside:
            columns.append((min(box.x0 for box in inside), max(box.x1 for box in inside)))
    return tuple(columns)


def assign(lines: Sequence[Line], columns: Sequence[tuple[float, float]]) -> tuple[int, ...]:
    """The index of the column each line lies in.

    A line lies in a column when their ``x`` ranges share some width (or, for a line of zero
    width, when it lies within the column's range). The index is -1 for a line that overlaps
    several columns or none, and for a line without a box.
    """
    result: list[int] = []
    for line in lines:
        index = -1
        if line.box is not None:
            box = line.box
            hits = [
                i for i, (x0, x1) in enumerate(columns) if span_overlap(box.x0, box.x1, x0, x1) > 0
            ]
            if len(hits) == 1:
                index = hits[0]
        result.append(index)
    return tuple(result)
