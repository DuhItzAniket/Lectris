from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import (
    block_texts,
    make_line,
    make_paragraph,
    scale_line,
    scan_column,
    scrambled,
    skew_line,
    texts,
    words_of,
)
from lectris.io import read
from lectris.layout import arrange, arrange_document
from lectris.model import Block, Box, Document, Line, Page, Word, union_of

TITLE = make_line("Notes on the reading of old scans", 50, 30, height=30, width=870)
LEFT_FIRST = [
    "The left column opens with a first",
    "paragraph that runs over three lines",
    "and ends without a stop",
]
LEFT_SECOND = ["A second paragraph follows it and", "ends the column."]
RIGHT = ["The right column holds one more", "paragraph of three lines that ends", "the page."]


def two_column_lines() -> list[Line]:
    return [
        TITLE,
        *make_paragraph(LEFT_FIRST, y=100, indent=40),
        *make_paragraph(LEFT_SECOND, y=190, indent=40),
        *make_paragraph(RIGHT, x=520, y=100, indent=40),
    ]


def two_column_page(lines: list[Line] | None = None) -> Page:
    """The page as a reader might give it: every line in one block, out of order."""
    lines = scrambled(two_column_lines()) if lines is None else lines
    return Page((Block(tuple(lines)),), width=1000, height=1400, number=4)


EXPECTED = [[TITLE.text], LEFT_FIRST, LEFT_SECOND, RIGHT]


class TestArrange:
    def test_a_two_column_page_is_put_in_order_and_paragraphs(self) -> None:
        assert block_texts(arrange(two_column_page()).blocks) == EXPECTED

    def test_the_page_keeps_its_size_and_number(self) -> None:
        page = arrange(two_column_page())
        assert (page.width, page.height, page.number) == (1000, 1400, 4)

    def test_the_blocks_the_input_gave_are_split_into_paragraphs(self) -> None:
        lines = two_column_lines()
        page = Page((Block(tuple(lines[:4])), Block(tuple(lines[4:]))))
        assert block_texts(arrange(page).blocks) == EXPECTED

    def test_the_text_reads_in_order(self) -> None:
        text = arrange(two_column_page()).text
        assert text.startswith(TITLE.text + "\n\nThe left column")
        assert text.endswith(
            "ends the column.\n\nThe right column holds one more\n" + RIGHT[1] + "\nthe page."
        )

    def test_a_page_with_a_line_without_a_box_is_returned_as_it_is(self) -> None:
        page = Page((Block((Line.from_text("from a plain text file"),)), Block((TITLE,))))
        assert arrange(page) is page

    def test_a_page_without_lines_is_returned_as_it_is(self) -> None:
        page = Page((), width=10, height=10)
        assert arrange(page) is page

    def test_options_are_passed_on(self) -> None:
        page = two_column_page()
        # Paragraphs: the first two are told apart by their indent only, of two line heights.
        assert len(arrange(page, indent=5).blocks) == 3
        # Order: a gutter must be ten line heights wide, so the columns are read row by row.
        interleaved = arrange(page, min_gap=10)
        assert interleaved.lines[1].text == LEFT_FIRST[0]
        assert interleaved.lines[2].text == RIGHT[0]

    @given(st.floats(min_value=0.05, max_value=50))
    def test_a_page_at_any_resolution_is_arranged_the_same(self, factor: float) -> None:
        lines = [scale_line(line, factor) for line in scrambled(two_column_lines())]
        assert block_texts(arrange(two_column_page(lines)).blocks) == EXPECTED


class TestInputBlocks:
    def test_lines_from_two_input_blocks_are_never_merged(self) -> None:
        lines = make_paragraph(LEFT_SECOND + LEFT_SECOND)
        assert len(arrange(Page((Block(tuple(lines)),))).blocks) == 1
        page = Page((Block(tuple(lines[:2])), Block(tuple(lines[2:]))))
        assert block_texts(arrange(page).blocks) == [LEFT_SECOND, LEFT_SECOND]

    def test_a_heading_block_is_not_merged_into_the_text_under_it(self) -> None:
        # The geometry of tests/data/io/alto_v4.xml: a heading, two lines of text, a page number.
        heading = Line.from_text("Field Notes", box=Box(800, 100, 1300, 160))
        body = (
            Line.from_text("Hedgerows shelter wrens and spar-", box=Box(200, 300, 1470, 370)),
            Line.from_text("rows in the colder months.", box=Box(200, 410, 1900, 480)),
        )
        number = Line.from_text("3", box=Box(1030, 2850, 1070, 2900))
        page = Page((Block((heading,)), Block(body), Block((number,))))
        assert [len(block.lines) for block in arrange(page).blocks] == [1, 2, 1]

    def test_the_alto_sample_keeps_its_heading_apart(self) -> None:
        sample = Path(__file__).parent / "data" / "io" / "alto_v4.xml"
        if not sample.exists():
            pytest.skip("the ALTO sample is not in this checkout")
        page = read(sample).pages[0]
        arranged = arrange(page)
        assert [block.text for block in arranged.blocks] == [block.text for block in page.blocks]
        assert arranged.blocks[0].text == "Field Notes"


def two_rows_in_one_line() -> Line:
    """One line holding the words of two visual lines, as hOCR gives words outside any line."""
    first = [Word("First", Box(50, 100, 100, 120)), Word("line.", Box(600, 100, 650, 120))]
    second = words_of([make_line("Second line.", 50, 140)])
    words = (*first, *second)
    return Line(words, box=union_of(word.box for word in words), confidence=0.9)


class TestVisualLines:
    def test_a_line_on_two_visual_lines_is_split(self) -> None:
        arranged = arrange(Page((Block((two_rows_in_one_line(),)),)))
        assert texts(arranged.lines) == ["First line.", "Second line."]
        assert [line.confidence for line in arranged.lines] == [None, None]

    def test_a_wide_gap_inside_a_line_does_not_split_it(self) -> None:
        words = (Word("Chapter", Box(50, 100, 120, 120)), Word("12", Box(900, 100, 920, 120)))
        line = Line(words, box=Box(50, 100, 920, 120), confidence=0.8)
        assert arrange(Page((Block((line,)),))).lines == (line,)

    def test_a_line_without_a_box_takes_its_words_union(self) -> None:
        words = tuple(words_of([make_line("boxed words only", 50, 100)]))
        arranged = arrange(Page((Block((Line(words, confidence=0.7),)),)))
        (line,) = arranged.lines
        assert line.box == Box(50, 100, 210, 120)
        assert (line.words, line.confidence) == (words, 0.7)

    def test_a_line_with_a_word_without_a_box_is_kept(self) -> None:
        words = (*two_rows_in_one_line().words, Word("unboxed"))
        line = Line(words, box=Box(50, 100, 650, 160))
        assert arrange(Page((Block((line,)),))).lines == (line,)

    def test_the_input_page_is_not_changed(self) -> None:
        page = Page((Block((two_rows_in_one_line(),)),))
        before = page.lines[0]
        arrange(page)
        assert page.lines[0] is before
        assert len(before.words) == 4


class TestSkew:
    @pytest.mark.parametrize("degrees", [-2.25, 1.0, 1.75, 2.25, 3.0])
    def test_a_skewed_two_column_page(self, degrees: float) -> None:
        title = make_line("A Title Across Both Columns", 600, 80, height=50, char_width=30)
        left = scan_column("A", 100, 200, 40, width=950, words=8)
        right = scan_column("B", 1150, 200, 40, width=950, words=8)
        lines = [skew_line(line, degrees, (1100, 1100)) for line in [title, *left, *right]]
        page = Page((Block(tuple(scrambled(lines))),))
        arranged = arrange(page)
        assert [line.words[0].text for line in arranged.lines] == [
            "A",
            *(f"A{i:02d}" for i in range(40)),
            *(f"B{i:02d}" for i in range(40)),
        ]
        assert [len(block.lines) for block in arranged.blocks] == [1, 40, 40]


def sparse_line(label: str, y: float, words: int) -> Line:
    """A line of ``words`` words spread over 2000, type 35 high: few, widely spaced words."""
    step = 2000 / words
    boxes = [Box(300 + i * step, y, 300 + (i + 0.8) * step, y + 35) for i in range(words)]
    parts = tuple(Word(f"{label}w{i}", box) for i, box in enumerate(boxes))
    return Line(parts, box=union_of(boxes))


class TestSkewedLinesStayWhole:
    @pytest.mark.parametrize("degrees", [1.0, 1.5, 2.25, 3.0, -2.25])
    def test_lines_of_three_wide_words(self, degrees: float) -> None:
        # Between two words 667 apart, a line skewed by 1.5 degrees climbs 17: half a word's
        # height. The visual lines are found on the boxes turned back.
        straight = [sparse_line(f"L{i:02d}", 300 + 45 * i, 3) for i in range(6)]
        lines = [skew_line(line, degrees, (1275, 1650)) for line in straight]
        arranged = arrange(Page((Block(tuple(lines)),)))
        assert arranged.lines == tuple(lines)
        assert texts(arranged.lines) == texts(straight)

    @pytest.mark.parametrize("pitch", [45, 54])
    @pytest.mark.parametrize("degrees", [1.75, 2.25])
    def test_thirty_lines_of_eight_words(self, degrees: float, pitch: float) -> None:
        straight = [sparse_line(f"L{i:02d}", 300 + pitch * i, 8) for i in range(30)]
        lines = [skew_line(line, degrees, (1275, 1650)) for line in straight]
        assert arrange(Page((Block(tuple(scrambled(lines))),))).lines == tuple(lines)

    def test_a_line_on_two_visual_lines_of_a_skewed_page_is_split(self) -> None:
        straight = [sparse_line(f"L{i:02d}", 300 + 45 * i, 8) for i in range(6)]
        lines = [skew_line(line, 2.25, (1275, 1650)) for line in straight]
        words = lines[2].words + lines[3].words
        merged = Line(words, box=union_of(word.box for word in words))
        page = Page((Block((*lines[:2], merged, *lines[4:])),))
        arranged = arrange(page)
        assert [line.words for line in arranged.lines] == [line.words for line in lines]
        assert all(
            a is b
            for line, original in zip(arranged.lines, lines, strict=True)
            for a, b in zip(line.words, original.words, strict=True)
        )


class TestArrangeDocument:
    def test_each_page_is_arranged(self) -> None:
        plain = Page((Block((Line.from_text("plain text"),)),), number=2)
        document = arrange_document(Document((two_column_page(), plain)))
        assert block_texts(document.pages[0].blocks) == EXPECTED
        assert document.pages[1] is plain

    def test_options_are_passed_on_to_each_page(self) -> None:
        document = arrange_document(Document((two_column_page(), two_column_page())), indent=5)
        assert [len(page.blocks) for page in document.pages] == [3, 3]

    def test_an_empty_document(self) -> None:
        assert arrange_document(Document(())) == Document(())
