"""Evidence: the features a candidate edit is judged by (architecture §10).

``Evidence(pack)`` scores candidates with a model pack. For a candidate on a stage's text, with
the map from that text back to the block's source (``OffsetMap``) and the block's lines:

- **channel** (``channel``): log P(``before`` observed | ``after`` intended) minus
  log P(``before`` | ``before``): how plausible the text is as an engine error, compared with
  being written as it is. It is near zero for an error the engine often makes and far below
  zero for one it rarely or never makes;
- **language** (``lm``, ``lm_per_char``): the change in the character model's log probability of
  the span and the few characters after it, given the text before it, when ``after`` replaces
  ``before``;
- **lexicon** (``word_before``, ``word_after``, ``word_gain``): log(1 + count) of the word the
  span lies in (the token without its surrounding punctuation; the weaker part's when the span
  joins or splits tokens), before and after the edit, and their difference;
- **engine** (``line_confidence``, ``detection``, ``engine_missing``): the lowest recognition
  confidence and detection score of the lines the span came from (``engine_missing`` is 1, and
  the others 1.0, when the input has none);
- **shape** (``size``, ``insertion``, ``deletion``, ``digits``): the longer side's length,
  whether nothing is replaced or nothing replaces, and whether the token holds a digit;
- **rule** (``rule=<id>``): 1 for the candidate's rule.

Features already on the candidate (such as ``v01``) are kept. Every value is a finite float;
the names are sorted, as ``Candidate`` requires.
"""

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Final

from lectris.edits import Candidate, OffsetMap
from lectris.model import Line
from lectris.models.pack import ModelPack
from lectris.propose import core_of

_TOKEN: Final = re.compile(r"\S+")
_DIGIT: Final = re.compile(r"\d")
LEFT: Final = 24
"""How many characters before a span the language feature conditions on."""
RIGHT: Final = 6
"""How many characters after a span the language feature scores with it."""


@dataclass(frozen=True, slots=True)
class BlockLines:
    """A block's source text, its lines, and where each line lies in the source."""

    source: str
    lines: tuple[Line, ...]
    spans: tuple[tuple[int, int], ...]

    @classmethod
    def of(cls, source: str, lines: Sequence[Line]) -> "BlockLines":
        """The lines of a block whose source is its lines' text joined by line breaks; any other
        source (plain text, read as it is written) has no lines to point to."""
        if "\n".join(line.text for line in lines) != source:
            return cls(source, (), ())
        spans: list[tuple[int, int]] = []
        position = 0
        for line in lines:
            spans.append((position, position + len(line.text)))
            position += len(line.text) + 1
        return cls(source, tuple(lines), tuple(spans))

    def lines_over(self, start: int, end: int) -> list[Line]:
        """The lines the source span ``[start, end)`` touches (a position, the line it is on)."""
        found = []
        for line, (a, b) in zip(self.lines, self.spans, strict=True):
            if (a <= start <= b) if start == end else (start < b and a < end):
                found.append(line)
        return found


class Evidence:
    """Features for candidates, from a model pack."""

    def __init__(self, pack: ModelPack) -> None:
        self.pack = pack

    def score(
        self,
        text: str,
        candidates: Iterable[Candidate],
        offsets: OffsetMap,
        block: BlockLines,
    ) -> tuple[Candidate, ...]:
        """The candidates with their features (the module's documentation lists them)."""
        return tuple(self._one(text, candidate, offsets, block) for candidate in candidates)

    def _one(
        self, text: str, candidate: Candidate, offsets: OffsetMap, block: BlockLines
    ) -> Candidate:
        before, after = candidate.before, candidate.after
        channel = self.pack.channel.log_likelihood(
            after, before
        ) - self.pack.channel.log_likelihood(before, before)
        left = text[max(0, candidate.start - LEFT) : candidate.start]
        right = text[candidate.end : candidate.end + RIGHT]
        language = self.pack.language.score(after + right, left) - self.pack.language.score(
            before + right, left
        )
        old_word, new_word = _token(text, candidate)
        word_before = self._word_value(old_word)
        word_after = self._word_value(new_word)
        source = offsets.source(candidate.start, candidate.end)
        lines = block.lines_over(*source)
        confidences = [line.confidence for line in lines if line.confidence is not None]
        detections = [line.detection for line in lines if line.detection is not None]
        found = dict(candidate.features)
        found |= {
            "channel": channel,
            "lm": language,
            "lm_per_char": language / max(1, len(before), len(after)),
            "word_before": word_before,
            "word_after": word_after,
            "word_gain": word_after - word_before,
            "line_confidence": min(confidences) if confidences else 1.0,
            "detection": min(detections) if detections else 1.0,
            "engine_missing": 0.0 if confidences else 1.0,
            "size": float(max(len(before), len(after), 1)),
            "insertion": 1.0 if not before else 0.0,
            "deletion": 1.0 if not after else 0.0,
            "digits": 1.0 if _DIGIT.search(old_word) else 0.0,
            f"rule={candidate.rule}": 1.0,
        }
        return replace(candidate, features=tuple(sorted(found.items())))

    def _word_value(self, token: str) -> float:
        """log(1 + count) of the token's word, the weakest part's when it holds a space."""
        parts = [core_of(part) for part in token.split()]
        values = [math.log1p(self.pack.lexicon.frequency(part)) for part in parts if part]
        return min(values) if values else 0.0


def _token(text: str, candidate: Candidate) -> tuple[str, str]:
    """The token the candidate's span lies in, before the edit and after it."""
    start = candidate.start
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = candidate.end
    while end < len(text) and not text[end].isspace():
        end += 1
    old = text[start:end]
    new = text[start : candidate.start] + candidate.after + text[candidate.end : end]
    return old.strip(), new.strip()
