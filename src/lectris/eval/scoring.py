"""Scoring a cleaned page against its ground truth (experiment protocol §2 and §3).

**References by block.** The OCR lines of the cleaned document are matched with the ground-truth
lines (``matching``). Each block's reference is the text of the ground-truth lines its lines are
matched with, in the block's own order, one per line, so a difference in reading order is not an
error. A ground-truth line no OCR line is matched with is a deletion: its characters count as
errors, before and after cleaning alike. Without boxes on either side, nothing can be matched,
and the whole page is compared as one block, in the order each side gives.

**Don't care.** Ground-truth lines marked ``care: false`` (illegible, handwritten, vertical)
do not count, as in GLYPHARIS's page metrics: ``drop_dont_care`` removes, before cleaning, every
OCR line that is matched with no line that counts but is matched with a don't-care line, or lies
mostly (half its area or more) inside one; ``score_page`` scores against the lines that count.

**Layout-neutral references.** Line-level ground truth (HierText, GDC) transcribes each printed
line as it stands, line-end hyphens included, while the cleaned text joins lines and rejoins
hyphenated words. Against such a reference a correct de-hyphenation would count as a harm
(RISK_REGISTER R-15). So the reference the cleaned text is compared with is laid out the way the
cleaned text was: the block's reference lines, joined by line breaks, are passed through the
same layout steps the system ran (``hyphenation.join`` and ``unwrap.join_lines``, in the
profile's order). ``hyphenation.join`` proposes, and its decisions are the system's: the
reference rejoins a word across a line break exactly where the system rejoined the block's
(that break mapped back to the block's OCR lines, and both lines on its sides matched), when the
rule finds a word to rejoin there. The policy is not asked again on the ground truth: a scoring
policy (``risk``) scores only the OCR's candidates, so its decisions on the reference would not
be the system's (LX-TEST-001's re-run). A line-break decision is then the same on both sides and
is neither a fix nor a harm; where the OCR text near a line end differs from the ground truth,
the two sides can still differ, and that difference counts. Without boxes (the page compared
as one block), the reference is laid out under the system's policy. The uncorrected text is
compared with the reference lines as they are. Layout edits are labelled *layout*: they are
scored apart, on data with reading-text ground truth.

**Two tracks.** ``raw`` compares texts in NFC with whitespace runs made one space (line breaks
are layout, not text). ``normalised``, the primary track, also passes both sides through
LECTRIS's transforms (compatibility forms, invisible characters, ligatures, dashes, straight
quotes, three-dot ellipses), so normalising is not counted as correcting.

**Edit labels.** Each edit a block's rules made is labelled by its effect, in the normalised
track, on the distance from the block's text to its (laid-out) reference: the distance with the
edit applied to the text it was made on, less the distance without it. Below zero it is a *fix*,
above zero a *harm*, otherwise *neutral*; an edit of a layout rule is *layout*, whatever its
effect. This is the exact marginal effect of the edit where it was made, with no window to
choose.

**Harm rate.** A page's harm rate is the characters its harmful edits broke (the sum of their
effects) divided by the characters of its reference (at least 1): the risk ADR-0002 bounds.
"""

import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from lectris.decide import PARITY, Policy
from lectris.edits import Candidate, Edit, OffsetMap, apply_edits, revise
from lectris.eval.matching import Matching, match_lines
from lectris.eval.truth import TruthPage
from lectris.lexicon import Lexicon
from lectris.metrics import char_errors, word_errors
from lectris.model import Document, Line
from lectris.pipeline import CleanBlock, Result, Step
from lectris.text import punctuation, unicode

type Label = Literal["fix", "harm", "neutral", "layout"]

LAYOUT_RULES: Final = frozenset({"hyphenation.join", "unwrap.join_lines"})
"""The rules that lay text out (join lines, rejoin hyphenated words): scored apart."""

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


def lay_out(
    text: str,
    steps: Sequence[Step],
    policy: Policy,
    lexicon: Lexicon | None = None,
    *,
    joins: frozenset[int] | None = None,
) -> str:
    """``text`` through the layout steps among ``steps``, in their order, under ``policy``.

    With ``joins``, ``hyphenation.join`` joins a word exactly at those line junctions of
    ``text`` (``k``: the break after its line ``k``, counting from 0) where the rule finds one,
    whatever ``policy`` would decide: the decisions a system made on its own text, carried over
    to the reference (``score_page``).
    """
    for step in steps:
        if step.id == _HYPHENATION and joins is not None:
            found = step.apply(text, lexicon, PARITY).edits
            text = revise(text, [e for e in found if _junction(text, e) in joins]).text
        elif step.id in LAYOUT_RULES:
            text = step.apply(text, lexicon, policy).text
    return text


_HYPHENATION: Final = "hyphenation.join"


def _junction(text: str, edit: Edit) -> int:
    """The line junction a ``hyphenation.join`` edit joins across (each edit spans one break)."""
    return text.count("\n", 0, edit.start + edit.before.index("\n"))


def _joins(block: CleanBlock) -> frozenset[int]:
    """The line junctions of ``block.source`` where the system's ``hyphenation.join`` joined a
    word, found by mapping each of its edits back through the revisions before it."""
    offsets = OffsetMap()
    for rule, revision in block.revisions:
        if rule == _HYPHENATION:
            found: set[int] = set()
            for edit in revision.edits:
                start, end = offsets.source(edit.start, edit.end)
                span = block.source[start:end]
                if span.count("\n") == 1:
                    found.add(block.source.count("\n", 0, start + span.index("\n")))
            return frozenset(found)
        offsets = offsets.then(OffsetMap.from_edits(revision.edits))
    return frozenset()


def _reference_joins(joins: frozenset[int], matched: Sequence[int]) -> frozenset[int]:
    """``joins`` (junctions of the OCR block) as junctions of its reference, whose line ``k`` is
    the ground truth of the block's line ``matched[k]``: a junction carries over when the lines
    on both sides of it are matched."""
    return frozenset(
        k
        for k in range(len(matched) - 1)
        if matched[k] in joins and matched[k + 1] == matched[k] + 1
    )


@dataclass(frozen=True, slots=True)
class EditLabel:
    """One edit, located by block and step, with its effect on the distance and its label."""

    block: int
    step: int
    edit: Edit
    effect: int

    @property
    def label(self) -> Label:
        if self.edit.rule in LAYOUT_RULES:
            return "layout"
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
        return sum(item.effect for item in self.labels if item.label == "harm")

    @property
    def fixed_chars(self) -> int:
        """The characters the fixing edits repaired."""
        return -sum(item.effect for item in self.labels if item.label == "fix")

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


def score_page(
    result: Result,
    truth: TruthPage,
    *,
    iou_threshold: float = 0.5,
    lexicon: Lexicon | None = None,
    steps: Sequence[Step] | None = None,
) -> PageScore:
    """``result`` (one OCR page, cleaned) scored against ``truth``'s lines that count; see the
    module's docs. Drop the OCR lines on don't-care lines first (``drop_dont_care``).

    The reference is laid out with ``steps`` (by default, those of the built-in profile the
    result names), under the result's policy, with ``lexicon``: pass the ones ``clean()`` used.
    """
    if steps is None:
        from lectris.profiles import get  # noqa: PLC0415 - the profiles import the pipeline

        steps = get(result.profile).steps

    def laid(text: str) -> str:
        return lay_out(text, steps, result.policy, lexicon)

    truth = truth.counted
    blocks = _blocks_with_lines(result)
    ocr_lines = [line for _, lines in blocks for line in lines]
    matching = match_lines(
        [line.box for line in ocr_lines],
        [line.box for line in truth.lines],
        threshold=iou_threshold,
    )
    if not matching.pairs and not _any_box(ocr_lines, truth):
        return _score_whole(result, truth, len(ocr_lines), laid)
    found = _references(blocks, truth, matching)
    references = [reference for reference, _ in found]
    laid_out = _laid_out(blocks, found, steps, result.policy, lexicon)
    missing = [truth.lines[j].text for j in matching.truth_unmatched]
    sources = [block.source for block, _ in blocks]
    cleaned = [block.text for block, _ in blocks]
    labels = tuple(
        label
        for (block, _), reference in zip(blocks, laid_out, strict=True)
        for label in _labels(block, reference)
    )
    return PageScore(
        page=truth.page,
        chars=_chars(references, laid_out, sources, cleaned, missing, prepare=normalised),
        raw_chars=_chars(references, laid_out, sources, cleaned, missing, prepare=raw),
        words=_words(references, laid_out, sources, cleaned, missing),
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
) -> list[tuple[str, tuple[int, ...]]]:
    """Each block's reference: its matched ground-truth lines, one per line, in its order, with
    the block's lines (their offsets in the block) that they are matched with."""
    of = dict(matching.pairs)
    references: list[tuple[str, tuple[int, ...]]] = []
    position = 0
    for _, lines in blocks:
        matched = tuple(o for o in range(len(lines)) if position + o in of)
        references.append(("\n".join(truth.lines[of[position + o]].text for o in matched), matched))
        position += len(lines)
    return references


def _laid_out(
    blocks: Sequence[tuple[CleanBlock, tuple[Line, ...]]],
    references: Sequence[tuple[str, tuple[int, ...]]],
    steps: Sequence[Step],
    policy: Policy,
    lexicon: Lexicon | None,
) -> list[str]:
    """Each block's reference laid out as the block was: its words rejoined across the line
    breaks where the system rejoined the block's, then the other layout steps."""
    return [
        lay_out(
            reference,
            steps,
            policy,
            lexicon,
            joins=_reference_joins(_joins(block), matched),
        )
        for (block, _), (reference, matched) in zip(blocks, references, strict=True)
    ]


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
    laid_out: Sequence[str],
    sources: Sequence[str],
    cleaned: Sequence[str],
    missing: Sequence[str],
    *,
    prepare: Callable[[str], str],
) -> Counts:
    """Character errors: the sources against the references, the cleaned texts against the
    laid-out references, and every missing line's characters on both sides."""
    lost = sum(len(prepare(text)) for text in missing)
    reference = sum(len(prepare(text)) for text in references) + lost
    before = sum(
        char_errors(prepare(ref), prepare(hyp)).errors
        for ref, hyp in zip(references, sources, strict=True)
    )
    after = sum(
        char_errors(prepare(ref), prepare(hyp)).errors
        for ref, hyp in zip(laid_out, cleaned, strict=True)
    )
    return Counts(reference, before + lost, after + lost)


def _words(
    references: Sequence[str],
    laid_out: Sequence[str],
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
        for ref, hyp in zip(laid_out, cleaned, strict=True)
    )
    return Counts(reference, before + lost, after + lost)


def _score_whole(
    result: Result, truth: TruthPage, ocr_lines: int, laid: Callable[[str], str]
) -> PageScore:
    """Without boxes: the page as one block, in each side's own order."""
    reference = "\n".join(line.text for line in truth.lines)
    laid_out = laid(reference)
    sources = [" ".join(block.source for block in result.blocks)]
    cleaned = [" ".join(block.text for block in result.blocks)]
    texts = [block.source for block in result.blocks]
    labels = tuple(
        label
        for index, block in enumerate(result.blocks)
        for label in _labels(block, laid_out, " ".join(texts[:index]), " ".join(texts[index + 1 :]))
    )
    return PageScore(
        page=truth.page,
        chars=_chars([reference], [laid_out], sources, cleaned, [], prepare=normalised),
        raw_chars=_chars([reference], [laid_out], sources, cleaned, [], prepare=raw),
        words=_words([reference], [laid_out], sources, cleaned, []),
        labels=labels,
        matched_lines=0,
        ocr_lines=ocr_lines,
        truth_lines=len(truth.lines),
    )


@dataclass(frozen=True, slots=True)
class LabelledCandidate:
    """A candidate, accepted or not, with its effect where it was proposed (Phase 7's data)."""

    page: str
    block: int
    step: int
    candidate: Candidate
    accepted: bool
    effect: int
    reference_chars: int

    @property
    def fixes(self) -> bool:
        """Whether accepting the candidate brings its block closer to the reference."""
        return self.effect < 0


def label_candidates(
    result: Result,
    truth: TruthPage,
    *,
    iou_threshold: float = 0.5,
    lexicon: Lexicon | None = None,
    steps: Sequence[Step] | None = None,
) -> list[LabelledCandidate]:
    """Every candidate of every decision in ``result`` (layout rules left out), with the exact
    marginal effect it has on its block's distance to the laid-out reference when applied to the
    text its stage received, accepted or not. Pages without boxes give no candidates: their
    blocks have no reference of their own."""
    if steps is None:
        from lectris.profiles import get  # noqa: PLC0415 - the profiles import the pipeline

        steps = get(result.profile).steps
    truth = truth.counted
    blocks = _blocks_with_lines(result)
    ocr_lines = [line for _, lines in blocks for line in lines]
    matching = match_lines(
        [line.box for line in ocr_lines],
        [line.box for line in truth.lines],
        threshold=iou_threshold,
    )
    if not matching.pairs:
        return []
    references = _laid_out(
        blocks, _references(blocks, truth, matching), steps, result.policy, lexicon
    )
    reference_chars = sum(len(normalised(line.text)) for line in truth.lines)
    found: list[LabelledCandidate] = []
    for (block, _), reference in zip(blocks, references, strict=True):
        target = normalised(reference)
        text = block.source
        for step, (_, revision) in enumerate(block.revisions):
            judged = [d for d in revision.decisions if d.candidate.rule not in LAYOUT_RULES]
            if judged:
                base = _distance(target, text)
                for decision in judged:
                    changed = apply_edits(text, (decision.candidate.edit(),))
                    found.append(
                        LabelledCandidate(
                            truth.page,
                            block.index,
                            step,
                            decision.candidate,
                            decision.accepted,
                            _distance(target, changed) - base,
                            reference_chars,
                        )
                    )
            text = revision.text
    return found
