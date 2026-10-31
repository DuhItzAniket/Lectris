"""The box measurements layout needs: overlaps, gaps, medians, projections and skew.

Boxes are in image coordinates: the origin is the top-left corner and ``y`` grows downwards. A
*span* is a closed interval ``(start, end)`` with ``start <= end``: a box's extent along one axis.
"""

import math
from collections.abc import Iterable
from typing import Protocol

from lectris.model import Box, Line

# A larger angle is not the small rotation of a skewed scan: such an estimate is not used.
_MAX_SKEW = math.radians(10)


class Boxed(Protocol):
    """Anything with an optional box: a word, a line or a block."""

    @property
    def box(self) -> Box | None: ...


def _check_span(start: float, end: float) -> None:
    if not start <= end:
        raise ValueError(f"a span needs start <= end, not {start!r}..{end!r}")


def span_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """How much the spans ``a0..a1`` and ``b0..b1`` overlap, as a share of the shorter one.

    The result is between 0 (apart, or touching at one point) and 1 (the shorter span lies inside
    the longer one). A span of zero length counts as fully overlapping when it lies inside the
    other span, ends included, and as not overlapping otherwise.
    """
    _check_span(a0, a1)
    _check_span(b0, b1)
    low, high = max(a0, b0), min(a1, b1)
    shorter = min(a1 - a0, b1 - b0)
    if shorter <= 0:
        return 1.0 if low <= high else 0.0
    return max(0.0, high - low) / shorter


def span_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    """The distance between the spans ``a0..a1`` and ``b0..b1``: 0 when they overlap or touch."""
    _check_span(a0, a1)
    _check_span(b0, b1)
    return max(0.0, max(a0, b0) - min(a1, b1))


def vertical_overlap(a: Box, b: Box) -> float:
    """How much the boxes' ``y`` ranges overlap, as a share of the smaller height (0 to 1).

    Dividing by the smaller height makes a comma or a subscript that lies within a word's height
    overlap it fully. A box of zero height overlaps fully when its ``y`` lies within the other
    box's range, and not at all otherwise.
    """
    return span_overlap(a.y0, a.y1, b.y0, b.y1)


def horizontal_overlap(a: Box, b: Box) -> float:
    """How much the boxes' ``x`` ranges overlap, as a share of the smaller width (0 to 1).

    Zero widths are treated as zero heights are in ``vertical_overlap``.
    """
    return span_overlap(a.x0, a.x1, b.x0, b.x1)


def gap_x(a: Box, b: Box) -> float:
    """The horizontal distance between the boxes: 0 when their ``x`` ranges overlap or touch."""
    return span_gap(a.x0, a.x1, b.x0, b.x1)


def gap_y(a: Box, b: Box) -> float:
    """The vertical distance between the boxes: 0 when their ``y`` ranges overlap or touch."""
    return span_gap(a.y0, a.y1, b.y0, b.y1)


def median(values: Iterable[float]) -> float:
    """The median of the values: the middle one, or the mean of the two middle ones.

    Raises ``ValueError`` when there are no values.
    """
    ordered = sorted(values)
    if not ordered:
        raise ValueError("the median of no values is undefined")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def median_height(items: Iterable[Boxed]) -> float:
    """The median height of the items' boxes; items without a box are skipped.

    Layout thresholds are multiples of this height, so they scale with the scan's resolution.
    Returns 0.0 when no item has a box.
    """
    heights = [item.box.height for item in items if item.box is not None]
    return median(heights) if heights else 0.0


def coverage(spans: Iterable[tuple[float, float]]) -> tuple[tuple[float, float, int], ...]:
    """The spans' projection on their axis: elementary intervals, and how many spans cover each.

    Each pair of consecutive distinct span ends ``a < b`` gives one interval ``(a, b, count)``,
    where ``count`` is the number of spans with ``start <= a`` and ``end >= b``. The intervals run
    in order from the smallest start to the largest end, without holes. No spans give ``()``.
    """
    items = list(spans)
    for start, end in items:
        _check_span(start, end)
    points = sorted({point for span in items for point in span})
    position = {point: index for index, point in enumerate(points)}
    delta = [0] * len(points)
    for start, end in items:
        if start < end:
            delta[position[start]] += 1
            delta[position[end]] -= 1
    intervals: list[tuple[float, float, int]] = []
    count = 0
    for index in range(len(points) - 1):
        count += delta[index]
        intervals.append((points[index], points[index + 1], count))
    return tuple(intervals)


def gaps(
    spans: Iterable[tuple[float, float]], *, min_width: float = 0.0, max_cover: int = 0
) -> tuple[tuple[float, float], ...]:
    """The gaps between the spans: stretches of the projection that at most ``max_cover`` cover.

    A gap ``(a, b)`` is a maximal run of consecutive intervals of ``coverage(spans)`` each covered
    by at most ``max_cover`` spans, with ``b - a >= min_width``, and with at least one span lying
    entirely before it (``end <= a``) and one entirely after it (``start >= b``), so that a gap is
    always between spans, never at either end of the projection. With ``max_cover=0`` the gaps are
    the holes in the union of the spans; a larger ``max_cover`` lets a few spans, such as a title
    across two columns, cross a gap without closing it. Gaps are returned in order.
    """
    if not min_width >= 0:
        raise ValueError(f"min_width is a number >= 0, not {min_width!r}")
    if max_cover < 0:
        raise ValueError(f"max_cover is a count >= 0, not {max_cover!r}")
    items = list(spans)
    intervals = coverage(items)
    if not intervals:
        return ()
    runs: list[tuple[float, float]] = []
    for a, b, count in intervals:
        if count > max_cover:
            continue
        if runs and runs[-1][1] == a:
            runs[-1] = (runs[-1][0], b)
        else:
            runs.append((a, b))
    first_end = min(end for _, end in items)
    last_start = max(start for start, _ in items)
    return tuple(
        (a, b) for a, b in runs if b - a >= min_width and first_end <= a and b <= last_start
    )


def skew(lines: Iterable[Line]) -> float:
    """The angle of the text lines, in radians: positive when they descend to the right.

    Each line with two or more word boxes gives the slope of its words' centres (least squares),
    unless a centre lies further from the fitted line than half the median height of the line's
    word boxes: such a line holds words of more than one row, and its slope is not the page's.
    The estimate is the median of these slopes, each weighted by how far its words spread along
    the line, so long lines count most and no single line decides it. The result is 0 when no
    line gives a slope, or when the angle is over 10 degrees: a skewed scan is turned by a few
    degrees, and a larger estimate comes from something else.
    """
    estimates: list[tuple[float, float]] = []
    for line in lines:
        boxes = [word.box for word in line.words if word.box is not None]
        if len(boxes) <= 1:
            continue
        centres = [box.center for box in boxes]
        mean_x = sum(x for x, _ in centres) / len(centres)
        mean_y = sum(y for _, y in centres) / len(centres)
        spread = sum((x - mean_x) ** 2 for x, _ in centres)
        if spread <= 0:
            continue
        slope = sum((x - mean_x) * (y - mean_y) for x, y in centres) / spread
        tolerance = median(box.height for box in boxes) / 2
        if all(abs(y - mean_y - slope * (x - mean_x)) <= tolerance for x, y in centres):
            estimates.append((slope, spread))
    if not estimates:
        return 0.0
    estimates.sort()
    half = sum(weight for _, weight in estimates) / 2
    reached = 0.0
    chosen = estimates[-1][0]
    for slope, weight in estimates:
        reached += weight
        if reached >= half:
            chosen = slope
            break
    angle = math.atan(chosen)
    return angle if abs(angle) <= _MAX_SKEW else 0.0


def deskew(box: Box, angle: float) -> Box:
    """The box as it lies once the page is turned back by ``angle`` (see ``skew``).

    The box is taken as the axis-aligned bounds of a rectangle turned by ``angle``: its centre is
    turned back about the origin, and the rectangle's own width and height are recovered from the
    bounds (never below 0). For a page turned by a few degrees, a line's box shrinks back to its
    text's height, and the boxes of lines lower down a column move back under those above them.
    """
    if angle == 0:
        return box
    cos, sin = math.cos(angle), math.sin(angle)
    x, y = box.center
    turned_x, turned_y = x * cos + y * sin, y * cos - x * sin
    lean = abs(sin)
    scale = cos * cos - lean * lean
    width = max(0.0, (box.width * cos - box.height * lean) / scale)
    height = max(0.0, (box.height * cos - box.width * lean) / scale)
    return Box(
        turned_x - width / 2, turned_y - height / 2, turned_x + width / 2, turned_y + height / 2
    )
