import itertools
import re
import time
from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, Revision, apply_edits
from lectris.text import unwrap
from lectris.text.lexis import SECTION_BREAK
from lectris.text.unwrap import join_lines


def assert_contract(text: str, revision: Revision, rule: str) -> None:
    """Edits name the rule, are sorted and apart, and turn ``text`` into the revision's text."""
    assert apply_edits(text, revision.edits) == revision.text
    assert all(edit.rule == rule for edit in revision.edits)
    assert all(a.end <= b.start for a, b in itertools.pairwise(revision.edits))


LIST_ITEM = re.compile(
    r"[ \t]*(?:[-*\u2010\u2013\u2014\u2022\u2023\u2043\u25aa\u25cf\u25e6\u00b7]"
    r"|\d{1,3}[.)]|[A-Za-z]\)|\(\w{1,4}\))[ \t]"
)

PIECES = ["a", "B", "7", " ", "\t", "\n", "\n", "-", "\u2013", "\u00ac", "\u00ad", ".", "and "]
MARKERS = ["- ", "\u2022 ", "1. ", "a) ", "(iv) ", "* * *", "***"]
LONG_INPUTS = [
    (join_lines, "a" + " " * 50_000 + "\n b"),
    (join_lines, "* " * 25_000 + "x\nb"),
]
LINES = st.lists(
    st.one_of(st.sampled_from(PIECES + MARKERS), st.characters(codec="utf-8")), max_size=30
).map("".join)


class TestJoinLines:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("The cat\nsat on  \n  the mat.", "The cat sat on the mat."),
            ("a well-\nknown fact", "a well-known fact"),  # a compound's hyphen
            ("Jean-\nPierre and COVID-\n19", "Jean-Pierre and COVID-19"),
            ("the years 1914\u2013\n1918", "the years 1914\u20131918"),
            ("pre-\nand post-war, Ein-\nund Ausgang", "pre- and post-war, Ein- und Ausgang"),
            ("rock-\nand-roll", "rock-and-roll"),  # a conjunction inside a compound
            ("a pause -\nthen more", "a pause - then more"),  # a dash, not a hyphen
            ("Haus\u00ac\nt\u00fcr, Jean\u2e17\nPierre", "Haus-t\u00fcr, Jean-Pierre"),
            ("Ein\u00ac\nund Ausgang", "Ein- und Ausgang"),  # Fraktur hyphens
            ("exam\u00ad\nple", "example"),  # a soft hyphen marks a split word
        ],
    )
    def test_lines_are_joined(self, text: str, expected: str) -> None:
        revision = join_lines(text)
        assert revision.text == expected
        assert_contract(text, revision, "unwrap.join_lines")

    def test_each_line_break_is_one_edit(self) -> None:
        assert join_lines("one \ntwo-\nthree").edits == (
            Edit("unwrap.join_lines", 3, 5, " \n", " "),
            Edit("unwrap.join_lines", 9, 10, "\n", ""),
        )
        assert join_lines("Haus\u00ac \nt\u00fcr").edits == (
            Edit("unwrap.join_lines", 4, 7, "\u00ac \n", "-"),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "Steps:\n- flour\n* sugar\n\u2022 eggs\n1. mix\n2) bake\na) or (iv) fry",
            "one paragraph\n\nanother\n \t\nand a third",  # blank lines separate paragraphs
            "\nleading and trailing\n",
            "single line, no breaks",
            "the end of one.\n* * *\nThe next morning came.",  # section breaks
            "End.\n***\nStart.",
        ],
    )
    def test_list_items_blank_lines_and_section_breaks_keep_their_line_breaks(
        self, text: str
    ) -> None:
        assert not join_lines(text).changed

    def test_a_list_item_continues_on_its_next_line(self) -> None:
        text = "Notes:\n- the first item\nwraps here\n- the second"
        assert join_lines(text).text == "Notes:\n- the first item wraps here\n- the second"

    @given(LINES)
    def test_properties(self, text: str) -> None:
        revision = join_lines(text)
        assert_contract(text, revision, "unwrap.join_lines")
        assert join_lines(revision.text).edits == ()
        joints = {"", " ", "-", "- "}
        assert all("\n" in edit.before and edit.after in joints for edit in revision.edits)
        for current, following in itertools.pairwise(revision.text.split("\n")):
            blank = not current.strip(" \t") or not following.strip(" \t")
            section = SECTION_BREAK.fullmatch(current) or SECTION_BREAK.fullmatch(following)
            assert blank or section or LIST_ITEM.match(following)


def test_the_rules() -> None:
    assert (join_lines,) == unwrap.RULES


@pytest.mark.parametrize(("rule", "text"), LONG_INPUTS)
def test_long_input_takes_linear_time(rule: Callable[[str], Revision], text: str) -> None:
    start = time.perf_counter()
    rule(text)
    assert time.perf_counter() - start < 2  # generous for slow CI; quadratic took minutes
