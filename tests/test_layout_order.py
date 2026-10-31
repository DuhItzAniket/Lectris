import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import (
    firsts,
    make_column,
    make_line,
    scale_line,
    scan_column,
    scrambled,
    skew_line,
)
from lectris.layout.order import reading_order, reading_order_indices
from lectris.model import Box, Line


def column(
    label: str, x: float, rows: int, *, y: float = 100, width: float = 400, pitch: float = 30
) -> list[Line]:
    """Justified lines labelled ``label0``, ``label1``... one ``pitch`` apart."""
    texts = [f"{label}{i} aaaa bbbb cccc dddd" for i in range(rows)]
    return make_column(texts, x, y, pitch=pitch, width=width)


def labels(label: str, rows: int) -> list[str]:
    return [f"{label}{i}" for i in range(rows)]


TITLE = make_line("Title across the page", 50, 30, height=30, width=870)


class TestColumns:
    def test_a_single_column_is_read_from_the_top(self) -> None:
        lines = column("a", 50, 8)
        assert firsts(reading_order(scrambled(lines))) == labels("a", 8)

    def test_two_columns_under_a_title(self) -> None:
        lines = [TITLE, *column("l", 50, 6), *column("r", 520, 6)]
        assert firsts(reading_order(scrambled(lines))) == [
            "Title",
            *labels("l", 6),
            *labels("r", 6),
        ]

    def test_two_columns_over_a_footer(self) -> None:
        footer = make_line("Footer across the page", 50, 300, width=870)
        lines = [*column("l", 50, 5), *column("r", 520, 5), footer]
        assert firsts(reading_order(scrambled(lines))) == [
            *labels("l", 5),
            *labels("r", 5),
            "Footer",
        ]

    def test_columns_of_uneven_length_between_a_title_and_a_footer(self) -> None:
        footer = make_line("Footer across the page", 50, 400, width=870)
        lines = [TITLE, *column("l", 50, 9), *column("r", 520, 4), footer]
        expected = ["Title", *labels("l", 9), *labels("r", 4), "Footer"]
        assert firsts(reading_order(scrambled(lines))) == expected

    def test_three_columns(self) -> None:
        lines = [line for c in range(3) for line in column(f"c{c}", 50 + 300 * c, 5, width=250)]
        expected = [*labels("c0", 5), *labels("c1", 5), *labels("c2", 5)]
        assert firsts(reading_order(scrambled(lines))) == expected

    def test_a_title_closer_to_the_columns_than_their_line_spacing(self) -> None:
        # The band under the title (8) is narrower than the bands between rows (10): the title is
        # cut off first because it crosses the gutter, not because its band is the widest.
        title = make_line("Title placed across the gutter", 330, 72)
        lines = [title, *column("l", 50, 4), *column("r", 520, 4)]
        expected = ["Title", *labels("l", 4), *labels("r", 4)]
        assert firsts(reading_order(scrambled(lines))) == expected
        assert firsts(reading_order(lines, max_spanning=0)) != expected

    def test_a_page_number_in_the_gutter_comes_after_the_columns(self) -> None:
        number = make_line("12", 475, 250)
        lines = [number, *column("l", 50, 4), *column("r", 520, 4)]
        assert firsts(reading_order(lines)) == [*labels("l", 4), *labels("r", 4), "12"]

    def test_paragraph_breaks_level_across_columns_do_not_cut_them(self) -> None:
        # Both columns have a blank line at the same height: a band across, but narrower than
        # the gutter.
        left = column("a", 50, 3) + column("b", 50, 3, y=220)
        right = column("c", 520, 3) + column("d", 520, 3, y=220)
        expected = [*labels("a", 3), *labels("b", 3), *labels("c", 3), *labels("d", 3)]
        assert firsts(reading_order(scrambled(left + right))) == expected

    def test_a_section_break_wider_than_the_gutter_ends_a_row_of_columns(self) -> None:
        upper = column("a", 50, 3) + column("b", 520, 3)
        lower = column("c", 50, 3, y=260) + column("d", 520, 3, y=260)
        expected = [*labels("a", 3), *labels("b", 3), *labels("c", 3), *labels("d", 3)]
        assert firsts(reading_order(scrambled(upper + lower))) == expected


class TestHeadersAndRows:
    def test_a_header_with_a_page_number_on_the_right(self) -> None:
        header, number = make_line("Chapter One", 50, 20), make_line("17", 880, 20)
        body = column("b", 50, 5, y=80, width=850)
        expected = ["Chapter", "17", *labels("b", 5)]
        assert firsts(reading_order(scrambled([*body, number, header]))) == expected

    def test_a_header_set_well_apart_from_two_columns_is_read_first(self) -> None:
        header, number = make_line("Running head", 50, 0), make_line("7", 910, 0)
        lines = [number, header, *column("l", 50, 4), *column("r", 520, 4)]
        expected = ["Running", "7", *labels("l", 4), *labels("r", 4)]
        assert firsts(reading_order(lines)) == expected

    def test_lines_that_touch_are_read_from_the_top(self) -> None:
        lines = column("a", 50, 6, pitch=20)
        assert firsts(reading_order(scrambled(lines))) == labels("a", 6)

    def test_lines_that_overlap_a_little_are_read_from_the_top(self) -> None:
        # Ascenders and descenders: each line reaches 3 into the next.
        left, right = column("l", 50, 5, pitch=17), column("r", 520, 5, pitch=17)
        expected = [*labels("l", 5), *labels("r", 5)]
        assert firsts(reading_order(scrambled(left + right))) == expected

    def test_trim_finds_the_band_under_a_title_that_touches_the_columns(self) -> None:
        title = make_line("Title placed across the gutter", 330, 82)
        lines = [title, *column("l", 50, 4), *column("r", 520, 4)]
        expected = ["Title", *labels("l", 4), *labels("r", 4)]
        assert firsts(reading_order(lines)) == expected
        assert firsts(reading_order(lines, trim=0)) != expected

    def test_a_row_is_read_from_the_left_even_if_its_right_part_starts_higher(self) -> None:
        left = Line.from_text("left part", box=Box(50, 100, 140, 120))
        right = Line.from_text("right part", box=Box(150, 96, 250, 122))
        assert firsts(reading_order([right, left])) == ["left", "right"]

    def test_min_gap_sets_the_narrowest_gutter(self) -> None:
        lines = column("l", 50, 3) + column("r", 520, 3)
        assert firsts(reading_order(lines)) == ["l0", "l1", "l2", "r0", "r1", "r2"]
        assert firsts(reading_order(lines, min_gap=5)) == ["l0", "r0", "l1", "r1", "l2", "r2"]


DEGREES = [1.0, 1.75, 2.25, 3.0, -2.25]


def numbered(label: str, rows: int) -> list[str]:
    return [f"{label}{i:02d}" for i in range(rows)]


class TestSkew:
    @pytest.mark.parametrize("deskew", [True, False])
    @pytest.mark.parametrize("degrees", DEGREES)
    def test_a_skewed_single_column_is_read_from_the_top(
        self, degrees: float, deskew: bool
    ) -> None:
        # Lines 2000 wide: their boxes are two to five times as tall as the type, and each
        # overlaps the next by more than half its height.
        page = scan_column("L", 100, 200, 25, width=2000, words=20)
        lines = [skew_line(line, degrees, (1100, 800)) for line in page]
        assert firsts(reading_order(scrambled(lines), deskew=deskew)) == numbered("L", 25)

    @pytest.mark.parametrize("degrees", DEGREES)
    def test_a_skewed_two_column_page_under_a_title(self, degrees: float) -> None:
        title = make_line("A Title Across Both Columns", 600, 80, height=50, char_width=30)
        left = scan_column("A", 100, 200, 50, width=950, words=8)
        right = scan_column("B", 1150, 200, 50, width=950, words=8)
        lines = [skew_line(line, degrees, (1100, 1300)) for line in [title, *left, *right]]
        expected = ["A", *numbered("A", 50), *numbered("B", 50)]
        assert firsts(reading_order(scrambled(lines))) == expected

    def test_without_deskew_a_skewed_gutter_closes(self) -> None:
        # Over 2250 of height, 3 degrees move the columns 118 sideways: more than the gutter.
        left = scan_column("A", 100, 200, 50, width=950, words=8)
        right = scan_column("B", 1150, 200, 50, width=950, words=8)
        lines = [skew_line(line, 3, (1100, 1300)) for line in [*left, *right]]
        expected = [*numbered("A", 50), *numbered("B", 50)]
        assert firsts(reading_order(lines)) == expected
        assert firsts(reading_order(lines, deskew=False)) != expected

    def test_stacked_lines_whose_boxes_overlap_are_read_by_their_middle(self) -> None:
        # The lower line starts further left, as on a page turned clockwise: a row of the two,
        # read from the left, would put it first.
        upper = Line.from_text("upper", box=Box(52, 100, 900, 160))
        lower = Line.from_text("lower", box=Box(50, 130, 898, 190))
        assert firsts(reading_order([lower, upper])) == ["upper", "lower"]


class TestWithoutBoxes:
    def test_lines_without_boxes_keep_the_input_order(self) -> None:
        lines = [Line.from_text("second"), Line.from_text("first")]
        assert reading_order(lines) == tuple(lines)

    def test_one_line_without_a_box_keeps_the_input_order_of_all(self) -> None:
        lines = [*scrambled(column("a", 50, 4)), Line.from_text("loose")]
        assert reading_order(lines) == tuple(lines)

    def test_no_lines_and_one_line(self) -> None:
        line = make_line("only", 0, 0)
        assert reading_order([]) == ()
        assert reading_order([line]) == (line,)


class TestValues:
    def test_the_lines_themselves_are_returned_and_the_input_is_unchanged(self) -> None:
        lines = scrambled([TITLE, *column("l", 50, 3), *column("r", 520, 3)])
        before = list(lines)
        ordered = reading_order(lines)
        assert lines == before
        assert sorted(map(id, ordered)) == sorted(map(id, lines))

    @pytest.mark.parametrize(
        ("min_gap", "max_spanning", "trim"),
        [(-1.0, 0.25, 0.25), (1.0, 1.0, 0.25), (1.0, -0.5, 0.25), (1.0, 0.25, 0.5)],
    )
    def test_invalid_options_are_refused(
        self, min_gap: float, max_spanning: float, trim: float
    ) -> None:
        with pytest.raises(ValueError, match=r"min_gap|max_spanning|trim"):
            reading_order([], min_gap=min_gap, max_spanning=max_spanning, trim=trim)


def template() -> list[Line]:
    """A header with a page number, a title, uneven columns and a footer."""
    header, number = make_line("Running head", 50, 0), make_line("7", 910, 0)
    footer = make_line("Footer across the page", 50, 420, width=870)
    return [header, number, TITLE, *column("l", 50, 9), *column("r", 520, 5), footer]


@st.composite
def random_lines(draw: st.DrawFn) -> list[Line]:
    count = draw(st.integers(0, 25))
    lines = []
    for i in range(count):
        x, y = draw(st.integers(0, 900)), draw(st.integers(0, 1200))
        width, height = draw(st.integers(0, 500)), draw(st.integers(0, 40))
        lines.append(Line.from_text(f"n{i}", box=Box(x, y, x + width, y + height)))
    return lines


class TestProperties:
    @given(random_lines())
    def test_the_order_is_a_permutation_and_does_not_change_when_repeated(
        self, lines: list[Line]
    ) -> None:
        ordered = reading_order(lines)
        assert sorted(map(id, ordered)) == sorted(map(id, lines))
        assert reading_order(ordered) == ordered

    @given(random_lines())
    def test_the_indices_give_the_order(self, lines: list[Line]) -> None:
        indices = reading_order_indices(lines)
        assert sorted(indices) == list(range(len(lines)))
        assert tuple(lines[i] for i in indices) == reading_order(lines)

    @given(st.floats(min_value=0.05, max_value=50))
    def test_a_page_at_any_resolution_is_read_in_the_same_order(self, factor: float) -> None:
        lines = scrambled(template())
        scaled = [scale_line(line, factor) for line in lines]
        assert firsts(reading_order(scaled)) == firsts(reading_order(lines))

    def test_the_template_page_is_read_in_order(self) -> None:
        expected = ["Running", "7", "Title", *labels("l", 9), *labels("r", 5), "Footer"]
        assert firsts(reading_order(scrambled(template()))) == expected

    def test_a_scan_at_twice_the_resolution(self) -> None:
        lines = scrambled(template())
        doubled = [scale_line(line, 2) for line in lines]
        assert firsts(reading_order(doubled)) == firsts(reading_order(lines))
