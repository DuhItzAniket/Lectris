import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, Revision, apply_edits, revise, substitute, unchanged


class TestEdit:
    def test_an_edit_that_changes_nothing_is_refused(self) -> None:
        with pytest.raises(ValueError, match="itself"):
            Edit("demo.rule", 0, 1, "a", "a")

    def test_before_must_fill_the_span(self) -> None:
        with pytest.raises(ValueError, match="span"):
            Edit("demo.rule", 0, 3, "ab", "x")

    def test_the_span_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="start <= end"):
            Edit("demo.rule", 3, 1, "", "x")

    def test_an_insertion_has_an_empty_span(self) -> None:
        assert Edit("demo.rule", 2, 2, "", "-").before == ""


class TestApplyEdits:
    def test_edits_apply_in_order(self) -> None:
        edits = [Edit("r", 0, 1, "a", "A"), Edit("r", 2, 4, "cd", ""), Edit("r", 5, 5, "", "!")]
        assert apply_edits("abcdef", edits) == "Abe!f"

    def test_overlapping_edits_are_refused(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            apply_edits("abcdef", [Edit("r", 0, 3, "abc", "x"), Edit("r", 2, 4, "cd", "y")])

    def test_an_edit_that_does_not_match_the_text_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected 'zz'"):
            apply_edits("abcdef", [Edit("r", 0, 2, "zz", "x")])


class TestRevise:
    def test_edits_are_sorted(self) -> None:
        revision = revise("abc", [Edit("r", 2, 3, "c", "C"), Edit("r", 0, 1, "a", "A")])
        assert revision == Revision("AbC", (Edit("r", 0, 1, "a", "A"), Edit("r", 2, 3, "c", "C")))
        assert revision.changed

    def test_no_edits_is_unchanged(self) -> None:
        assert revise("abc", []) == unchanged("abc")
        assert not unchanged("abc").changed


class TestSubstitute:
    def test_each_match_is_one_edit(self) -> None:
        revision = substitute("a  b   c", r" {2,}", " ", "whitespace.demo")
        assert revision.text == "a b c"
        assert [(e.start, e.end, e.before) for e in revision.edits] == [(1, 3, "  "), (4, 7, "   ")]

    def test_a_template_expands_groups(self) -> None:
        revision = substitute("x=1", re.compile(r"(\w)=(\d)"), r"\2=\1", "demo.swap")
        assert revision.text == "1=x"

    def test_a_function_can_decline_a_match(self) -> None:
        def only_lowercase(match: re.Match[str]) -> str | None:
            return match.group(0).upper() if match.group(0).islower() else None

        revision = substitute("ab Cd ef", r"\w+", only_lowercase, "demo.upper")
        assert revision.text == "AB Cd EF"
        assert len(revision.edits) == 2

    def test_a_replacement_equal_to_the_match_records_nothing(self) -> None:
        assert substitute("abc", r"b", "b", "demo.same") == unchanged("abc")


@given(st.text(max_size=60), st.text(alphabet="ab ", min_size=1, max_size=3), st.text(max_size=3))
def test_a_substitution_always_reproduces_its_text(text: str, pattern: str, after: str) -> None:
    revision = substitute(text, re.escape(pattern), lambda _: after, "demo.any")
    assert apply_edits(text, revision.edits) == revision.text
    for edit in revision.edits:
        assert text[edit.start : edit.end] == edit.before
