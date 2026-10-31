import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import block_texts, make_line, make_paragraph, scale_line, skew_line
from lectris.layout.paragraphs import group
from lectris.model import Box, Line, union_of


def stack(*paragraphs: list[str], indent: float = 0, x: float = 50) -> list[Line]:
    """Paragraphs one under the other, with no space between them."""
    lines: list[Line] = []
    for rows in paragraphs:
        lines += make_paragraph(rows, x=x, y=100 + 30 * len(lines), indent=indent)
    return lines


FIRST = ["The first paragraph runs over three", "lines of text and comes to its", "end here."]
SECOND = ["Then a second paragraph starts and", "goes on for two lines."]


class TestOneBlock:
    def test_a_paragraph_is_one_block_with_the_union_of_its_boxes(self) -> None:
        lines = make_paragraph(FIRST)
        (block,) = group(lines)
        assert block.lines == tuple(lines)
        assert block.box == union_of(line.box for line in lines)

    def test_lines_set_solid_stay_one_make_paragraph(self) -> None:
        rows = ["Lines set solid touch each other", "and they still belong to one", "paragraph."]
        assert len(group(make_paragraph(rows, pitch=20))) == 1

    def test_no_lines(self) -> None:
        assert group([]) == ()


class TestVerticalGap:
    def test_a_blank_line_starts_a_make_paragraph(self) -> None:
        first = make_paragraph(["The first paragraph has two lines", "and no final stop"])
        second = make_paragraph(["the second one follows after a", "blank line"], y=190)
        assert block_texts(group(first + second)) == [
            ["The first paragraph has two lines", "and no final stop"],
            ["the second one follows after a", "blank line"],
        ]

    def test_spacing_sets_how_large_a_gap_breaks(self) -> None:
        first = make_paragraph(["The first paragraph has two lines", "and no final stop"])
        second = make_paragraph(["the second one follows after a", "blank line"], y=190)
        assert len(group(first + second, spacing=3)) == 1

    def test_a_heading_in_larger_type_is_its_own_block(self) -> None:
        heading = make_line("Heading", 50, 60, height=40, char_width=20)
        rows = ["Body text follows the heading and", "goes on for a few lines of text"]
        body = make_paragraph([*rows, "until it reaches its very end", "here."], y=110)
        blocks = group([heading, *body])
        assert block_texts(blocks)[0] == ["Heading"]
        assert len(blocks) == 2


class TestIndents:
    def test_an_indented_first_line_starts_a_make_paragraph(self) -> None:
        lines = stack(FIRST, SECOND, indent=40)
        assert block_texts(group(lines)) == [FIRST, SECOND]

    def test_indent_sets_how_far_in_a_first_line_must_start(self) -> None:
        rows = ["A paragraph that ends without its", "final stop"]
        lines = stack(rows, ["Another indented paragraph that is", "long enough"], indent=40)
        assert len(group(lines)) == 2
        assert len(group(lines, indent=2.5)) == 1

    def test_a_block_quote_is_its_own_block(self) -> None:
        body = make_paragraph(
            ["The text quotes a passage set in", "from both sides below and then"]
        )
        quote = make_paragraph(
            ["a quoted passage of two lines that", "has no final stop"], x=90, y=160, width=320
        )
        after = make_paragraph(["the text goes on after the quote", "to its end."], y=220)
        assert block_texts(group(body + quote + after)) == [
            ["The text quotes a passage set in", "from both sides below and then"],
            ["a quoted passage of two lines that", "has no final stop"],
            ["the text goes on after the quote", "to its end."],
        ]

    def test_a_first_line_further_left_does_not_split_a_make_paragraph(self) -> None:
        # Indent on the first line only: the second line is to its left, not an outdent.
        lines = make_paragraph(FIRST, indent=40)
        assert len(group(lines)) == 1


class TestLists:
    def test_bullets_start_items(self) -> None:
        lines = [
            make_line("• First item", 50, 100),
            make_line("• Second item", 50, 130),
            make_line("• Third item", 50, 160),
        ]
        assert block_texts(group(lines)) == [["• First item"], ["• Second item"], ["• Third item"]]

    def test_items_with_hanging_indents(self) -> None:
        lines = [
            make_line("1. The first item is long enough to", 50, 100, width=400),
            make_line("wrap onto a second line.", 80, 130),
            make_line("2. The second item also wraps over", 50, 160, width=400),
            make_line("two lines", 80, 190),
            make_line("3. And a short third one", 50, 220),
        ]
        assert block_texts(group(lines)) == [
            ["1. The first item is long enough to", "wrap onto a second line."],
            ["2. The second item also wraps over", "two lines"],
            ["3. And a short third one"],
        ]

    def test_short_enumerated_items_in_a_column_of_text(self) -> None:
        body = make_paragraph(["The list below names the fruit and", "ends this paragraph:"])
        rows = ["a) apples", "b) pears", "(c) plums", "iv. figs"]
        items = [make_line(row, 50, 160 + 30 * i) for i, row in enumerate(rows)]
        assert block_texts(group(body + items))[1:] == [[row] for row in rows]

    def test_short_enumerated_items_alone_give_no_column_width(self) -> None:
        # Every line is as short as the column: nothing shows that a line ended early.
        rows = ["a) apples", "b) pears", "(c) plums"]
        lines = [make_line(row, 50, 100 + 30 * i) for i, row in enumerate(rows)]
        assert len(group(lines)) == 1

    def test_a_number_starting_a_line_after_a_full_one_is_not_an_item(self) -> None:
        lines = make_paragraph(["The figure was published in volume", "2. It shows the results."])
        assert len(group(lines)) == 1


class TestSentenceEnds:
    def test_a_short_line_ending_a_sentence_before_a_capital_ends_a_make_paragraph(self) -> None:
        first = ["Block paragraphs have no indent and", "end with a short line."]
        second = ["Next starts with a capital and", "continues."]
        assert block_texts(group(stack(first, second))) == [first, second]

    def test_closing_and_opening_quotes_around_the_break(self) -> None:
        first = ["He looked up and said it once more", "to her: “It is late.”"]
        second = ["“Yes,” she said, and that was all", "there was."]
        assert block_texts(group(stack(first, second))) == [first, second]

    def test_a_line_left_short_because_the_next_word_did_not_fit(self) -> None:
        lines = [
            make_line("The line ends with a sentence.", 50, 100),
            make_line("Extraordinarily long words follow it.", 50, 130),
            make_line("The end of it", 50, 160),
        ]
        assert len(group(lines)) == 1

    @pytest.mark.parametrize(
        ("end", "start"),
        [("like etc.", "and the text goes on here"), ("a pause,", "Then more of the text")],
    )
    def test_no_sentence_end_or_no_capital_keeps_the_make_paragraph(
        self, end: str, start: str
    ) -> None:
        lines = stack(["A line ends with an abbreviation", end], [start, "to the end"])
        assert len(group(lines)) == 1


class TestColumnsAndBoxes:
    def test_a_change_of_column_starts_a_block(self) -> None:
        left = make_paragraph(["left column text goes on and on", "and it wraps"])
        right = make_paragraph(["right column text continues the", "sentence"], x=520)
        assert block_texts(group(left + right)) == [
            ["left column text goes on and on", "and it wraps"],
            ["right column text continues the", "sentence"],
        ]

    def test_min_overlap_sets_what_counts_as_the_same_column(self) -> None:
        upper = make_line("a line that is set further right", 250, 100)
        lower = make_line("a line on the left side of a page", 50, 130)
        assert len(group([upper, lower])) == 2
        assert len(group([upper, lower], min_overlap=0.2)) == 1

    def test_lines_without_boxes_form_one_block_per_run(self) -> None:
        loose = [Line.from_text("no box"), Line.from_text("none here")]
        boxed = make_paragraph(FIRST)
        blocks = group([*loose, *boxed, Line.from_text("last")])
        assert block_texts(blocks) == [["no box", "none here"], FIRST, ["last"]]
        assert blocks[0].box is None

    def test_only_lines_without_boxes_are_one_block(self) -> None:
        lines = [Line.from_text("one."), Line.from_text("Two.")]
        assert block_texts(group(lines)) == [["one.", "Two."]]

    @pytest.mark.parametrize(
        ("spacing", "min_overlap", "indent"),
        [(0.0, 0.5, 0.5), (float("inf"), 0.5, 0.5), (1.5, 1.5, 0.5), (1.5, 0.5, -1.0)],
    )
    def test_invalid_options_are_refused(
        self, spacing: float, min_overlap: float, indent: float
    ) -> None:
        with pytest.raises(ValueError, match=r"spacing|min_overlap|indent"):
            group([], spacing=spacing, min_overlap=min_overlap, indent=indent)


class TestSources:
    def test_lines_from_different_sources_are_never_merged(self) -> None:
        lines = make_paragraph(FIRST)
        assert len(group(lines)) == 1
        assert block_texts(group(lines, sources=[0, 0, 1])) == [FIRST[:2], FIRST[2:]]

    def test_a_source_can_hold_several_paragraphs(self) -> None:
        lines = stack(FIRST, SECOND, indent=40)
        assert block_texts(group(lines, sources=[7] * len(lines))) == [FIRST, SECOND]

    def test_one_number_per_line(self) -> None:
        with pytest.raises(ValueError, match="sources"):
            group(make_paragraph(FIRST), sources=[0, 0])


class TestLineSpacing:
    def test_a_short_page_of_a_heading_two_lines_and_a_footer(self) -> None:
        # The distances are 210 (heading), 110 (between the lines) and 2440 (footer): their
        # median is the heading's, but the line spacing is the smallest.
        heading = Line.from_text("Field Notes", box=Box(800, 100, 1300, 160))
        body = [
            Line.from_text("Hedgerows shelter wrens and spar-", box=Box(200, 300, 1470, 370)),
            Line.from_text("rows in the colder months.", box=Box(200, 410, 1900, 480)),
        ]
        footer = Line.from_text("3", box=Box(1030, 2850, 1070, 2900))
        assert [len(block.lines) for block in group([heading, *body, footer])] == [1, 2, 1]

    def test_paragraph_gaps_do_not_raise_the_line_spacing(self) -> None:
        # Five one-line paragraphs, each followed by a blank line, and one of four lines: most
        # distances are gaps, yet each gap is still seen.
        rows = ["a paragraph of one line and no stop"] * 5
        lines = [make_line(row, 50, 100 + 60 * i) for i, row in enumerate(rows)]
        lines += make_paragraph(["the last one is longer and runs"] * 3 + ["on"], y=400)
        assert [len(block.lines) for block in group(lines)] == [1, 1, 1, 1, 1, 4]


SCAN_ROWS = [
    "The first paragraph of the scanned page begins with an indented line of text set in a",
    "book face, and it goes on for a few more lines of the same length, all of them",
    "justified to the right edge, until it comes to its end on a short line.",
    "A second paragraph begins with an indent of its own and runs over two whole lines of",
    "text, then stops.",
]


def scan_page() -> list[Line]:
    """Two indented paragraphs and a block quote, with the type and the size of a 300 dpi scan."""
    size = {"pitch": 45, "height": 35, "char_width": 20, "width": 2000}
    first = make_paragraph(SCAN_ROWS[:3], x=100, y=200, indent=70, **size)
    second = make_paragraph(SCAN_ROWS[3:], x=100, y=335, indent=70, **size)
    quote_rows = ["a quoted passage set in from both sides runs over two lines of", "text"]
    quote = make_paragraph(quote_rows, x=250, y=425, pitch=45, height=35, char_width=20, width=1700)
    return [*first, *second, *quote]


class TestSkew:
    @pytest.mark.parametrize("degrees", [-2.25, 1.0, 1.75, 2.25, 3.0])
    def test_a_skewed_page_gives_the_same_paragraphs(self, degrees: float) -> None:
        lines = scan_page()
        skewed = [skew_line(line, degrees, (1100, 300)) for line in lines]
        assert block_texts(group(skewed)) == block_texts(group(lines))
        assert [len(block.lines) for block in group(skewed)] == [3, 2, 2]

    def test_without_deskew_a_short_line_of_a_skewed_page_seems_set_apart(self) -> None:
        # Turned by 3 degrees, a full line's box is 136 high and the short line's under it 53:
        # their tops are further apart than the lines are.
        skewed = [skew_line(line, 3, (1100, 300)) for line in scan_page()]
        assert [len(block.lines) for block in group(skewed, deskew=False)] == [3, 1, 1, 2]


def template() -> list[Line]:
    """A heading, indented paragraphs, a block quote and a list, in reading order."""
    heading = make_line("Heading", 50, 40, height=40, char_width=20)
    body = stack(FIRST, SECOND, indent=40)
    quote = make_paragraph(["a quoted passage of two lines that", "has no final stop"], x=90, y=280)
    after = make_paragraph(["the text goes on after the quote", "to its end."], y=340)
    items = [make_line("• an item", 50, 400), make_line("• another", 50, 430)]
    return [heading, *body, *quote, *after, *items]


@st.composite
def lines_in_any_order(draw: st.DrawFn) -> list[Line]:
    lines = []
    for i in range(draw(st.integers(0, 20))):
        if draw(st.integers(0, 5)) == 0:
            lines.append(Line.from_text(f"loose {i}."))
            continue
        x, y = draw(st.integers(0, 600)), draw(st.integers(0, 900))
        width, height = draw(st.integers(0, 400)), draw(st.integers(0, 30))
        text = draw(st.sampled_from(["Word.", "word", "• item", "2. item", "End:", "x"]))
        lines.append(Line.from_text(text, box=Box(x, y, x + width, y + height)))
    return lines


class TestProperties:
    def test_the_template_page(self) -> None:
        assert [len(block.lines) for block in group(template())] == [1, 3, 2, 2, 2, 1, 1]

    @given(lines_in_any_order())
    def test_blocks_hold_the_lines_in_order(self, lines: list[Line]) -> None:
        blocks = group(lines)
        assert [line for block in blocks for line in block.lines] == lines
        assert all(block.lines for block in blocks)
        for block in blocks:
            assert block.box == union_of(line.box for line in block.lines)

    @given(st.floats(min_value=0.05, max_value=50))
    def test_a_page_at_any_resolution_gives_the_same_blocks(self, factor: float) -> None:
        lines = template()
        scaled = group([scale_line(line, factor) for line in lines])
        assert block_texts(scaled) == block_texts(group(lines))
