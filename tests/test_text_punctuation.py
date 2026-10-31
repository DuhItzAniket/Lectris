import functools
import itertools
import time
from collections.abc import Callable
from typing import Literal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, Revision, apply_edits
from lectris.text import punctuation
from lectris.text.punctuation import dashes, ellipsis, quotes, spacing


def assert_contract(text: str, revision: Revision, rule: str) -> None:
    """Edits name the rule, are sorted and apart, and turn ``text`` into the revision's text."""
    assert apply_edits(text, revision.edits) == revision.text
    assert all(edit.rule == rule for edit in revision.edits)
    assert all(a.end <= b.start for a, b in itertools.pairwise(revision.edits))


def text_with(targets: str) -> st.SearchStrategy[str]:
    """Text that mixes ``targets``, letters, digits, spaces and line breaks with any character."""
    alphabet = st.one_of(st.sampled_from(targets + "aZ1  \n"), st.characters(codec="utf-8"))
    return st.text(alphabet=alphabet, max_size=40)


LONG_INPUTS = [
    (spacing, "a" + " " * 50_000 + "b"),
    (functools.partial(spacing, high_punctuation=True), "a" + " \t" * 25_000 + "\x0bb"),
    (spacing, "(" * 25_000 + " x " + ")" * 25_000),
]


class TestSpacing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Paris , Lyon and Nice .", "Paris, Lyon and Nice."),
            ("e.g. , ask Dr . Smith", "e.g., ask Dr. Smith"),
            ("( see above )", "(see above)"),
            ("a list ( [ nested ] ) ,", "a list ([nested]),"),
            ("the end \t.\nNext", "the end.\nNext"),
        ],
    )
    def test_spaces_before_closing_and_after_opening_marks_go(
        self, text: str, expected: str
    ) -> None:
        revision = spacing(text)
        assert revision.text == expected
        assert_contract(text, revision, "punctuation.spacing")

    def test_each_run_of_spaces_is_one_edit(self) -> None:
        assert spacing("a  , ( b )").edits == (
            Edit("punctuation.spacing", 1, 3, "  ", ""),
            Edit("punctuation.spacing", 6, 7, " ", ""),
            Edit("punctuation.spacing", 8, 9, " ", ""),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "Pourquoi ? Parce que ; voil\u00e0 : \u00ab oui ! \u00bb \u00bfQu\u00e9 tal ?",
            "pi is 3 . 14 and 1 , 5",  # numbers are for the numbers rule
            "the .gitignore file, a ,b",  # a mark joined to the next word
            "wait ... and wait . . .",  # ellipses
            "mail me@example.com or see https://example.org/a?b=1",
            "[ ] a task, f( x ), ( )",  # empty brackets, brackets inside a word
            "end\n, next",  # line breaks
        ],
    )
    def test_text_without_evidence_is_left_alone(self, text: str) -> None:
        assert not spacing(text).changed

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Pourquoi ? Voil\u00e0 !", "Pourquoi? Voil\u00e0!"),
            ("Note : this ; that", "Note: this; that"),
            ("at 10 : 30 , sharp", "at 10 : 30, sharp"),
        ],
    )
    def test_high_punctuation_removes_spaces_before_colons_and_marks(
        self, text: str, expected: str
    ) -> None:
        assert spacing(text, high_punctuation=True).text == expected

    @given(text_with(" \t.,;:!?()[]{}\"'\u2026\u00ab"), st.booleans())
    def test_properties(self, text: str, high: bool) -> None:
        revision = spacing(text, high_punctuation=high)
        assert_contract(text, revision, "punctuation.spacing")
        assert spacing(revision.text, high_punctuation=high).edits == ()
        assert all(edit.after == "" and not edit.before.strip(" \t") for edit in revision.edits)


class TestQuotes:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("\u201cIt\u2019s here,\u201d she said.", '"It\'s here," she said.'),
            ("\u201eGut,\u201c \u201aSo\u2018, 5\u203210\u2033", "\"Gut,\" 'So', 5'10\""),
        ],
    )
    def test_straight_style(self, text: str, expected: str) -> None:
        revision = quotes(text)
        assert revision.text == expected
        assert_contract(text, revision, "punctuation.quotes")

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ('"Don\'t," she said.', "\u201cDon\u2019t,\u201d she said."),
            ("'Hello' and l'homme", "\u2018Hello\u2019 and l\u2019homme"),
            ("the '90s, the dogs' bones", "the \u201990s, the dogs\u2019 bones"),
            ('("a") \u2014"\'b\'"', "(\u201ca\u201d) \u2014\u201c\u2018b\u2019\u201d"),
        ],
    )
    def test_curly_style(self, text: str, expected: str) -> None:
        revision = quotes(text, style="curly")
        assert revision.text == expected
        assert_contract(text, revision, "punctuation.quotes")

    @pytest.mark.parametrize(
        ("text", "style"),
        [
            ("\u00ab Bonjour \u00bb, \u2039oui\u203a, Hawai\u02bci", "straight"),
            ('5\'10" and 12"', "curly"),  # primes after digits
            ('a " b', "curly"),  # a quote between spaces opens or closes nothing
            ("\u201cdone\u201d", "curly"),
        ],
    )
    def test_text_without_evidence_is_left_alone(
        self, text: str, style: Literal["straight", "curly"]
    ) -> None:
        assert not quotes(text, style=style).changed

    def test_an_unknown_style_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no quote style 'smart'"):
            quotes("x", style="smart")  # type: ignore[arg-type]

    @given(
        text_with("'\"([\u2014\u2018\u2019\u201a\u201c\u201d\u201e\u2032\u2033"),
        st.booleans(),
    )
    def test_properties(self, text: str, curly: bool) -> None:
        style: Literal["straight", "curly"] = "curly" if curly else "straight"
        revision = quotes(text, style=style)
        assert_contract(text, revision, "punctuation.quotes")
        assert quotes(revision.text, style=style).edits == ()
        assert len(revision.text) == len(text)
        assert revision.text.count("\n") == text.count("\n")


class TestDashes:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("well\u2010known", "well-known"),
            ("non\u2011breaking", "non-breaking"),
            ("call 555\u20120199", "call 555-0199"),
        ],
    )
    def test_hyphen_variants_become_hyphen_minus(self, text: str, expected: str) -> None:
        revision = dashes(text)
        assert revision.text == expected
        assert len(revision.edits) == 1
        assert_contract(text, revision, "punctuation.dashes")

    @pytest.mark.parametrize(
        "text",
        [
            "1914\u20131918, a pause \u2014 then \u22125 degrees",  # meaning a hyphen lacks
            "a \u2012 b, run --verbose",  # a figure dash between words; a double hyphen
        ],
    )
    def test_dashes_with_meaning_are_left_alone(self, text: str) -> None:
        assert not dashes(text).changed

    @given(text_with("-\u2010\u2011\u2012\u2013\u2014\u22120"))
    def test_properties(self, text: str) -> None:
        revision = dashes(text)
        assert_contract(text, revision, "punctuation.dashes")
        assert dashes(revision.text).edits == ()
        assert not set("\u2010\u2011") & set(revision.text)
        assert len(revision.text) == len(text)


class TestEllipsis:
    @pytest.mark.parametrize(
        ("text", "style", "expected"),
        [
            ("so\u2026 and so\u2026.", "three-dots", "so... and so...."),
            ("wait . . . what .\u00a0.\u202f.", "three-dots", "wait ... what ..."),
            ("wait... what", "character", "wait\u2026 what"),
            ("U.S. ... and . . .", "character", "U.S. \u2026 and \u2026"),
        ],
    )
    def test_an_ellipsis_takes_the_style(
        self, text: str, style: Literal["three-dots", "character"], expected: str
    ) -> None:
        revision = ellipsis(text, style=style)
        assert revision.text == expected
        assert_contract(text, revision, "punctuation.ellipsis")

    @pytest.mark.parametrize(
        "text",
        [
            "Chapter 1 ........ 5, so.... and . . . .",  # leaders, four dots
            "a .. b, . ., end.  . .",  # two dots, dots apart by more than one space
        ],
    )
    def test_runs_that_are_not_ellipses_are_left_alone(self, text: str) -> None:
        assert not ellipsis(text).changed
        assert not ellipsis(text, style="character").changed

    def test_an_unknown_style_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no ellipsis style 'dots'"):
            ellipsis("x", style="dots")  # type: ignore[arg-type]

    @given(text_with(". .\u2026\u00a0"), st.booleans())
    def test_properties(self, text: str, character: bool) -> None:
        style: Literal["three-dots", "character"] = "character" if character else "three-dots"
        revision = ellipsis(text, style=style)
        assert_contract(text, revision, "punctuation.ellipsis")
        assert ellipsis(revision.text, style=style).edits == ()
        assert revision.text.count("\n") == text.count("\n")


def test_the_rules_in_order() -> None:
    assert (ellipsis, dashes, quotes, spacing) == punctuation.RULES
    text = "wait . . . \u201cwell\u2010known\u201d , ( he said )"
    for rule in punctuation.RULES:
        text = rule(text).text
    assert text == 'wait ... "well-known", (he said)'


@pytest.mark.parametrize(("rule", "text"), LONG_INPUTS)
def test_long_input_takes_linear_time(rule: Callable[[str], Revision], text: str) -> None:
    start = time.perf_counter()
    rule(text)
    assert time.perf_counter() - start < 2  # generous for slow CI; quadratic took minutes
