"""Words to lines: words that share a height and follow each other closely form a line."""

import bisect
import math
from collections import deque
from collections.abc import Sequence

from lectris.layout.geometry import median, span_overlap
from lectris.model import Box, Line, Word, union_of

# A line's matching range is taken from its last few words, so that it follows a skewed line.
_RECENT = 5


class _Run:
    """A line being built from left to right: its words, its extent, and the range words match.

    The range a new word is matched against (``top`` to ``bottom``) is the median top and the
    median bottom of the run's last ``_RECENT`` words.
    """

    def __init__(self, order: int, word: Word, box: Box) -> None:
        self.order = order
        self.words = [word]
        self.x0, self.x1, self.y0 = box.x0, box.x1, box.y0
        self.recent: deque[Box] = deque([box], maxlen=_RECENT)
        self.top, self.bottom = box.y0, box.y1

    def add(self, word: Word, box: Box) -> None:
        self.words.append(word)
        self.x1 = max(self.x1, box.x1)
        self.y0 = min(self.y0, box.y0)
        self.recent.append(box)
        self.top = median(recent.y0 for recent in self.recent)
        self.bottom = median(recent.y1 for recent in self.recent)


class _Open:
    """The runs that can still take words, sorted by the top of their matching range."""

    def __init__(self) -> None:
        self.tops: list[float] = []
        self.runs: list[_Run] = []
        self.tallest = 0.0

    def insert(self, run: _Run) -> None:
        at = bisect.bisect_right(self.tops, run.top)
        self.tops.insert(at, run.top)
        self.runs.insert(at, run)
        self.tallest = max(self.tallest, run.bottom - run.top)

    def remove(self, run: _Run) -> None:
        at = bisect.bisect_left(self.tops, run.top)
        while self.runs[at] is not run:
            at += 1
        del self.tops[at]
        del self.runs[at]

    def near(self, y0: float, y1: float) -> list[_Run]:
        """The runs whose matching range can meet ``y0..y1``: no other run can overlap it."""
        start = bisect.bisect_left(self.tops, y0 - self.tallest)
        end = bisect.bisect_right(self.tops, y1)
        return self.runs[start:end]


def group_words(
    words: Sequence[Word], *, min_overlap: float = 0.5, max_gap: float = 3.0
) -> tuple[Line, ...]:
    """Group words into lines by vertical overlap; returns the lines from top to bottom.

    Words with boxes are taken from left to right. A word joins a line when its ``y`` range
    overlaps the line's by at least ``min_overlap`` of the smaller height, and the horizontal gap
    from the line's right end to the word is at most ``max_gap`` times the median word height.
    When several lines qualify, it joins the one it overlaps most, and of those the nearest.
    Otherwise it starts a line.

    - A line's ``y`` range, for this test, is the median top and median bottom of its last five
      words, not the union of its words: once a line has a few words, one tall word on it (a
      bracket, a rule read as a letter) does not widen the range the words after it are matched
      against, so it does not pull the next line in; and on a skewed scan the range follows the
      line as it climbs or falls, a few words behind. A skewed line of few, widely spaced words
      climbs too far between them: turn the boxes back first (``geometry.deskew``), as
      ``layout.arrange`` does. Measuring the overlap against the smaller height keeps
      punctuation, subscripts and superscripts that lie mostly within the line's height on it.
    - ``max_gap`` keeps two columns apart when their lines share a ``y`` range: a gap wider than
      it ends the line. The default, three word heights, is several times the space between the
      words of a justified line and still narrower than the gutter of most multi-column pages;
      lower it for pages with narrow gutters, raise it for text set with wide spaces or tab stops.
      With ``math.inf``, only the words' heights separate lines.

    Each line's words are in left-to-right order and its box is the union of theirs; lines are
    sorted by top, then left. A new line has no confidence of its own; its words keep theirs.
    Words without a box form one more line, last, in their input order.
    """
    if not 0 < min_overlap <= 1:
        raise ValueError(f"min_overlap is a share in (0, 1], not {min_overlap!r}")
    if not max_gap >= 0:
        raise ValueError(f"max_gap is a number >= 0, not {max_gap!r}")
    boxed = [(index, word, word.box) for index, word in enumerate(words) if word.box is not None]
    loose = tuple(word for word in words if word.box is None)
    if math.isinf(max_gap):
        limit = math.inf
    else:
        limit = max_gap * median(box.height for _, _, box in boxed) if boxed else 0.0
    runs: list[_Run] = []
    open_runs = _Open()
    for index, word, box in sorted(boxed, key=lambda item: (item[2].x0, item[2].y0, item[0])):
        best: _Run | None = None
        best_key = (0.0, 0.0)
        for run in open_runs.near(box.y0, box.y1):
            # Words arrive in order of x0 (so never left of a run's start): a run whose right end
            # is out of this word's reach is out of reach of every word after it.
            gap = box.x0 - run.x1
            if gap > limit:
                open_runs.remove(run)
                continue
            overlap = span_overlap(run.top, run.bottom, box.y0, box.y1)
            key = (overlap, -max(0.0, gap))
            if overlap >= min_overlap and (best is None or key > best_key):
                best, best_key = run, key
        if best is None:
            run = _Run(index, word, box)
            runs.append(run)
            open_runs.insert(run)
        else:
            open_runs.remove(best)
            best.add(word, box)
            open_runs.insert(best)
    runs.sort(key=lambda run: (run.y0, run.x0, run.order))
    lines = [Line(tuple(run.words), box=union_of(word.box for word in run.words)) for run in runs]
    if loose:
        lines.append(Line(loose))
    return tuple(lines)
