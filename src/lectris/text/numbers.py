"""Numbers: the spaces OCR inserts around the separators inside a number.

OCR engines often see the narrow gap before a decimal point or thousands separator as a space:
``"3 .14"``, ``"1 ,000"``. ``separators`` removes those spaces where the layout of the digits
shows the separator is inside one number, and leaves sentence ends, lists, dates, times and
versions as they are.
"""

import re
from typing import Final

from lectris.edits import Edit, Revision, revise

SEPARATORS: Final = "numbers.separators"

# Digit groups joined by "." or ",", with optional spaces on either side of each separator, not
# attached to a letter, digit or underscore, and not continuing a number on the left.
_CHAIN: Final = re.compile(r"(?<![\w.,])[0-9]+(?: *[.,] *[0-9]+)+(?!\w)")
_GAP: Final = re.compile(r"(?P<before> *)(?P<separator>[.,])(?P<after> *)")
# The digits in a thousands group, and the most before the first comma.
_GROUP: Final = 3


def _join(gap: re.Match[str], thousands: bool) -> bool:
    """Whether the spaces around one separator are inside a number; ``thousands`` says whether
    the run's commas are laid out as thousands separators."""
    if not gap["before"] or gap["after"]:
        return False
    return gap["separator"] == "." or thousands


def separators(text: str, /) -> Revision:
    """Remove the spaces OCR put before a decimal point or thousands separator.

    The rule looks at runs of digit groups joined by ``.`` or ``,``, with or without spaces, that
    are not attached to a letter or underscore. It removes the spaces before a separator that
    has spaces before it and none after, when it is:

    - a ``.``: ``"3 .14"`` becomes ``"3.14"``;
    - a ``,``, and the run's commas are laid out as thousands separators (at most three digits
      before the first, exactly three after each): ``"1 ,000"`` becomes ``"1,000"``, ``"1 ,00
      ,000"`` stays.

    A separator with spaces on both sides is never joined: ``"aged 92 . 3 children survive"``
    ends a sentence, ``"page 12 , 300 words"`` ends a clause, and unwrapping makes ``"52 . 48
    members"`` of a line that ended ``"52 ."``, so ``"1 , 000"`` is left too. Such a space is
    ``punctuation.spacing``'s to remove. A separator with no space before it is never touched
    either, because ``"3. 14"`` may end a sentence and ``"1, 2"`` is a list. Also left alone:
    ``"12 ,5"`` (a decimal comma or a list: no way to tell), dates (``"2024 . 10"``,
    ``"31 . 10 . 2024"``), section numbers (``"1 . 2 . 3"``), ``"v1 .2"`` (attached to a
    letter), ``"10 : 30"`` (only ``.`` and ``,`` are separators here), spaces between digit
    groups with no separator (``"1 000"``, a valid thousands space), and anything across a line
    break.

    A list of three-digit numbers typed with a space before each comma and none after
    (``"101 ,202"``) is joined; that spacing is rare in print. The rule is idempotent.

    >>> separators("pi is 3 .14 and a crowd of 1 ,000").text
    'pi is 3.14 and a crowd of 1,000'
    """
    edits: list[Edit] = []
    for chain in _CHAIN.finditer(text):
        gaps = list(_GAP.finditer(text, chain.start(), chain.end()))
        bounds = [chain.start(), *(end for gap in gaps for end in gap.span()), chain.end()]
        groups = [text[bounds[i] : bounds[i + 1]] for i in range(0, len(bounds), 2)]
        commas = [index for index, gap in enumerate(gaps) if gap["separator"] == ","]
        thousands = bool(commas) and len(groups[commas[0]]) <= _GROUP
        thousands = thousands and all(len(groups[index + 1]) == _GROUP for index in commas)
        edits.extend(
            Edit(SEPARATORS, gap.start(), gap.end(), gap.group(0), gap["separator"])
            for gap in gaps
            if _join(gap, thousands)
        )
    return revise(text, edits)


RULES: Final = (separators,)
