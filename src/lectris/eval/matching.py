"""OCR lines matched one to one with ground-truth lines, by the overlap of their boxes.

``match_lines(ocr, truth)`` pairs each OCR line with at most one ground-truth line and the
reverse. Pairs are taken greedily, from the largest intersection over union (IoU) down, while it
is at least ``threshold`` (0.5 by default); ties go to the earlier OCR line, then the earlier
ground-truth line. Lines without a box are never matched. What is left is unmatched: an OCR line
with no ground truth is an insertion, a ground-truth line with no OCR line a deletion.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from lectris.model import Box


def iou(a: Box, b: Box) -> float:
    """The intersection over union of two boxes; 0.0 when they do not overlap."""
    overlap = a.intersection(b)
    if overlap is None:
        return 0.0
    union = a.area + b.area - overlap.area
    return overlap.area / union if union > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Matching:
    """The pairs ``(ocr index, truth index)``, and the indexes of each side left unmatched."""

    pairs: tuple[tuple[int, int], ...]
    ocr_unmatched: tuple[int, ...]
    truth_unmatched: tuple[int, ...]

    def truth_of(self, ocr_index: int) -> int | None:
        """The ground-truth line matched with OCR line ``ocr_index``, or ``None``."""
        for ocr, truth in self.pairs:
            if ocr == ocr_index:
                return truth
        return None


def match_lines(
    ocr: Sequence[Box | None], truth: Sequence[Box | None], *, threshold: float = 0.5
) -> Matching:
    """Match the lines whose boxes are ``ocr`` with those whose boxes are ``truth``."""
    if not 0 < threshold <= 1:
        raise ValueError(f"the IoU threshold is in (0, 1], not {threshold!r}")
    scored = sorted(
        (
            (-iou(a, b), i, j)
            for i, a in enumerate(ocr)
            if a is not None
            for j, b in enumerate(truth)
            if b is not None
        )
    )
    used_ocr: set[int] = set()
    used_truth: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for negative, i, j in scored:
        if -negative < threshold:
            break
        if i in used_ocr or j in used_truth:
            continue
        pairs.append((i, j))
        used_ocr.add(i)
        used_truth.add(j)
    return Matching(
        tuple(sorted(pairs)),
        tuple(i for i in range(len(ocr)) if i not in used_ocr),
        tuple(j for j in range(len(truth)) if j not in used_truth),
    )
