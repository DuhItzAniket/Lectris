import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import (
    Edit,
    OffsetMap,
    Revision,
    apply_edits,
    revise,
    substitute,
    unchanged,
)


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


@st.composite
def revisions(draw: st.DrawFn, text: str | None = None) -> tuple[str, tuple[Edit, ...]]:
    """A text and non-overlapping edits on it: replacements, deletions and insertions."""
    source = draw(st.text(alphabet="abc", max_size=20)) if text is None else text
    edits: list[Edit] = []
    position = 0
    while position <= len(source) and draw(st.booleans()):
        start = draw(st.integers(position, len(source)))
        end = draw(st.integers(start, min(len(source), start + 3)))
        after = draw(st.text(alphabet="xyz", max_size=3))
        if source[start:end] != after:
            edits.append(Edit("demo.any", start, end, source[start:end], after))
        position = end + 1 if end == start else end  # one insertion per gap
    return source, tuple(edits)


def origins(source: str, edits: tuple[Edit, ...]) -> list[tuple[int, int]]:
    """Each output character's input span, by walking the text: the reference for OffsetMap."""
    result: list[tuple[int, int]] = []
    position = 0
    for edit in edits:
        result.extend((index, index + 1) for index in range(position, edit.start))
        result.extend((edit.start, edit.end) for _ in edit.after)
        position = edit.end
    result.extend((index, index + 1) for index in range(position, len(source)))
    return result


class TestOffsetMap:
    def test_untouched_text_maps_exactly(self) -> None:
        revision = substitute("ﬁne day", "ﬁ", "fi", "unicode.ligatures")
        offsets = OffsetMap.from_edits(revision.edits)
        assert revision.text[3:7] == "e da"
        assert offsets.source(3, 7) == (2, 6)

    def test_a_span_reaching_into_an_edit_covers_what_it_replaced(self) -> None:
        revision = substitute("ﬁne", "ﬁ", "fi", "unicode.ligatures")
        offsets = OffsetMap.from_edits(revision.edits)
        assert offsets.source(1, 2) == (0, 1)  # the "i" came from the ligature
        assert offsets.source(0, 3) == (0, 2)

    def test_insertions_deletions_and_positions(self) -> None:
        edits = (Edit("demo.cut", 1, 3, "bc", ""), Edit("demo.add", 4, 4, "", "XY"))
        text = apply_edits("abcde", edits)
        assert text == "adXYe"
        offsets = OffsetMap.from_edits(edits)
        assert offsets.source(2, 4) == (4, 4)  # inserted: from the gap it was inserted in
        assert offsets.source(1, 2) == (3, 4)  # the "d" after the deletion
        assert offsets.source(1) == (3, 3)
        assert offsets.source(len(text)) == (5, 5)  # the end maps to the end

    def test_two_stages(self) -> None:
        first = substitute("a  b", "  ", " ", "whitespace.collapse")
        second = substitute(first.text, "b", "bee", "demo.word")
        offsets = OffsetMap.from_edits(first.edits).then(OffsetMap.from_edits(second.edits))
        assert second.text == "a bee"
        assert offsets.source(2, 5) == (3, 4)
        assert offsets.source(1, 2) == (1, 3)

    def test_no_stages_and_no_edits_are_the_identity(self) -> None:
        assert OffsetMap().source(2, 5) == (2, 5)
        assert OffsetMap.from_edits(()).source(2, 5) == (2, 5)

    @pytest.mark.parametrize(("start", "end"), [(-1, 2), (3, 2)])
    def test_a_span_must_be_ordered(self, start: int, end: int) -> None:
        with pytest.raises(ValueError, match="0 <= start <= end"):
            OffsetMap().source(start, end)

    def test_overlapping_edits_are_refused(self) -> None:
        edits = (Edit("demo.a", 0, 2, "ab", "x"), Edit("demo.b", 1, 3, "bc", "y"))
        with pytest.raises(ValueError, match="overlap"):
            OffsetMap.from_edits(edits)

    @given(revisions(), st.data())
    def test_every_span_matches_the_reference(
        self, revision: tuple[str, tuple[Edit, ...]], data: st.DataObject
    ) -> None:
        source, edits = revision
        reference = origins(source, edits)
        output = apply_edits(source, edits)
        offsets = OffsetMap.from_edits(reversed(edits))  # any order
        assert len(reference) == len(output)
        for start in range(len(output)):
            for end in range(start + 1, len(output) + 1):
                assert offsets.source(start, end) == (reference[start][0], reference[end - 1][1])
        position = data.draw(st.integers(0, len(output)))
        expected = reference[position][0] if position < len(output) else len(source)
        assert offsets.source(position) == (expected, expected)

    @given(revisions())
    def test_characters_no_edit_wrote_map_exactly(
        self, revision: tuple[str, tuple[Edit, ...]]
    ) -> None:
        source, edits = revision
        output = apply_edits(source, edits)
        written: set[int] = set()
        position = 0
        for edit in edits:
            start = edit.start + position
            written.update(range(start, start + len(edit.after)))
            position += len(edit.after) - len(edit.before)
        offsets = OffsetMap.from_edits(edits)
        for index in set(range(len(output))) - written:
            start, end = offsets.source(index, index + 1)
            assert (end - start, source[start:end]) == (1, output[index])

    @given(st.data())
    def test_composition_maps_through_each_stage(self, data: st.DataObject) -> None:
        source, first = data.draw(revisions())
        middle = apply_edits(source, first)
        _, second = data.draw(revisions(middle))
        output = apply_edits(middle, second)
        one, two = OffsetMap.from_edits(first), OffsetMap.from_edits(second)
        both = one.then(two)
        start = data.draw(st.integers(0, len(output)))
        end = data.draw(st.integers(start, len(output)))
        assert both.source(start, end) == one.source(*two.source(start, end))
        assert one.then(two).then(OffsetMap()) == both == OffsetMap().then(one).then(two)
