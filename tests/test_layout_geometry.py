import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import make_column, make_line, skew_box, skew_line, words_of
from lectris.layout.geometry import (
    coverage,
    deskew,
    gap_x,
    gap_y,
    gaps,
    horizontal_overlap,
    median,
    median_height,
    skew,
    span_gap,
    span_overlap,
    vertical_overlap,
)
from lectris.model import Block, Box, Line, Word

coordinates = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False)
sizes = st.floats(min_value=0, max_value=1e6, allow_nan=False)


@st.composite
def boxes(draw: st.DrawFn) -> Box:
    x0, y0 = draw(coordinates), draw(coordinates)
    return Box(x0, y0, x0 + draw(sizes), y0 + draw(sizes))


class TestOverlap:
    @pytest.mark.parametrize(
        ("other", "expected"),
        [
            (Box(0, 0, 10, 10), 1.0),
            (Box(0, 5, 10, 15), 0.5),
            (Box(0, 8, 10, 28), 0.2),
            (Box(0, 10, 10, 20), 0.0),
            (Box(0, 30, 10, 40), 0.0),
        ],
    )
    def test_vertical_overlap_is_a_share_of_the_smaller_height(
        self, other: Box, expected: float
    ) -> None:
        assert vertical_overlap(Box(0, 0, 10, 10), other) == pytest.approx(expected)

    def test_a_comma_within_a_words_height_overlaps_it_fully(self) -> None:
        word, comma = Box(0, 100, 40, 120), Box(40, 112, 44, 118)
        assert vertical_overlap(word, comma) == 1.0
        assert vertical_overlap(comma, word) == 1.0

    @pytest.mark.parametrize(("y", "expected"), [(100, 1.0), (110, 1.0), (120, 1.0), (121, 0.0)])
    def test_a_box_of_zero_height_overlaps_when_inside(self, y: float, expected: float) -> None:
        assert vertical_overlap(Box(0, 100, 10, 120), Box(0, y, 10, y)) == expected

    def test_two_boxes_of_zero_height_overlap_only_at_the_same_y(self) -> None:
        assert vertical_overlap(Box(0, 5, 1, 5), Box(3, 5, 4, 5)) == 1.0
        assert vertical_overlap(Box(0, 5, 1, 5), Box(3, 6, 4, 6)) == 0.0

    def test_horizontal_overlap_is_a_share_of_the_smaller_width(self) -> None:
        assert horizontal_overlap(Box(0, 0, 100, 10), Box(50, 50, 70, 60)) == 1.0
        assert horizontal_overlap(Box(0, 0, 100, 10), Box(90, 0, 110, 10)) == 0.5
        assert horizontal_overlap(Box(0, 0, 100, 10), Box(100, 0, 110, 10)) == 0.0

    def test_an_inverted_span_is_refused(self) -> None:
        with pytest.raises(ValueError, match="span"):
            span_overlap(5, 1, 0, 10)
        with pytest.raises(ValueError, match="span"):
            span_gap(0, 10, 5, 1)

    @given(boxes(), boxes())
    def test_overlap_is_symmetric_and_between_0_and_1(self, a: Box, b: Box) -> None:
        for measure in (vertical_overlap, horizontal_overlap):
            assert 0.0 <= measure(a, b) <= 1.0
            assert measure(a, b) == measure(b, a)


class TestGap:
    def test_the_gap_is_the_distance_between_the_ranges(self) -> None:
        assert gap_x(Box(0, 0, 10, 10), Box(25, 0, 30, 10)) == 15
        assert gap_y(Box(0, 0, 10, 10), Box(0, 40, 10, 50)) == 30

    @pytest.mark.parametrize("other", [Box(5, 5, 20, 20), Box(10, 10, 20, 20)])
    def test_overlapping_or_touching_boxes_have_no_gap(self, other: Box) -> None:
        assert gap_x(Box(0, 0, 10, 10), other) == 0
        assert gap_y(Box(0, 0, 10, 10), other) == 0

    @given(boxes(), boxes())
    def test_a_gap_is_symmetric_and_excludes_overlap(self, a: Box, b: Box) -> None:
        assert gap_x(a, b) == gap_x(b, a) >= 0
        assert gap_y(a, b) == gap_y(b, a) >= 0
        if vertical_overlap(a, b) > 0:
            assert gap_y(a, b) == 0


class TestMedian:
    @pytest.mark.parametrize(
        ("values", "expected"), [([3.0], 3.0), ([5, 1, 3], 3.0), ([4, 1, 3, 2], 2.5)]
    )
    def test_the_middle_value(self, values: list[float], expected: float) -> None:
        assert median(values) == expected

    def test_no_values_have_no_median(self) -> None:
        with pytest.raises(ValueError, match="no values"):
            median([])

    def test_median_height_skips_items_without_boxes(self) -> None:
        words = [Word("a", Box(0, 0, 5, 10)), Word("b"), Word("c", Box(0, 0, 5, 30))]
        assert median_height(words) == 20
        assert median_height([Line(()), Block(())]) == 0.0
        assert median_height([]) == 0.0


class TestCoverage:
    def test_each_interval_between_ends_is_counted(self) -> None:
        assert coverage([(0, 10), (5, 20), (30, 40)]) == (
            (0, 5, 1),
            (5, 10, 2),
            (10, 20, 1),
            (20, 30, 0),
            (30, 40, 1),
        )

    def test_a_span_of_zero_length_covers_nothing(self) -> None:
        assert coverage([(0, 10), (5, 5)]) == ((0, 5, 1), (5, 10, 1))
        assert coverage([(3, 3)]) == ()
        assert coverage([]) == ()

    def test_an_inverted_span_is_refused(self) -> None:
        with pytest.raises(ValueError, match="span"):
            coverage([(10, 0)])


class TestGaps:
    def test_the_holes_between_spans(self) -> None:
        assert gaps([(0, 10), (5, 20), (30, 40), (45, 50)]) == ((20, 30), (40, 45))

    def test_a_gap_narrower_than_min_width_is_dropped(self) -> None:
        assert gaps([(0, 10), (30, 40), (45, 50)], min_width=10) == ((10, 30),)

    def test_max_cover_lets_spans_cross_a_gap(self) -> None:
        spans = [(0, 100), (0, 40), (0, 40), (60, 100), (60, 100)]
        assert gaps(spans) == ()
        assert gaps(spans, max_cover=1) == ((40, 60),)

    def test_a_gap_has_a_span_entirely_on_each_side(self) -> None:
        # The ends of a ragged column are covered by few spans, but nothing lies beyond them.
        spans = [(0, 100), (0, 60), (0, 50)]
        assert gaps(spans, max_cover=1) == ()

    @pytest.mark.parametrize(("min_width", "max_cover"), [(-1.0, 0), (float("nan"), 0), (0, -1)])
    def test_invalid_options_are_refused(self, min_width: float, max_cover: int) -> None:
        with pytest.raises(ValueError, match=r"min_width|max_cover"):
            gaps([(0, 1)], min_width=min_width, max_cover=max_cover)

    @given(st.lists(st.tuples(coordinates, sizes), max_size=12), st.integers(0, 3))
    def test_no_more_spans_than_max_cover_cross_a_gap(
        self, starts: list[tuple[float, float]], max_cover: int
    ) -> None:
        spans = [(start, start + size) for start, size in starts]
        for a, b in gaps(spans, max_cover=max_cover):
            assert a < b
            middle = (a + b) / 2
            assert sum(start < middle < end for start, end in spans) <= max_cover
            assert any(end <= a for _, end in spans)
            assert any(start >= b for start, _ in spans)


def paragraph_lines() -> list[Line]:
    return make_column([f"line{i} with several words on it" for i in range(6)], 100, 200)


class TestSkew:
    @pytest.mark.parametrize("degrees", [-3.0, -1.0, 0.0, 1.0, 1.75, 2.25, 3.0])
    def test_the_angle_of_the_lines(self, degrees: float) -> None:
        lines = [skew_line(line, degrees, (300, 300)) for line in paragraph_lines()]
        assert math.degrees(skew(lines)) == pytest.approx(degrees, abs=1e-9)

    def test_lines_without_word_boxes_give_no_angle(self) -> None:
        lines = [Line.from_text("no word boxes", box=Box(0, 0, 130, 20)), make_line("one", 0, 40)]
        assert skew(lines) == 0.0
        assert skew([]) == 0.0

    def test_one_line_misread_does_not_decide_the_angle(self) -> None:
        lines = [skew_line(line, 1.5, (300, 300)) for line in paragraph_lines()]
        steep = Line((Word("a", Box(0, 0, 10, 20)), Word("b", Box(40, 60, 50, 80))))
        assert math.degrees(skew([*lines, steep])) == pytest.approx(1.5)

    def test_a_line_holding_two_rows_gives_no_slope(self) -> None:
        upper = words_of([make_line("upper row of words", 50, 100)])
        lower = words_of([make_line("lower row", 50, 140)])
        assert skew([Line((*upper, *lower))]) == 0.0

    def test_an_angle_over_ten_degrees_is_not_skew(self) -> None:
        lines = [skew_line(line, 12, (300, 300)) for line in paragraph_lines()]
        assert skew(lines) == 0.0


class TestDeskew:
    @pytest.mark.parametrize("degrees", [-3.0, 1.0, 1.75, 2.25, 3.0])
    def test_turning_back_recovers_the_box(self, degrees: float) -> None:
        box = Box(100, 400, 2100, 435)
        turned = deskew(skew_box(box, degrees, (0, 0)), math.radians(degrees))
        assert [turned.x0, turned.y0, turned.x1, turned.y1] == pytest.approx([100, 400, 2100, 435])

    def test_no_angle_leaves_the_box(self) -> None:
        box = Box(1, 2, 3, 4)
        assert deskew(box, 0.0) is box

    def test_a_size_that_cannot_be_recovered_is_not_negative(self) -> None:
        turned = deskew(Box(0, 0, 100, 1), math.radians(5))
        assert turned.height == 0
