"""The document model: pages of blocks of lines of words, with boxes and confidences.

Coordinates are image coordinates: the origin is the top-left corner and ``y`` grows downwards.
A confidence is a float in ``[0, 1]``, or ``None`` when the OCR engine gave none.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _check_confidence(confidence: float | None) -> None:
    if confidence is not None and not (0.0 <= confidence <= 1.0):
        raise ValueError(f"a confidence is between 0 and 1, not {confidence!r}")


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
    """A line of words, left to right."""

    words: tuple[Word, ...]
    box: Box | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        _check_confidence(self.confidence)

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
    """An OCR'd document: its pages in order."""

    pages: tuple[Page, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)
