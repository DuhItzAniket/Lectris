from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.io import plain
from lectris.model import Block, Document, Line, Page, Word

SAMPLE = Path(__file__).parent / "data" / "io" / "pages.txt"


class TestParse:
    def test_the_sample(self) -> None:
        document = plain.parse(SAMPLE.read_text(encoding="utf-8"))
        assert [page.number for page in document.pages] == [1, 2]  # the final form feed ends page 2
        assert [block.text for block in document.pages[0].blocks] == [
            "The Mill",
            "The lane ran down to the river,\npast the mill that stood empty.",
            "Nobody had ground flour there\nfor forty years.",
        ]
        assert document.pages[1].text == "Second page, one line."

    def test_words_have_no_boxes_or_confidences(self) -> None:
        (line,) = plain.parse("  spaced\tout  words ").pages[0].lines
        assert line == Line((Word("spaced"), Word("out"), Word("words")))
        assert line.box is None
        assert line.confidence is None

    @pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
    def test_line_breaks(self, newline: str) -> None:
        text = newline.join(["one", "two", "", "three", ""])
        assert [block.text for block in plain.parse(text).pages[0].blocks] == [
            "one\ntwo",
            "three",
        ]

    def test_runs_of_blank_lines_separate_blocks_once(self) -> None:
        text = "\n \n\nfirst\n\n\t\n\n\nsecond\n\n"
        assert [block.text for block in plain.parse(text).pages[0].blocks] == [
            "first",
            "second",
        ]

    @pytest.mark.parametrize(
        ("text", "pages"),
        [
            ("", 1),
            ("only", 1),
            ("only\f", 1),
            ("only\f\n", 1),
            ("one\ftwo", 2),
            ("one\f\ftwo\f", 3),
            ("\f", 1),
            ("\f\f", 2),
        ],
    )
    def test_form_feeds_end_pages(self, text: str, pages: int) -> None:
        document = plain.parse(text)
        assert len(document.pages) == pages
        assert [page.number for page in document.pages] == list(range(1, pages + 1))

    def test_an_empty_page_in_between_is_kept(self) -> None:
        document = plain.parse("one\f\ftwo")
        assert [page.text for page in document.pages] == ["one", "", "two"]

    def test_a_byte_order_mark_is_not_text(self) -> None:
        assert plain.parse("\N{ZERO WIDTH NO-BREAK SPACE}Title").text == "Title"


class TestDumps:
    def test_layout(self) -> None:
        first = Page(
            (Block((Line.from_text("a b"), Line.from_text("c"))), Block((Line.from_text("d"),)))
        )
        document = Document((first, Page(()), Page((Block((Line.from_text("e"),)),))))
        assert plain.dumps(document) == "a b\nc\n\nd\n\f\fe\n"

    def test_an_empty_document(self) -> None:
        assert plain.dumps(Document(())) == ""


@given(st.text(st.sampled_from("ab \t\n\r\f\N{NO-BREAK SPACE}\N{LINE SEPARATOR}é")))
def test_dumps_then_parse_gives_the_parsed_document_back(text: str) -> None:
    document = plain.parse(text)
    again = plain.parse(plain.dumps(document))
    assert again.text == document.text
    # The same pages, except that an empty last page does not survive.
    assert again.pages == document.pages[: len(again.pages)]
    assert all(not page.blocks for page in document.pages[len(again.pages) :])
