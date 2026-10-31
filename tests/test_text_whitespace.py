import itertools
import re
import time
from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, Revision, apply_edits
from lectris.text import whitespace
from lectris.text.whitespace import collapse, line_breaks, trim


def assert_contract(text: str, revision: Revision, rule: str) -> None:
    """Edits name the rule, are sorted and apart, and turn ``text`` into the revision's text."""
    assert apply_edits(text, revision.edits) == revision.text
    assert all(edit.rule == rule for edit in revision.edits)
    assert all(a.end <= b.start for a, b in itertools.pairwise(revision.edits))


TEXT = st.text(
    alphabet=st.one_of(
        st.sampled_from("ab.  \t\t\n\n\r\u2028\u2029\u00a0\u0085\x0c"),
        st.characters(codec="utf-8"),
    ),
    max_size=40,
)

LONG_INPUTS = [
    (trim, "a" + " " * 50_000 + "\x0bb"),
    (trim, "a" + "\n " * 25_000 + "b"),
    (collapse, "a" + " \t" * 25_000 + "\n"),
]


class TestLineBreaks:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("one\r\ntwo\rthree", "one\ntwo\nthree"),
            ("a\r\n\r\nb\u2028c\u2029d\r", "a\n\nb\nc\n\nd\n"),
            ("First paragraph.\u2029Second.", "First paragraph.\n\nSecond."),
        ],
    )
    def test_breaks_become_newlines(self, text: str, expected: str) -> None:
        revision = line_breaks(text)
        assert revision.text == expected
        assert_contract(text, revision, "whitespace.line_breaks")

    def test_each_break_is_one_edit(self) -> None:
        assert line_breaks("a\r\nb\rc").edits == (
            Edit("whitespace.line_breaks", 1, 3, "\r\n", "\n"),
            Edit("whitespace.line_breaks", 4, 5, "\r", "\n"),
        )

    @pytest.mark.parametrize("text", ["one\ntwo", "page\x0cpage, a\x0bb, said\u0085"])
    def test_other_controls_are_left_alone(self, text: str) -> None:
        assert not line_breaks(text).changed

    @given(TEXT)
    def test_properties(self, text: str) -> None:
        revision = line_breaks(text)
        assert_contract(text, revision, "whitespace.line_breaks")
        assert line_breaks(revision.text).edits == ()
        assert not set("\r\u2028\u2029") & set(revision.text)
        breaks = len(re.findall("\r\n?|[\n\u2028]", text)) + 2 * text.count("\u2029")
        assert revision.text.count("\n") == breaks


class TestCollapse:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("end.   Next", "end. Next"),
            ("a\t\tb \t c", "a b c"),
            ("one  two\nthree    four", "one two\nthree four"),
        ],
    )
    def test_runs_between_words_become_one_space(self, text: str, expected: str) -> None:
        revision = collapse(text)
        assert revision.text == expected
        assert_contract(text, revision, "whitespace.collapse")

    def test_each_run_is_one_edit(self) -> None:
        assert collapse("a  b \t c").edits == (
            Edit("whitespace.collapse", 1, 3, "  ", " "),
            Edit("whitespace.collapse", 4, 7, " \t ", " "),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "name\tvalue",  # a single tab may separate table columns
            "  indented, trailing  \nnext\n\n\nline",  # line edges are trim's
            "a\u00a0 b",  # a run next to other whitespace
        ],
    )
    def test_other_whitespace_is_left_alone(self, text: str) -> None:
        assert not collapse(text).changed

    @given(TEXT)
    def test_properties(self, text: str) -> None:
        revision = collapse(text)
        assert_contract(text, revision, "whitespace.collapse")
        assert collapse(revision.text).edits == ()
        assert re.search(r"\S[ \t]{2,}\S", revision.text) is None
        assert revision.text.count("\n") == text.count("\n")


class TestTrim:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("\n\n  first\nsecond \t\n\n", "first\nsecond"),
            ("one  \n  two", "one\ntwo"),
            ("one\n   \ntwo", "one\n\ntwo"),  # an inner blank line stays, emptied
            (" \n\t\n", ""),
        ],
    )
    def test_line_edges_and_blank_block_edges_are_removed(self, text: str, expected: str) -> None:
        revision = trim(text)
        assert revision.text == expected
        assert_contract(text, revision, "whitespace.trim")

    def test_each_run_is_one_edit(self) -> None:
        assert trim("\n a \n b").edits == (
            Edit("whitespace.trim", 0, 2, "\n ", ""),
            Edit("whitespace.trim", 3, 4, " ", ""),
            Edit("whitespace.trim", 5, 6, " ", ""),
        )

    def test_inner_spaces_and_other_whitespace_are_left_alone(self) -> None:
        assert not trim("a  b\nc\td \u00a0x\x0c").changed

    @given(TEXT)
    def test_properties(self, text: str) -> None:
        revision = trim(text)
        assert_contract(text, revision, "whitespace.trim")
        assert trim(revision.text).edits == ()
        lines = (line.strip(" \t") for line in text.split("\n"))
        assert revision.text == "\n".join(lines).strip("\n")


def test_the_rules_in_order() -> None:
    assert (line_breaks, collapse, trim) == whitespace.RULES
    text = "  first  line \r\n\r\n second\r\n"
    for rule in whitespace.RULES:
        text = rule(text).text
    assert text == "first line\n\nsecond"


@pytest.mark.parametrize(("rule", "text"), LONG_INPUTS)
def test_long_input_takes_linear_time(rule: Callable[[str], Revision], text: str) -> None:
    start = time.perf_counter()
    rule(text)
    assert time.perf_counter() - start < 2  # generous for slow CI; quadratic took minutes
