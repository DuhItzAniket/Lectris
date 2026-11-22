"""The document model: pages of blocks of lines of words, with boxes and confidences.

Coordinates are image coordinates: the origin is the top-left corner and ``y`` grows downwards.
A confidence is a float in ``[0, 1]``, or ``None`` when the OCR engine gave none. A line can also
keep what an engine's detector found: its outline (``polygon``) and its score (``detection``),
apart from the recognition ``confidence``. A document can name the ``Engine`` that read it.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

type Point = tuple[float, float]

_MIN_POLYGON_POINTS = 3
_POINT_VALUES = 2


def _check_confidence(confidence: float | None, what: str = "a confidence") -> None:
    if confidence is not None and not (0.0 <= confidence <= 1.0):
        raise ValueError(f"{what} is between 0 and 1, not {confidence!r}")


def _check_polygon(polygon: tuple[Point, ...] | None) -> None:
    if polygon is None:
        return
    if len(polygon) < _MIN_POLYGON_POINTS:
        raise ValueError(f"a polygon has at least 3 points, not {len(polygon)}")
    for point in polygon:
        if len(point) != _POINT_VALUES or not all(math.isfinite(value) for value in point):
            raise ValueError(f"a polygon's points are pairs of finite numbers, not {point!r}")


@dataclass(frozen=True, slots=True)
class Engine:
    """The OCR engine that read a document: its name, its version and its model, when known.

    Evidence fitted on one engine's output (what it confuses, how its confidences are
    calibrated) holds for that engine and model only, so a document keeps them.
    """

    name: str
    version: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("an engine has a name")
        if self.version == "" or self.model == "":
            raise ValueError("an engine's version or model is None when unknown, not empty")


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned rectangle: ``(x0, y0)`` is its top-left corner, ``(x1, y1)`` its
    bottom-right one."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        values = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"a box's coordinates are finite numbers, not {values!r}")
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(f"a box needs x0 <= x1 and y0 <= y1, not {values!r}")

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def union(self, other: "Box") -> "Box":
        """The smallest box that holds both."""
        return Box(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )

    def intersection(self, other: "Box") -> "Box | None":
        """The box both cover, or ``None`` if they do not overlap (touching edges do not)."""
        x0, y0 = max(self.x0, other.x0), max(self.y0, other.y0)
        x1, y1 = min(self.x1, other.x1), min(self.y1, other.y1)
        if x0 >= x1 or y0 >= y1:
            return None
        return Box(x0, y0, x1, y1)


def union_of(boxes: Iterable[Box | None]) -> Box | None:
    """The union of the boxes that are not ``None``, or ``None`` if there are none."""
    result: Box | None = None
    for box in boxes:
        if box is not None:
            result = box if result is None else result.union(box)
    return result


@dataclass(frozen=True, slots=True)
class Word:
    """One word as the OCR engine read it."""

    text: str
    box: Box | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        _check_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class Line:
    """A line of words, left to right.

    ``polygon`` is the line's outline as the engine's detector found it (at least three points,
    for a rotated or curved line), and ``detection`` the detector's score for it, in ``[0, 1]``.
    Both are ``None`` when the engine gives none.
    """

    words: tuple[Word, ...]
    box: Box | None = None
    confidence: float | None = None
    polygon: tuple[Point, ...] | None = None
    detection: float | None = None

    def __post_init__(self) -> None:
        _check_confidence(self.confidence)
        _check_confidence(self.detection, "a detection score")
        _check_polygon(self.polygon)

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @classmethod
    def from_text(
        cls, text: str, *, box: Box | None = None, confidence: float | None = None
    ) -> "Line":
        """A line whose words are ``text`` split on whitespace, without word boxes."""
        return cls(tuple(Word(part) for part in text.split()), box=box, confidence=confidence)


@dataclass(frozen=True, slots=True)
class Block:
    """A region of the page read as one unit, usually a paragraph: lines in reading order."""

    lines: tuple[Line, ...]
    box: Box | None = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True, slots=True)
class Page:
    """One page: its blocks in reading order, and its size when known."""

    blocks: tuple[Block, ...]
    width: float | None = None
    height: float | None = None
    number: int = 1

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.lines)

    @property
    def lines(self) -> tuple[Line, ...]:
        """Every line of the page, block by block."""
        return tuple(line for block in self.blocks for line in block.lines)


@dataclass(frozen=True, slots=True)
class Document:
    """An OCR'd document: its pages in order, and the engine that read it when known."""

    pages: tuple[Page, ...]
    engine: Engine | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)
