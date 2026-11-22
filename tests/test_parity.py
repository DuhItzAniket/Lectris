"""Parity (ADR-0006): under the ``PARITY`` policy, v2's pipeline gives v0.1's text and edits.

The reference is the frozen copy of v0.1's rules, pipeline and profiles in ``tests/legacy``. The
comparison covers every sample input, a lexicon, and generated OCR-like text built to reach every
rule: confusions, numbers, hyphens at line ends, punctuation, ligatures and noise lines.
"""

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import legacy.pipeline
import legacy.profiles
from lectris import clean, io
from lectris.lexicon import Lexicon
from lectris.model import Document
from lectris.profiles import PROFILES
from lectris.propose import PROPOSERS

DATA = Path(__file__).parent / "data" / "io"
LEXICON = Lexicon.from_lines(
    [
        "the",
        "survey",
        "river",
        "count",
        "well",
        "known",
        "co",
        "operate",
        "spring",
        "modem",
        "hives",
    ]
)

TOKENS = [
    *["the", "survey", "of", "river", "count", "hives", "each", "spring", "and", "keep", "record"],
    "1O5",
    "l0ng",
    "O.5",
    "3 .5",
    "1 000",
    "10,5",
    "S5",
    "I0",
    "O",
    "0",
    "l",
    "1",
    "co-",
    "well-",
    "spr-",
    "-operate",
    "ing",
    "known",
    "re-",
    "cord",
    "ﬁne",
    "ﬂow",
    "co­operate",
    "a\u200bb",
    chr(0x00A0),  # a no-break space
    chr(0xFF21),  # a fullwidth A
    ",",
    ".",
    ";",
    ":",
    "!",
    "?",
    " ,",
    " .",
    "( a )",
    "[ b ]",
    '"',
    "'",
    "...",
    "…",
    "--",
    "—",
    chr(0x2013),  # an en dash
    "-",
    "§",
    "***",
    "~~~",
    "|||",
    ",,,",
    "'' '",
    "modem",
    "rnodem",
]


@st.composite
def ocr_text(draw: st.DrawFn) -> str:
    """Pages of blocks of lines of tokens, with OCR-like noise."""
    pages = []
    for _ in range(draw(st.integers(1, 2))):
        blocks = []
        for _ in range(draw(st.integers(1, 3))):
            lines = []
            for _ in range(draw(st.integers(1, 4))):
                tokens = draw(st.lists(st.sampled_from(TOKENS), min_size=1, max_size=8))
                separator = draw(st.sampled_from([" ", "  ", "\t", " "]))
                lines.append(separator.join(tokens))
            blocks.append(draw(st.sampled_from(["\n", "\r\n"])).join(lines))
        pages.append("\n\n".join(blocks))
    return "\f".join(pages)


def outcome(result: Any) -> tuple[str, list[tuple[int, int, int, Any]]]:
    """A result's text and every edit, located."""
    return result.text, [(c.page, c.block, c.step, c.edit) for c in result.changes()]


def both(source: Document | str, profile: str, lexicon: Lexicon | None = None) -> None:
    v2 = clean(source, profile=profile, lexicon=lexicon)
    v01 = legacy.pipeline.clean(source, profile=legacy.profiles.get(profile), lexicon=lexicon)
    assert outcome(v2) == outcome(v01)
    decisions = list(v2.decisions())
    proposed = [change for change in v2.changes() if change.edit.rule in PROPOSERS]
    assert all(judgement.decision.accepted for judgement in decisions)
    assert [judgement.decision.candidate.edit() for judgement in decisions] == [
        change.edit for change in proposed
    ]


def test_the_profiles_are_the_frozen_ones() -> None:
    assert {name: p.rule_ids for name, p in PROFILES.items()} == {
        name: p.rule_ids for name, p in legacy.profiles.PROFILES.items()
    }


@pytest.mark.parametrize("profile", sorted(PROFILES))
@pytest.mark.parametrize("name", sorted(path.name for path in DATA.iterdir()))
@pytest.mark.parametrize("lexicon", [None, LEXICON], ids=["no lexicon", "lexicon"])
def test_every_sample(name: str, profile: str, lexicon: Lexicon | None) -> None:
    both(io.read(DATA / name), profile, lexicon)


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_the_readme_example(profile: str) -> None:
    text = (
        "The ﬁrst survey of the river  recorded 1O5 species , most of them\n"
        "in the upper reaches. Later surveys con-\n"
        "firmed the count.\n"
        "~~~ ,,, ' ' |||\n"
        "Water quality fell by 3 .5 percent in ten years."
    )
    both(text, profile)
    if profile == "standard":  # the comparison is not empty: every kind of proposer acted
        rules = {judgement.decision.candidate.rule for judgement in clean(text).decisions()}
        assert rules == {
            "noise.drop_lines",
            "hyphenation.join",
            "confusables.in_numbers",
            "numbers.separators",
            "punctuation.spacing",
        }


@settings(max_examples=300)
@given(ocr_text(), st.sampled_from(sorted(PROFILES)), st.booleans())
def test_generated_text(text: str, profile: str, with_lexicon: bool) -> None:
    both(text, profile, LEXICON if with_lexicon else None)
