"""Scoring a cleaned page against its ground truth (experiment protocol §2 and §3).

**References by block.** The OCR lines of the cleaned document are matched with the ground-truth
lines (``matching``). Each block's reference is the text of the ground-truth lines its lines are
matched with, in the block's own order, so a difference in reading order is not an error. A
ground-truth line no OCR line is matched with is a deletion: its characters count as errors,
before and after cleaning alike. Without boxes on either side, nothing can be matched, and the
whole page is compared as one block, in the order each side gives.

**Don't care.** Ground-truth lines marked ``care: false`` (illegible, handwritten, vertical)
do not count, as in GLYPHARIS's page metrics: ``drop_dont_care`` removes, before cleaning, every
OCR line that is matched with no line that counts but is matched with a don't-care line, or lies
mostly (half its area or more) inside one; ``score_page`` scores against the lines that count.

**Two tracks.** ``raw`` compares texts in NFC with whitespace runs made one space (line breaks
are layout, not text). ``normalised``, the primary track, also passes both sides through
LECTRIS's transforms (compatibility forms, invisible characters, ligatures, dashes, straight
quotes, three-dot ellipses), so normalising is not counted as correcting.

**Edit labels.** Each edit a block's rules made is labelled by its effect, in the normalised
track, on the distance from the block's text to its reference: the distance with the edit
applied to the text it was made on, less the distance without it. Below zero it is a *fix*,
above zero a *harm*, otherwise *neutral*. This is the exact marginal effect of the edit where it
was made, with no window to choose.

**Harm rate.** A page's harm rate is the characters its harmful edits broke (the sum of their
effects) divided by the characters of its reference (at least 1): the risk ADR-0002 bounds.
"""

import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from lectris.edits import Edit, apply_edits
from lectris.eval.matching import Matching, match_lines
from lectris.eval.truth import TruthPage
from lectris.metrics import char_errors, word_errors
from lectris.model import Document, Line
from lectris.pipeline import CleanBlock, Result
from lectris.text import punctuation, unicode

type Label = Literal["fix", "harm", "neutral"]

_SPACES = re.compile(r"\s+")


def raw(text: str) -> str:
    """The raw track: NFC, with each whitespace run one space, stripped."""
    return _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip()


def normalised(text: str) -> str:
    """The normalised track: the raw track after LECTRIS's transforms."""
    for transform in (unicode.compatibility, unicode.invisible, unicode.ligatures, unicode.nfc):
        text = transform(text).text
    text = punctuation.dashes(text).text
    text = punctuation.quotes(text, style="straight").text
    text = punctuation.ellipsis(text, style="three-dots").text
    return raw(text)


@dataclass(frozen=True, slots=True)
class EditLabel:
    """One edit, located by block and step, with its effect on the distance and its label."""

    block: int
    step: int
    edit: Edit
    effect: int

    @property
    def label(self) -> Label:
        if self.effect < 0:
            return "fix"
        return "harm" if self.effect > 0 else "neutral"


@dataclass(frozen=True, slots=True)
class Counts:
    """Errors against a reference of ``reference`` elements, before and after cleaning."""

    reference: int
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class PageScore:
    """A cleaned page against its ground truth."""

    page: str
    chars: Counts  # the normalised track
    raw_chars: Counts
    words: Counts  # the normalised track
    labels: tuple[EditLabel, ...]
    matched_lines: int
    ocr_lines: int
    truth_lines: int

    def count(self, label: Label) -> int:
        """How many edits have ``label``."""
        return sum(1 for item in self.labels if item.label == label)

    @property
    def harm_chars(self) -> int:
        """The characters the harmful edits broke."""
        return sum(item.effect for item in self.labels if item.effect > 0)

    @property
    def fixed_chars(self) -> int:
        """The characters the fixing edits repaired."""
        return -sum(item.effect for item in self.labels if item.effect < 0)

    @property
    def harm_rate(self) -> float:
        """``harm_chars`` per character of the reference (ADR-0002's loss for this page)."""
        return self.harm_chars / max(1, self.chars.reference)


def drop_dont_care(document: Document, truth: TruthPage, *, iou_threshold: float = 0.5) -> Document:
    """``document`` without the OCR lines that lie on ``truth``'s don't-care lines.

    Lines are matched with the lines that count first, so a don't-care line never takes a match
    from one that counts; of the lines left, those matched with a don't-care line, or lying half
    or more inside one, are dropped (with blocks left empty). A document whose lines have no
    boxes is returned as it is.
    """
    ignored = [line.box for line in truth.lines if not line.care and line.box is not None]
    if not ignored:
        return document
    lines = [line for page in document.pages for line in page.lines]
    counted = [line.box for line in truth.lines if line.care]
    first = match_lines([line.box for line in lines], counted, threshold=iou_threshold)
    left = list(first.ocr_unmatched)
    second = match_lines([lines[i].box for i in left], ignored, threshold=iou_threshold)
    drop = {id(lines[left[i]]) for i, _ in second.pairs}
    for i in left:
        line_box = lines[i].box
        if (
            line_box is not None
            and line_box.area > 0
            and any(
                (overlap := line_box.intersection(other)) is not None
                and overlap.area >= line_box.area / 2
                for other in ignored
            )
        ):
            drop.add(id(lines[i]))
    if not drop:
        return document
    pages = []
    for page in document.pages:
        blocks = []
        for block in page.blocks:
            kept = tuple(line for line in block.lines if id(line) not in drop)
            if kept:
                blocks.append(replace(block, lines=kept))
        pages.append(replace(page, blocks=tuple(blocks)))
    return replace(document, pages=tuple(pages))


def score_page(result: Result, truth: TruthPage, *, iou_threshold: float = 0.5) -> PageScore:
    """``result`` (one OCR page, cleaned) scored against ``truth``'s lines that count; see the
    module's docs. Drop the OCR lines on don't-care lines first (``drop_dont_care``)."""
    truth = truth.counted
    blocks = _blocks_with_lines(result)
    ocr_lines = [line for _, lines in blocks for line in lines]
    matching = match_lines(
        [line.box for line in ocr_lines],
        [line.box for line in truth.lines],
        threshold=iou_threshold,
    )
    if not matching.pairs and not _any_box(ocr_lines, truth):
        return _score_whole(result, truth, len(ocr_lines))
    references = _references(blocks, truth, matching)
    missing = [truth.lines[j].text for j in matching.truth_unmatched]
    sources = [block.source for block, _ in blocks]
    cleaned = [block.text for block, _ in blocks]
    labels = tuple(
        label
        for (block, _), reference in zip(blocks, references, strict=True)
        for label in _labels(block, reference)
    )
    return PageScore(
        page=truth.page,
        chars=_chars(references, sources, cleaned, missing, normalised),
        raw_chars=_chars(references, sources, cleaned, missing, raw),
        words=_words(references, sources, cleaned, missing),
        labels=labels,
        matched_lines=len(matching.pairs),
        ocr_lines=len(ocr_lines),
        truth_lines=len(truth.lines),
    )


def _blocks_with_lines(result: Result) -> list[tuple[CleanBlock, tuple[Line, ...]]]:
    """Each cleaned block with the lines of the layout block it came from."""
    layout = [block for page in result.document.pages for block in page.blocks]
    if len(layout) != len(result.blocks):
        raise ValueError("the result's blocks do not match its document's")  # pragma: no cover
    return [(block, source.lines) for block, source in zip(result.blocks, layout, strict=True)]


def _any_box(lines: Iterable[Line], truth: TruthPage) -> bool:
    return any(line.box is not None for line in lines) and any(
        line.box is not None for line in truth.lines
    )


def _references(
    blocks: Sequence[tuple[CleanBlock, tuple[Line, ...]]], truth: TruthPage, matching: Matching
) -> list[str]:
    of = dict(matching.pairs)
    references: list[str] = []
    position = 0
    for _, lines in blocks:
        matched = [of.get(position + offset) for offset in range(len(lines))]
        references.append(" ".join(truth.lines[j].text for j in matched if j is not None))
        position += len(lines)
    return references


def _labels(
    block: CleanBlock, reference: str, before: str = "", after: str = ""
) -> list[EditLabel]:
    """The block's edits, labelled against ``reference``; ``before`` and ``after`` are the text
    around the block when the reference is a whole page's."""
    target = normalised(reference)
    labels: list[EditLabel] = []
    text = block.source
    for step, (_, revision) in enumerate(block.revisions):
        if revision.edits:
            base = _distance(target, f"{before} {text} {after}")
            for edit in revision.edits:
                changed = apply_edits(text, (edit,))
                effect = _distance(target, f"{before} {changed} {after}") - base
                labels.append(EditLabel(block.index, step, edit, effect))
        text = revision.text
    return labels


def _distance(reference: str, text: str) -> int:
    return char_errors(reference, normalised(text)).errors


def _chars(
    references: Sequence[str],
    sources: Sequence[str],
    cleaned: Sequence[str],
    missing: Sequence[str],
    prepare: Callable[[str], str],
) -> Counts:
    lost = sum(len(prepare(text)) for text in missing)
    reference = sum(len(prepare(text)) for text in references) + lost
    before = sum(
        char_errors(prepare(ref), prepare(hyp)).errors
        for ref, hyp in zip(references, sources, strict=True)
    )
    after = sum(
        char_errors(prepare(ref), prepare(hyp)).errors
        for ref, hyp in zip(references, cleaned, strict=True)
    )
    return Counts(reference, before + lost, after + lost)


def _words(
    references: Sequence[str],
    sources: Sequence[str],
    cleaned: Sequence[str],
    missing: Sequence[str],
) -> Counts:
    lost = sum(len(normalised(text).split()) for text in missing)
    reference = sum(len(normalised(text).split()) for text in references) + lost
    before = sum(
        word_errors(normalised(ref), normalised(hyp)).errors
        for ref, hyp in zip(references, sources, strict=True)
    )
    after = sum(
        word_errors(normalised(ref), normalised(hyp)).errors
        for ref, hyp in zip(references, cleaned, strict=True)
    )
    return Counts(reference, before + lost, after + lost)


def _score_whole(result: Result, truth: TruthPage, ocr_lines: int) -> PageScore:
    """Without boxes: the page as one block, in each side's own order."""
    reference = " ".join(line.text for line in truth.lines)
    sources = [" ".join(block.source for block in result.blocks)]
    cleaned = [" ".join(block.text for block in result.blocks)]
    texts = [block.source for block in result.blocks]
    labels = tuple(
        label
        for index, block in enumerate(result.blocks)
        for label in _labels(
            block, reference, " ".join(texts[:index]), " ".join(texts[index + 1 :])
        )
    )
    return PageScore(
        page=truth.page,
        chars=_chars([reference], sources, cleaned, [], normalised),
        raw_chars=_chars([reference], sources, cleaned, [], raw),
        words=_words([reference], sources, cleaned, []),
        labels=labels,
        matched_lines=0,
        ocr_lines=ocr_lines,
        truth_lines=len(truth.lines),
    )
