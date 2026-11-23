"""Matched lines of paired data: what the channel model and the language model are fitted on.

``matched_lines(pairs)`` reads each page of a pairs manifest, drops the OCR lines on don't-care
ground truth, matches the OCR lines with the ground-truth lines that count, and returns, per page,
the matched pairs ``(intended, observed)`` and the text of every line that counts, both in the
normalised track (the form the proposers see once the transforms have run).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from lectris import io
from lectris.eval import truth as truth_io
from lectris.eval.experiment import Pair
from lectris.eval.matching import match_lines
from lectris.eval.scoring import drop_dont_care, normalised


@dataclass(frozen=True, slots=True)
class PageLines:
    """One page's matched line pairs and its ground-truth lines that count."""

    page: str
    pairs: tuple[tuple[str, str], ...]
    truth: tuple[str, ...]


def matched_lines(pairs: Sequence[Pair], *, iou_threshold: float = 0.5) -> Iterator[PageLines]:
    """Each page's matched ``(intended, observed)`` lines and its ground-truth lines."""
    for pair in pairs:
        page = truth_io.read(pair.truth)
        document = drop_dont_care(io.read(pair.engine), page, iou_threshold=iou_threshold)
        counted = page.counted
        lines = [line for p in document.pages for line in p.lines]
        matching = match_lines(
            [line.box for line in lines],
            [line.box for line in counted.lines],
            threshold=iou_threshold,
        )
        yield PageLines(
            pair.page,
            tuple(
                (normalised(counted.lines[j].text), normalised(lines[i].text))
                for i, j in matching.pairs
            ),
            tuple(normalised(line.text) for line in counted.lines),
        )
