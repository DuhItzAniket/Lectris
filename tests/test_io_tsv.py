from pathlib import Path

import pytest

from lectris.errors import FormatError
from lectris.io import tsv
from lectris.model import Box, Document, Word

SAMPLE = Path(__file__).parent / "data" / "io" / "tesseract.tsv"
HEADER = "\t".join(tsv.HEADER)


def rows(*lines: str) -> str:
    """A TSV document: the header, then ``lines`` with their fields separated by spaces."""
    return "\n".join([HEADER, *(line.replace(" ", "\t") for line in lines)]) + "\n"


@pytest.fixture(scope="module")
def sample() -> Document:
    return tsv.parse(SAMPLE.read_text(encoding="utf-8"))


class TestSample:
    def test_pages_and_their_sizes(self, sample: Document) -> None:
        assert [(p.number, p.width, p.height) for p in sample.pages] == [
            (1, 1000, 800),
            (2, 1000, 800),
        ]

    def test_paragraphs_are_blocks(self, sample: Document) -> None:
        assert [block.text for block in sample.pages[0].blocks] == [
            "Lanterns hung along the harbour\nand glowed in the fog.",
            "Nobody answered.",
        ]
        assert sample.pages[1].text == "Morning came."

    def test_boxes_come_from_the_rows(self, sample: Document) -> None:
        block = sample.pages[0].blocks[0]
        assert block.box == Box(60, 50, 760, 140)
        assert block.lines[0].box == Box(60, 50, 710, 90)
        assert block.lines[0].words[1].box == Box(195, 52, 275, 90)

    def test_conf_is_scaled_to_0_1(self, sample: Document) -> None:
        words = sample.pages[0].blocks[1].lines[0].words
        assert [word.confidence for word in words] == [0.621, 0.719]  # no float noise
        assert sample.pages[0].blocks[0].lines[0].words[0].confidence == 0.95518524

    def test_structure_rows_give_no_line_confidence(self, sample: Document) -> None:
        assert all(line.confidence is None for page in sample.pages for line in page.lines)

    def test_a_word_of_whitespace_is_skipped(self, sample: Document) -> None:
        assert len(sample.pages[0].blocks[0].lines[1].words) == 5


class TestGrouping:
    def test_words_alone_are_grouped_by_page_block_paragraph_and_line(self) -> None:
        document = tsv.parse(
            rows(
                "5 1 1 1 1 1 0 0 40 10 90 one",
                "5 1 1 1 2 1 0 20 40 10 90 two",
                "5 1 1 2 1 1 0 40 40 10 90 three",
                "5 1 2 1 1 1 0 60 40 10 90 four",
                "5 1 1 1 1 2 50 0 40 10 90 one-b",
                "5 3 1 1 1 1 0 0 40 10 90 five",
            )
        )
        assert [(p.number, [b.text for b in p.blocks]) for p in document.pages] == [
            (1, ["one one-b\ntwo", "three", "four"]),
            (3, ["five"]),
        ]
        first = document.pages[0]
        assert first.blocks[0].lines[0].box == Box(0, 0, 90, 10)  # the union of its words
        assert first.blocks[0].box == Box(0, 0, 90, 30)
        assert (first.width, first.height) == (None, None)

    def test_a_line_row_with_a_confidence_gives_the_line_one(self) -> None:
        document = tsv.parse(rows("4 1 1 1 1 0 0 0 40 10 80 ", "5 1 1 1 1 1 0 0 40 10 90 word"))
        assert document.pages[0].lines[0].confidence == 0.8

    def test_a_word_row_with_conf_minus_one_has_no_confidence(self) -> None:
        document = tsv.parse(rows("5 1 1 1 1 1 0 0 40 10 -1 unsure"))
        assert document.pages[0].lines[0].words == (Word("unsure", Box(0, 0, 40, 10)),)

    def test_a_row_without_its_text_field_is_read(self) -> None:
        document = tsv.parse(rows("1 1 0 0 0 0 0 0 300 200 -1", "5 1 1 1 1 1 0 0 40 10 90 kept"))
        assert (document.pages[0].width, document.text) == (300, "kept")

    def test_line_endings_and_blank_lines(self) -> None:
        content = "\N{ZERO WIDTH NO-BREAK SPACE}" + rows(
            "5 1 1 1 1 1 0 0 40 10 90 crlf", "", "5 1 1 1 2 1 0 20 40 10 90 lines"
        ).replace("\n", "\r\n")
        assert tsv.parse(content).text == "crlf\nlines"

    def test_only_a_header_is_an_empty_document(self) -> None:
        assert tsv.parse(HEADER + "\n") == Document(())


class TestMalformed:
    @pytest.mark.parametrize(
        "content",
        [
            "",
            "level page_num block_num par_num line_num word_num left top width height conf text",
            HEADER.replace("conf", "confidence"),
            "\n" + HEADER,
        ],
    )
    def test_a_missing_or_wrong_header_is_refused(self, content: str) -> None:
        with pytest.raises(FormatError, match="TSV header"):
            tsv.parse(content)

    @pytest.mark.parametrize(
        ("row", "message"),
        [
            ("5 1 1 1 1 1 0 0 40 10", "line 2 has 10 fields, not 12"),
            ("5 1 1 1 1 1 0 0 40 10 90 a b", "line 2 has 13 fields"),
            ("6 1 1 1 1 1 0 0 40 10 90 word", "level is 6"),
            ("5 one 1 1 1 1 0 0 40 10 90 word", "page_num is not a whole number"),
            ("5 1 1 1 1 1.5 0 0 40 10 90 word", "word_num is not a whole number"),
            ("5 1 1 1 1 1 left 0 40 10 90 word", "left is not a number"),
            ("5 1 1 1 1 1 0 0 -40 10 90 word", "x0 <= x1"),
            ("5 1 1 1 1 1 0 0 40 10 101 word", "conf is '101'; it must be from 0 to 100"),
            ("5 1 1 1 1 1 0 0 40 10 -2 word", "conf is '-2'"),
            ("5 1 1 1 1 1 0 0 40 10 nan word", "conf is not a number"),
        ],
    )
    def test_a_malformed_row_is_refused(self, row: str, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            tsv.parse(rows(row))

    def test_the_error_names_the_line(self) -> None:
        content = rows("5 1 1 1 1 1 0 0 40 10 90 fine", "", "5 1 1 1 1 2 0 0 40 x 90 bad")
        with pytest.raises(FormatError, match="line 4: height"):
            tsv.parse(content)
