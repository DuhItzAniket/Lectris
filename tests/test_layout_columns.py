import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import make_column, make_line, scale_line
from lectris.layout.columns import assign, detect
from lectris.model import Box, Line


def column(label: str, x: float, rows: int, *, width: float = 400) -> list[Line]:
    """Justified lines of five words, one ``PITCH`` apart from ``y = 100``."""
    return make_column(
        [f"{label}{i} aaaa bbbb cccc dddd" for i in range(rows)], x, 100, width=width
    )


TITLE = make_line("A title across both columns", 50, 40, height=30, width=870)
FOOTER = make_line("A footer across both columns", 50, 400, width=870)


class TestDetect:
    def test_a_single_column_spans_its_lines(self) -> None:
        lines = [*column("a", 50, 5), make_line("short last line", 50, 250)]
        assert detect(lines) == ((50, 450),)

    def test_two_columns(self) -> None:
        lines = column("l", 50, 6) + column("r", 520, 6)
        assert detect(lines) == ((50, 450), (520, 920))

    def test_three_columns(self) -> None:
        lines = [line for c in range(3) for line in column(f"c{c}", 50 + 300 * c, 5, width=250)]
        assert detect(lines) == ((50, 300), (350, 600), (650, 900))

    def test_a_title_and_a_footer_across_the_gutter_leave_it_open(self) -> None:
        lines = [TITLE, *column("l", 50, 6), *column("r", 520, 6), FOOTER]
        assert detect(lines) == ((50, 450), (520, 920))

    def test_columns_of_uneven_length(self) -> None:
        lines = [TITLE, *column("l", 50, 9), *column("r", 520, 3)]
        assert detect(lines) == ((50, 450), (520, 920))

    def test_a_page_number_in_the_gutter_belongs_to_no_column(self) -> None:
        number = make_line("12", 475, 400)
        lines = [*column("l", 50, 6), *column("r", 520, 6), number]
        columns = detect(lines)
        assert assign([number], columns) == (-1,)
        assert columns == ((50, 450), (520, 920))

    def test_max_spanning_sets_how_many_lines_may_cross_a_gutter(self) -> None:
        lines = [TITLE, *column("l", 50, 3), *column("r", 520, 3), FOOTER]
        assert detect(lines) == ((50, 450), (520, 920))
        assert detect(lines, max_spanning=0) == ((50, 920),)
        assert detect(lines, max_spanning=0.2) == ((50, 920),)

    def test_a_gap_narrower_than_min_gap_is_not_a_gutter(self) -> None:
        # The gap is 15, three quarters of a line's height.
        lines = column("l", 50, 4) + column("r", 465, 4)
        assert detect(lines) == ((50, 865),)
        assert detect(lines, min_gap=0.5) == ((50, 450), (465, 865))

    def test_lines_without_boxes_are_ignored(self) -> None:
        lines = [Line.from_text("no box"), *column("l", 50, 3), *column("r", 520, 3)]
        assert detect(lines) == ((50, 450), (520, 920))
        assert detect([Line.from_text("no box")]) == ()
        assert detect([]) == ()

    @pytest.mark.parametrize(
        ("min_gap", "max_spanning"), [(-1.0, 0.25), (float("nan"), 0.25), (1.0, 1.0), (1.0, -0.1)]
    )
    def test_invalid_options_are_refused(self, min_gap: float, max_spanning: float) -> None:
        with pytest.raises(ValueError, match=r"min_gap|max_spanning"):
            detect([], min_gap=min_gap, max_spanning=max_spanning)

    @given(st.floats(min_value=0.05, max_value=50))
    def test_the_columns_scale_with_the_page(self, factor: float) -> None:
        lines = [TITLE, *column("l", 50, 6), *column("r", 520, 4), FOOTER]
        found = detect([scale_line(line, factor) for line in lines])
        assert len(found) == 2
        assert [x for span in found for x in span] == pytest.approx(
            [50 * factor, 450 * factor, 520 * factor, 920 * factor]
        )


class TestAssign:
    def test_each_line_gets_its_column(self) -> None:
        lines = [TITLE, *column("l", 50, 4), *column("r", 520, 4), FOOTER]
        assert assign(lines, detect(lines)) == (-1, 0, 0, 0, 0, 1, 1, 1, 1, -1)

    def test_a_line_without_a_box_or_between_columns_gets_minus_one(self) -> None:
        columns = ((0.0, 100.0), (200.0, 300.0))
        between = Line.from_text("gap", box=Box(120, 0, 180, 20))
        assert assign([Line.from_text("no box"), between], columns) == (-1, -1)

    def test_a_line_of_zero_width_inside_a_column(self) -> None:
        line = Line.from_text("|", box=Box(250, 0, 250, 20))
        assert assign([line], ((0.0, 100.0), (200.0, 300.0))) == (1,)

    def test_no_columns(self) -> None:
        assert assign(column("a", 50, 2), ()) == (-1, -1)
