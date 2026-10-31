"""Reading order: a recursive XY-cut over the lines' boxes."""

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from lectris.layout.geometry import deskew as turn_back
from lectris.layout.geometry import gaps, median, skew, span_overlap
from lectris.model import Box, Line

# Lines side by side whose heights overlap by at least this share of the smaller one form a row.
_ROW_OVERLAP = 0.5
# A core needs some height left: at most just under half is trimmed at each end.
_MAX_TRIM = 0.5


@dataclass(frozen=True, slots=True)
class _Item:
    index: int
    box: Box
    core: tuple[float, float]


@dataclass(frozen=True, slots=True)
class _Band:
    """A horizontal band of whitespace between ``ordered[:split]`` and ``ordered[split:]``."""

    split: int
    space: float


def reading_order(
    lines: Sequence[Line],
    *,
    min_gap: float = 1.0,
    max_spanning: float = 0.25,
    trim: float = 0.25,
    deskew: bool = True,
) -> tuple[Line, ...]:
    """The lines in reading order: top to bottom, and column by column, left to right.

    A recursive XY-cut. Starting from all the lines, each region is split in two at a band of
    whitespace that runs across it or down it, and each part is ordered the same way:

    - A cut *down* is a vertical gap between the lines' boxes that no line crosses, at least
      ``min_gap`` times the median line height wide. The left part is read first.
    - A cut *across* is a horizontal band that no line crosses. The top part is read first. Bands
      are found on the lines' cores, their boxes less ``trim`` of their height at the top and at
      the bottom, so ascenders and descenders that reach into the next line do not hide the
      space between two lines. A band's width is the whitespace between the boxes above and
      below it (0 when they touch or overlap).

    At each level the wider of the widest cut down and the widest cut across is taken, and a
    cut down when they are equal. Columns whose gutter is wider than the space between their
    lines and paragraphs are thus read one after the other, and a band across the page wider
    than the gutter (a section break) ends a row of columns.

    When there is no cut down, a title or footer may be what closes the gutter. If a gap at
    least ``min_gap`` line heights wide is crossed by at most ``max_spanning`` of the region's
    lines (rounded down; see ``geometry.gaps``), the lines across its middle are taken as
    spanning lines, and the cut across is the widest band directly above or below one of them.
    Cutting off the title first lets the columns under it be cut down next.

    A region with no cut is read from the top, by the middle of each line's box. Lines side by
    side (their ``x`` ranges apart) whose heights overlap by half the smaller one form a row,
    read from the left. Lines stacked above one another are never put in a row, however much
    their boxes overlap: the boxes of a skewed scan's lines are taller than the text and overlap
    their neighbours'.

    With ``deskew`` (the default), the boxes are first turned back by the page's skew, as
    ``geometry.skew`` estimates it from the word boxes, so that the columns of a skewed scan are
    upright again and the gutter between them is clear (see ``geometry.deskew``). The lines
    returned are the input's, with their boxes unchanged.

    If any line has no box, the lines are returned in their input order: the order the input
    gives is the only evidence for those lines, and ordering the rest around them would scramble
    the text.
    """
    return tuple(
        lines[index]
        for index in reading_order_indices(
            lines, min_gap=min_gap, max_spanning=max_spanning, trim=trim, deskew=deskew
        )
    )


def reading_order_indices(
    lines: Sequence[Line],
    *,
    min_gap: float = 1.0,
    max_spanning: float = 0.25,
    trim: float = 0.25,
    deskew: bool = True,
) -> tuple[int, ...]:
    """The positions of the lines in reading order, as ``reading_order`` puts them.

    ``reading_order(lines)`` is ``lines[i]`` for each ``i`` of this, with the same options.
    """
    if not (math.isfinite(min_gap) and min_gap >= 0):
        raise ValueError(f"min_gap is a finite number >= 0, not {min_gap!r}")
    if not 0 <= max_spanning < 1:
        raise ValueError(f"max_spanning is a share in [0, 1), not {max_spanning!r}")
    if not 0 <= trim < _MAX_TRIM:
        raise ValueError(f"trim is a share in [0, 0.5), not {trim!r}")
    if len(lines) <= 1 or any(line.box is None for line in lines):
        return tuple(range(len(lines)))
    angle = skew(lines) if deskew else 0.0
    boxes = [turn_back(line.box, angle) for line in lines if line.box is not None]
    min_width = min_gap * median(box.height for box in boxes)
    items = [
        _Item(index, box, (box.y0 + trim * box.height, box.y1 - trim * box.height))
        for index, box in enumerate(boxes)
    ]
    result: list[int] = []
    stack = [items]
    while stack:
        region = stack.pop()
        parts = _split(region, min_width, max_spanning) if len(region) > 1 else None
        if parts is None:
            result.extend(item.index for item in _rows(region))
        else:
            stack.extend(reversed(parts))
    return tuple(result)


def _split(region: list[_Item], min_width: float, max_spanning: float) -> list[list[_Item]] | None:
    """The region's parts in reading order, or ``None`` when it has no cut."""
    ordered, bands = _bands(region)
    spread = max(item.box.x0 for item in region) - min(item.box.x1 for item in region)
    if spread <= 0 or spread < min_width:
        # No two lines lie side by side far enough apart for a cut down or a gutter, here or in
        # any part of the region: cutting at the widest band, again and again, ends with the
        # region cut at every band. Doing that at once gives the same parts.
        if not bands:
            return None
        cuts = [0, *(band.split for band in bands), len(ordered)]
        return [ordered[start:end] for start, end in pairwise(cuts)]
    down = _cut_down(region, min_width)
    across = _widest(bands)
    if down is not None and (across is None or down[0] >= across.space):
        return [down[1], down[2]]
    if across is None:
        return None
    if down is None:
        spanning = _spanning_band(region, ordered, bands, min_width, max_spanning)
        if spanning is not None:
            across = spanning
    return [ordered[: across.split], ordered[across.split :]]


def _cut_down(
    region: list[_Item], min_width: float
) -> tuple[float, list[_Item], list[_Item]] | None:
    """The widest vertical gap no line crosses (the leftmost of equals), and the two sides."""
    ordered = sorted(region, key=lambda item: (item.box.x0, item.box.x1, item.index))
    best: tuple[float, int] | None = None
    reach = ordered[0].box.x1
    for position in range(1, len(ordered)):
        width = ordered[position].box.x0 - reach
        if width > 0 and width >= min_width and (best is None or width > best[0]):
            best = (width, position)
        reach = max(reach, ordered[position].box.x1)
    if best is None:
        return None
    width, position = best
    return width, ordered[:position], ordered[position:]


def _bands(region: list[_Item]) -> tuple[list[_Item], list[_Band]]:
    """The region's lines by the top of their cores, and the bands between the cores, in order."""
    ordered = sorted(region, key=lambda item: (item.core[0], item.core[1], item.index))
    highest_below = [0.0] * len(ordered)
    top = math.inf
    for position in range(len(ordered) - 1, -1, -1):
        top = min(top, ordered[position].box.y0)
        highest_below[position] = top
    bands: list[_Band] = []
    core_reach = ordered[0].core[1]
    box_reach = ordered[0].box.y1
    for position in range(1, len(ordered)):
        item = ordered[position]
        if item.core[0] > core_reach:
            bands.append(_Band(position, max(0.0, highest_below[position] - box_reach)))
        core_reach = max(core_reach, item.core[1])
        box_reach = max(box_reach, item.box.y1)
    return ordered, bands


def _widest(bands: list[_Band]) -> _Band | None:
    """The widest band, the topmost of equals."""
    return max(bands, key=lambda band: (band.space, -band.split), default=None)


def _spanning_band(
    region: list[_Item],
    ordered: list[_Item],
    bands: list[_Band],
    min_width: float,
    max_spanning: float,
) -> _Band | None:
    """The widest band next to a line that crosses a gutter, if the region has such a gutter."""
    allowed = math.floor(max_spanning * len(region))
    if allowed < 1 or not bands:
        return None
    gutters = gaps(
        ((item.box.x0, item.box.x1) for item in region), min_width=min_width, max_cover=allowed
    )
    middles = [(a + b) / 2 for a, b in gutters]
    splits = [band.split for band in bands]
    candidates: dict[int, _Band] = {}
    for position, item in enumerate(ordered):
        if any(item.box.x0 < middle < item.box.x1 for middle in middles):
            below = bisect.bisect_right(splits, position)
            if below > 0:
                candidates[below - 1] = bands[below - 1]
            if below < len(bands):
                candidates[below] = bands[below]
    return _widest(list(candidates.values()))


def _rows(region: list[_Item]) -> list[_Item]:
    """The region read from the top by the lines' middles, a row of lines side by side from the
    left."""
    rows: list[list[_Item]] = []
    for item in sorted(region, key=lambda item: (item.box.center[1], item.box.x0, item.index)):
        if rows and _beside(rows[-1], item):
            rows[-1].append(item)
        else:
            rows.append([item])
    return [item for row in rows for item in sorted(row, key=lambda i: (i.box.x0, i.index))]


def _beside(row: list[_Item], item: _Item) -> bool:
    """Whether the line is level with the row's first line and clear of all its lines in ``x``."""
    first, box = row[0].box, item.box
    if span_overlap(first.y0, first.y1, box.y0, box.y1) < _ROW_OVERLAP:
        return False
    return all(box.x0 >= other.box.x1 or box.x1 <= other.box.x0 for other in row)
