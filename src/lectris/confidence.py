"""Confidence: word confidences aggregated to lines, blocks and pages, and low-confidence spans.

A confidence is a float in ``[0, 1]``, or ``None`` when the OCR engine gave none. Unknown
confidences are skipped, never counted as zero, and a value aggregated from no known confidence
is ``None``.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from lectris.model import Block, Line, Page

type Method = Literal["weighted", "mean", "min", "geometric"]

METHODS: Final[tuple[Method, ...]] = ("weighted", "mean", "min", "geometric")


def aggregate(
    values: Iterable[tuple[float | None, int]], *, method: Method = "weighted"
) -> float | None:
    """One confidence from ``(confidence, weight)`` pairs; the weight is usually a length.

    Pairs whose confidence is ``None`` are skipped; with no known confidence the result is
    ``None``. The methods:

    - ``"weighted"``: the weighted mean.
    - ``"mean"``: the plain mean; weights are ignored.
    - ``"min"``: the lowest confidence; weights are ignored.
    - ``"geometric"``: the weighted geometric mean, ``exp(sum(w * ln c) / sum(w))``. It is 0 if
      a confidence with a positive weight is 0, and it is pulled down by a low value more than
      the weighted mean is.

    For ``"weighted"`` and ``"geometric"``, pairs with weight 0 do not count, unless every known
    confidence has weight 0: then each counts once. The result always lies between the lowest
    and the highest known confidence.

    Raises ``ValueError`` for an unknown method, a negative weight, or a confidence outside
    ``[0, 1]``.
    """
    if method not in METHODS:
        raise ValueError(f"method is one of {', '.join(METHODS)}, not {method!r}")
    known: list[tuple[float, int]] = []
    for confidence, weight in values:
        if weight < 0:
            raise ValueError(f"a weight is 0 or more, not {weight!r}")
        if confidence is None:
            continue
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"a confidence is between 0 and 1, not {confidence!r}")
        known.append((confidence, weight))
    if not known:
        return None
    if method == "min":
        return min(confidence for confidence, _ in known)
    if method == "mean":
        return _bounded(math.fsum(c for c, _ in known) / len(known), [c for c, _ in known])
    weighted = [(c, w) for c, w in known if w > 0] or [(c, 1) for c, _ in known]
    total = sum(w for _, w in weighted)
    confidences = [c for c, _ in weighted]
    if method == "weighted":
        return _bounded(math.fsum(c * w for c, w in weighted) / total, confidences)
    if min(confidences) == 0.0:
        return 0.0
    mean = math.exp(math.fsum(w * math.log(c) for c, w in weighted) / total)
    return _bounded(mean, confidences)


def _bounded(mean: float, confidences: list[float]) -> float:
    # A mean lies between the extremes; this only removes floating-point rounding.
    return min(max(mean, min(confidences)), max(confidences))


def line_confidence(line: Line, *, method: Method = "weighted") -> float | None:
    """The line's own confidence if it has one, else its words' aggregated by ``method``.

    Each word is weighted by its length in characters.
    """
    if line.confidence is not None:
        return line.confidence
    return aggregate(((word.confidence, len(word.text)) for word in line.words), method=method)


def block_confidence(block: Block, *, method: Method = "weighted") -> float | None:
    """The block's lines' confidences (``line_confidence``) aggregated by ``method``.

    Each line is weighted by the length of its text, so its spaces count with its letters.
    """
    return _lines_confidence(block.lines, method)


def page_confidence(page: Page, *, method: Method = "weighted") -> float | None:
    """Every line's confidence (``line_confidence``) on the page, aggregated by ``method``.

    Lines are weighted by the length of their text, as in ``block_confidence``; blocks are not
    weighted separately.
    """
    return _lines_confidence(page.lines, method)


def _lines_confidence(lines: Iterable[Line], method: Method) -> float | None:
    return aggregate(
        ((line_confidence(line, method=method), len(line.text)) for line in lines), method=method
    )


@dataclass(frozen=True, slots=True)
class Span:
    """A stretch of a block's text whose words the OCR engine was unsure of.

    ``text == block.text[start:end]``; ``confidence`` is the lowest of its words'.
    """

    start: int
    end: int
    text: str
    confidence: float


def low_confidence_spans(block: Block, *, threshold: float = 0.6) -> tuple[Span, ...]:
    """The spans of ``block.text`` whose words have a confidence below ``threshold``.

    Offsets are in ``block.text``: lines joined by ``"\\n"``, words by one space. A word without
    a confidence takes its line's; when neither has one, the word is never low. Low words next
    to each other on a line make one span, which covers the spaces between them; a span never
    crosses a line break. Words with empty text are skipped: they neither start nor end a span.

    Raises ``ValueError`` if ``threshold`` is not in ``[0, 1]``.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"a threshold is between 0 and 1, not {threshold!r}")
    text = block.text
    spans: list[Span] = []
    line_start = 0
    for line in block.lines:
        run: tuple[int, int, float] | None = None
        position = line_start
        for word in line.words:
            end = position + len(word.text)
            confidence = line.confidence if word.confidence is None else word.confidence
            if word.text and confidence is not None and confidence < threshold:
                if run is None:
                    run = (position, end, confidence)
                else:
                    run = (run[0], end, min(run[2], confidence))
            elif word.text and run is not None:
                spans.append(Span(run[0], run[1], text[run[0] : run[1]], run[2]))
                run = None
            position = end + 1
        if run is not None:
            spans.append(Span(run[0], run[1], text[run[0] : run[1]], run[2]))
        line_start += len(line.text) + 1
    return tuple(spans)
