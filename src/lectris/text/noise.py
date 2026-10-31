"""Noise: drop lines that are OCR noise, not text.

Scanner specks, ruled lines and pictures come out of OCR as lines such as ``~~~ ,,, ' |||`` or
``lllllllll``. ``drop_lines`` deletes them, deciding on ``lectris.quality.score``: the shape of
the line's characters, not its words. A line with no visible character is never dropped, and
neither is a section break of asterisks (``lectris.text.lexis.SECTION_BREAK``).
"""

from typing import Final

from lectris import quality
from lectris.edits import Edit, Revision, revise
from lectris.text.lexis import SECTION_BREAK

RULE: Final = "noise.drop_lines"


def drop_lines(text: str, /, *, threshold: float = 0.35, min_length: int = 1) -> Revision:
    """Delete each line (split on ``"\\n"``) that ``quality.is_noise`` flags at ``threshold``.

    A line is a candidate only if it has at least ``min_length`` visible characters
    (``quality.Features.length``); raise ``min_length`` to keep short lines whatever they hold.
    Each dropped line is one edit, which deletes the line and one line break: the break after
    it, or the break before it when no kept line follows. The result is the kept lines joined by
    ``"\\n"``. A block whose every line is noise becomes empty.

    A section break set as three or more asterisks (``* * *``, ``***``) is kept: it marks a
    break the author made. Other lines of only punctuation or symbols are dropped at the
    default threshold, including a lone ``}`` in a code listing; a threshold below 0.2 keeps
    them (see ``lectris.quality``).

    Raises ``ValueError`` if ``threshold`` is not in ``[0, 1]`` or ``min_length`` is below 1.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"a threshold is between 0 and 1, not {threshold!r}")
    if min_length < 1:
        raise ValueError(f"min_length is at least 1, not {min_length!r}")
    lines = text.split("\n")
    dropped = [
        quality.features(line).length >= min_length
        and quality.is_noise(line, threshold=threshold)
        and not SECTION_BREAK.fullmatch(line)
        for line in lines
    ]
    last_kept = max((index for index, drop in enumerate(dropped) if not drop), default=-1)
    edits: list[Edit] = []
    start = 0
    for index, line in enumerate(lines):
        end = start + len(line)
        if dropped[index]:
            if 0 <= last_kept < index:
                span = (start - 1, end)
            elif index < len(lines) - 1:
                span = (start, end + 1)
            else:
                span = (start, end)
            edits.append(Edit(RULE, span[0], span[1], text[span[0] : span[1]], ""))
        start = end + 1
    return revise(text, edits)


RULES: Final = (drop_lines,)
