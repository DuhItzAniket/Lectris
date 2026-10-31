"""The built-in profiles: which rules run, in which order, with which options.

The order matters, in three phases:

1. **Normalise**: line breaks, compatibility forms, invisible characters, ligatures, Unicode
   composition, and spaces, so the rules after see plain text.
2. **Lines**: noise lines are dropped, words hyphenated across lines are joined, and each
   paragraph is unwrapped onto one line. A short tidy-up follows: a soft hyphen de-hyphenation
   declined is now inside a line, where it means nothing, and removing it can leave a space.
3. **Characters**: confusions, separators inside numbers, then the punctuation characters
   (dashes, quotes, ellipses), then the spaces around punctuation, which read those
   characters. These rules read tokens, not lines, so they run on the final lines: unwrapping
   cannot hand them a token they have not seen (``"1\\n.5"`` becomes ``"1 .5"``, which the
   separators rule then repairs).

Each profile is idempotent: cleaning its own output changes nothing (a property test checks
this).
"""

from types import MappingProxyType
from typing import Final

from lectris.pipeline import Profile, Step
from lectris.text import (
    confusables,
    hyphenation,
    noise,
    numbers,
    punctuation,
    unicode,
    unwrap,
    whitespace,
)

_NORMALISE: Final = (
    Step(whitespace.line_breaks),
    # Before invisible, whose joiners depend on the letters next to them: a fullwidth letter
    # must already be the Latin letter it stands for.
    Step(unicode.compatibility),
    Step(unicode.invisible),
    Step(unicode.ligatures),
    # After compatibility, which can leave a sequence only NFC composes: a fullwidth letter
    # that becomes ASCII next to a combining accent.
    Step(unicode.nfc),
    Step(whitespace.collapse),
    Step(whitespace.trim),
)

_UNWRAP: Final = (
    Step(hyphenation.join, lexicon=True),
    Step(unwrap.join_lines),
    Step(unicode.invisible),
    Step(whitespace.collapse),
    Step(whitespace.trim),
)

CONSERVATIVE: Final = Profile(
    name="conservative",
    description=(
        "The safest repairs: line breaks, invisible characters, compatibility forms, "
        "ligatures, Unicode composition, extra spaces, and words hyphenated across lines. "
        "Line breaks are kept."
    ),
    steps=(*_NORMALISE, Step(hyphenation.join, lexicon=True)),
)

STANDARD: Final = Profile(
    name="standard",
    description=(
        "For archival and search: the conservative rules, plus noise lines dropped, each "
        "paragraph unwrapped onto one line, letters read inside numbers, spaces inside numbers "
        "and before punctuation, and dash variants."
    ),
    steps=(
        *_NORMALISE,
        Step(noise.drop_lines),
        *_UNWRAP,
        Step(confusables.in_numbers),
        Step(numbers.separators),
        Step(punctuation.dashes),
        Step(punctuation.spacing),
    ),
)

AGGRESSIVE: Final = Profile(
    name="aggressive",
    description=(
        "Recall over precision: the standard rules, plus digits read inside words, straight "
        "quotes and three-dot ellipses. Review its report before trusting it on text that "
        "matters."
    ),
    steps=(
        *_NORMALISE,
        Step(noise.drop_lines),
        *_UNWRAP,
        Step(confusables.in_numbers),
        Step(numbers.separators),
        Step(confusables.in_words, lexicon=True),
        Step(punctuation.dashes),
        Step(punctuation.quotes, MappingProxyType({"style": "straight"})),
        Step(punctuation.ellipsis, MappingProxyType({"style": "three-dots"})),
        Step(punctuation.spacing),
    ),
)

PROFILES: Final = MappingProxyType(
    {profile.name: profile for profile in (CONSERVATIVE, STANDARD, AGGRESSIVE)}
)


def get(name: str) -> Profile:
    """The built-in profile called ``name``."""
    try:
        return PROFILES[name]
    except KeyError:
        known = ", ".join(PROFILES)
        raise ValueError(f"no profile called {name!r}; the profiles are {known}") from None
