"""Metrics: character and word error rates (CER, WER) of a hypothesis against a reference.

The counts come from the minimum-edit alignment in ``lectris.align``: substitutions, deletions
(in the reference, missing from the hypothesis) and insertions (in the hypothesis only). The
rate is their sum over the reference's length, so it can exceed 1 when the hypothesis adds a
lot.

With ``normalize=True`` both texts are put in Unicode NFC, every run of whitespace becomes one
space, and leading and trailing whitespace is removed, before anything is counted. Case is kept
unless ``ignore_case=True``, which compares the texts' ``str.casefold()`` (so ``"ß"`` matches
``"ss"``, and lengths are counted after folding).
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from lectris.align import Op, align, align_chars

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ErrorCounts:
    """The errors of a hypothesis against a reference of ``reference_length`` elements."""

    substitutions: int
    deletions: int
    insertions: int
    reference_length: int

    def __post_init__(self) -> None:
        counts = (self.substitutions, self.deletions, self.insertions, self.reference_length)
        if min(counts) < 0:
            raise ValueError(f"error counts are 0 or more, not {counts!r}")
        if self.substitutions + self.deletions > self.reference_length:
            raise ValueError(
                f"{self.substitutions} substitutions and {self.deletions} deletions do not fit "
                f"in a reference of {self.reference_length}"
            )

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self) -> float:
        """``errors / reference_length``; 0.0 when both texts are empty.

        Raises ``ValueError`` when the reference is empty and the hypothesis is not: the rate
        of errors against nothing is undefined.
        """
        if self.reference_length:
            return self.errors / self.reference_length
        if self.errors:
            raise ValueError(
                f"the error rate against an empty reference is undefined ({self.errors} insertions)"
            )
        return 0.0


def _prepare(text: str, *, normalize: bool, ignore_case: bool) -> str:
    if normalize:
        text = _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()
    if ignore_case:
        text = text.casefold()
    return text


def _count(ops: Iterable[Op], reference_length: int) -> ErrorCounts:
    kinds = Counter(op.kind for op in ops)
    return ErrorCounts(kinds["substitute"], kinds["delete"], kinds["insert"], reference_length)


def char_errors(
    reference: str, hypothesis: str, *, normalize: bool = False, ignore_case: bool = False
) -> ErrorCounts:
    """The character errors of ``hypothesis`` against ``reference``; whitespace counts too."""
    reference = _prepare(reference, normalize=normalize, ignore_case=ignore_case)
    hypothesis = _prepare(hypothesis, normalize=normalize, ignore_case=ignore_case)
    return _count(align_chars(reference, hypothesis), len(reference))


def word_errors(
    reference: str, hypothesis: str, *, normalize: bool = False, ignore_case: bool = False
) -> ErrorCounts:
    """The word errors of ``hypothesis`` against ``reference``; words are whitespace-separated."""
    words = _prepare(reference, normalize=normalize, ignore_case=ignore_case).split()
    other = _prepare(hypothesis, normalize=normalize, ignore_case=ignore_case).split()
    return _count(align(words, other), len(words))


def cer(
    reference: str, hypothesis: str, *, normalize: bool = False, ignore_case: bool = False
) -> float:
    """The character error rate: ``char_errors(...).rate``."""
    return char_errors(reference, hypothesis, normalize=normalize, ignore_case=ignore_case).rate


def wer(
    reference: str, hypothesis: str, *, normalize: bool = False, ignore_case: bool = False
) -> float:
    """The word error rate: ``word_errors(...).rate``."""
    return word_errors(reference, hypothesis, normalize=normalize, ignore_case=ignore_case).rate


def confusions(
    reference: str, hypothesis: str, *, normalize: bool = False, ignore_case: bool = False
) -> Counter[tuple[str, str]]:
    """How often each reference character was read as another: ``(reference, hypothesis)`` pairs.

    Only one-to-one substitutions of the character alignment are counted, so ``"m"`` read as
    ``"rn"`` appears as an inserted ``"r"`` and the pair ``("m", "n")``.
    """
    reference = _prepare(reference, normalize=normalize, ignore_case=ignore_case)
    hypothesis = _prepare(hypothesis, normalize=normalize, ignore_case=ignore_case)
    return Counter(
        (op.reference, op.hypothesis)
        for op in align_chars(reference, hypothesis)
        if op.kind == "substitute"
    )
