from pathlib import Path

import pytest

from lectris.errors import FormatError
from lectris.io import hocr
from lectris.model import Box, Document, Word

SAMPLE = Path(__file__).parent / "data" / "io" / "two_columns.hocr"


def page(body: str, title: str = "bbox 0 0 1000 800") -> str:
    """An hOCR document of one page holding ``body``."""
    return (
        "<!DOCTYPE html>\n<html><head><title>test</title></head><body>\n"
        f"<div class='ocr_page' id='page_1' title='{title}'>\n{body}\n</div>\n</body></html>\n"
    )


def word(text: str, title: str = "bbox 0 0 10 10; x_wconf 90") -> str:
    return f"<span class='ocrx_word' title='{title}'>{text}</span>"


@pytest.fixture(scope="module")
def sample() -> Document:
    return hocr.parse(SAMPLE.read_text(encoding="utf-8"))


class TestSample:
    def test_the_page_and_its_size(self, sample: Document) -> None:
        assert len(sample.pages) == 1
        first = sample.pages[0]
        assert (first.width, first.height) == (1200, 1600)
        assert first.number == 1  # ppageno 0: hOCR counts pages from 0

    def test_paragraphs_are_blocks_in_document_order(self, sample: Document) -> None:
        assert [block.text for block in sample.pages[0].blocks] == [
            "Notes on the Lower Canal",
            "Barges once carried coal\nand timber past the mill.",
            "Today the towpath is quiet.",
            'Locks & weirs still\nhold the water back,\nsays the "keeper", Renée.',
        ]

    def test_boxes_come_from_bbox(self, sample: Document) -> None:
        block = sample.pages[0].blocks[1]
        assert block.box == Box(100, 200, 580, 300)
        assert block.lines[1].box == Box(100, 260, 580, 300)
        assert block.lines[1].words[0].box == Box(100, 260, 170, 300)

    def test_x_wconf_is_scaled_to_0_1_and_lines_have_no_confidence(self, sample: Document) -> None:
        line = sample.pages[0].blocks[0].lines[0]
        assert [w.confidence for w in line.words] == [0.96, 0.95, 0.97, 0.94, 0.93]
        assert all(line.confidence is None for line in sample.pages[0].lines)

    def test_entities_are_decoded_and_inner_tags_flattened(self, sample: Document) -> None:
        words = [w.text for line in sample.pages[0].blocks[3].lines for w in line.words]
        assert "&" in words
        assert '"keeper",' in words
        assert "Renée." in words
        assert words[4:8] == ["hold", "the", "water", "back,"]

    def test_a_word_of_whitespace_is_dropped(self, sample: Document) -> None:
        line = sample.pages[0].blocks[3].lines[1]
        assert len(line.words) == 4

    def test_a_quoted_property_may_hold_a_semicolon(self) -> None:
        title = 'image "scan; first.png"; bbox 0 0 640 480; ppageno 2'
        document = hocr.parse(page(word("Ink"), title))
        assert (document.pages[0].width, document.pages[0].number) == (640, 3)


class TestStructure:
    def test_pages_are_numbered_by_ppageno_or_position(self) -> None:
        pages = (
            "<div class='ocr_page' title='bbox 0 0 10 10; ppageno 4'>" + word("four") + "</div>"
            "<div class='ocr_page' title='bbox 0 0 10 10'>" + word("second") + "</div>"
        )
        document = hocr.parse(f"<html><body>{pages}</body></html>")
        assert [p.number for p in document.pages] == [5, 2]
        assert document.text == "four\n\nsecond"

    def test_an_area_without_paragraphs_is_one_block(self) -> None:
        body = (
            "<div class='ocr_carea' title='bbox 0 0 500 100'>"
            "<span class='ocr_line' title='bbox 0 0 500 40'>" + word("first") + "</span>"
            "<span class='ocr_line' title='bbox 0 50 500 90'>" + word("second") + "</span>"
            "</div>"
        )
        (block,) = hocr.parse(page(body)).pages[0].blocks
        assert block.text == "first\nsecond"
        assert block.box == Box(0, 0, 500, 100)

    def test_lines_and_words_outside_containers_are_grouped(self) -> None:
        body = (
            word("loose", "bbox 0 0 50 20")
            + word("words", "bbox 60 0 120 20")
            + "<span class='ocr_line'>"
            + word("a line", "bbox 0 40 90 60")
            + "</span>"
            + "<p class='ocr_par'><span class='ocr_line'>"
            + word("in a block")
            + "</span></p>"
            + "<span class='ocr_line'>"
            + word("after")
            + "</span>"
        )
        blocks = hocr.parse(page(body)).pages[0].blocks
        assert [block.text for block in blocks] == ["loose words\na line", "in a block", "after"]
        assert blocks[0].lines[0].box == Box(0, 0, 120, 20)
        assert blocks[0].box == Box(0, 0, 120, 60)

    def test_loose_lines_in_separate_areas_are_separate_blocks(self) -> None:
        def area(text: str) -> str:
            return (
                "<div class='ocr_carea'><p class='ocr_par'><span class='ocr_line'>"
                f"{word('kept')}</span></p><span class='ocr_line'>{word(text)}</span></div>"
            )

        blocks = hocr.parse(page(area("one") + area("two"))).pages[0].blocks
        assert [block.text for block in blocks] == ["kept", "one", "kept", "two"]

    def test_a_line_without_words_takes_its_text(self) -> None:
        body = "<span class='ocr_line' title='bbox 5 5 200 30'>Plain  line\n text</span>"
        (line,) = hocr.parse(page(body)).pages[0].lines
        assert line.words == (Word("Plain"), Word("line"), Word("text"))
        assert line.box == Box(5, 5, 200, 30)

    def test_a_line_class_holding_lines_is_a_container(self) -> None:
        body = (
            "<div class='ocr_header'>"
            "<span class='ocr_line'>" + word("Running") + "</span>"
            "<span class='ocr_line'>" + word("head") + "</span>"
            "</div>"
        )
        assert [line.text for line in hocr.parse(page(body)).pages[0].lines] == [
            "Running",
            "head",
        ]

    @pytest.mark.parametrize(
        "line_class", ["ocr_line", "ocrx_line", "ocr_caption", "ocr_textfloat"]
    )
    def test_line_classes(self, line_class: str) -> None:
        body = f"<span class='{line_class} extra'>" + word("text") + "</span>"
        assert hocr.parse(page(body)).pages[0].lines[0].text == "text"

    def test_missing_title_properties_give_no_box_or_confidence(self) -> None:
        body = (
            "<span class='ocr_line'>"
            + word("unboxed", "")
            + word("boxed", "bbox 100 10 150 40")
            + word("sure", "bbox 160 12 220 42; x_wconf 99.5")
            + "</span>"
        )
        document = hocr.parse(page(body, title=""))
        (line,) = document.pages[0].lines
        assert line.words == (
            Word("unboxed"),
            Word("boxed", Box(100, 10, 150, 40)),
            Word("sure", Box(160, 12, 220, 42), 0.995),
        )
        assert line.box == Box(100, 10, 220, 42)
        assert document.pages[0].blocks[0].box == line.box
        assert (document.pages[0].width, document.pages[0].height) == (None, None)

    def test_lenient_html_is_read(self) -> None:
        content = (
            "\N{ZERO WIDTH NO-BREAK SPACE}<HTML><BODY><DIV CLASS=ocr_page TITLE='bbox 0 0 90 90'>"
            "<P CLASS='ocr_par'><SPAN CLASS='ocr_line'>"
            "<SPAN CLASS=ocrx_word>un&shy;closed</SPAN><br>"
            "<span class='ocrx_word'>tags</span></P></DIV>"
        )
        assert hocr.parse(content).text == "un\N{SOFT HYPHEN}closed tags"

    @pytest.mark.parametrize(
        "second",
        [
            "<p class='ocr_par' title='bbox 0 50 200 70'>",
            "<div class='ocr_carea' title='bbox 0 50 200 70'>",
        ],
    )
    def test_a_new_paragraph_or_area_ends_an_unclosed_p(self, second: str) -> None:
        body = (
            "<p class='ocr_par' title='bbox 0 0 200 20'><span class='ocr_line'>"
            + word("first")
            + "</span>"
            + second
            + "<span class='ocr_line'>"
            + word("second")
            + "</span>"
        )
        blocks = hocr.parse(page(body)).pages[0].blocks
        assert [(block.text, block.box) for block in blocks] == [
            ("first", Box(0, 0, 200, 20)),
            ("second", Box(0, 50, 200, 70)),
        ]

    def test_other_elements_do_not_end_a_p(self) -> None:
        body = (
            "<p class='ocr_par'><span class='ocr_line'>"
            + word("one")
            + "</span><div><span class='ocr_line'>"
            + word("block")
            + "</span></div></p>"
        )
        assert [block.text for block in hocr.parse(page(body)).pages[0].blocks] == ["one\nblock"]

    def test_a_word_never_spans_lines(self) -> None:
        body = "<span class='ocr_line'>" + word("two\n   parts") + "</span>"
        assert hocr.parse(page(body)).pages[0].lines[0].words[0].text == "two parts"


class TestMalformed:
    @pytest.mark.parametrize(
        ("body", "message"),
        [
            (word("x", "bbox 0 0 10"), "bbox needs four numbers"),
            (word("x", "bbox 0 0 ten 10"), "bbox is not a number: 'ten'"),
            (word("x", "bbox 10 0 0 10"), "x0 <= x1"),
            (word("x", "bbox 0 0 10 10; x_wconf high"), "x_wconf is not a number"),
            (word("x", "bbox 0 0 10 10; x_wconf 140"), "from 0 to 100"),
            (word("x", "bbox 0 0 10 10; x_wconf -3"), "from 0 to 100"),
            (word("x", "bbox 0 0 nan 10"), "not a number"),
        ],
    )
    def test_a_malformed_property_is_refused(self, body: str, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            hocr.parse(page(f"<span class='ocr_line'>{body}</span>"))

    @pytest.mark.parametrize("ppageno", ["one", "-1", "1.5"])
    def test_a_malformed_ppageno_is_refused(self, ppageno: str) -> None:
        with pytest.raises(FormatError, match="ppageno"):
            hocr.parse(page(word("x"), f"bbox 0 0 10 10; ppageno {ppageno}"))

    def test_the_error_names_the_element_and_its_line(self) -> None:
        content = page("\n\n<span class='ocrx_word' id='word_1_9' title='x_wconf 1e'>x</span>")
        with pytest.raises(FormatError, match=r"ocrx_word 'word_1_9' \(input line 6\)"):
            hocr.parse(content)

    @pytest.mark.parametrize(
        "content",
        ["", "plain text", "<html><body><p class='ocr_par'>no page</p></body></html>"],
    )
    def test_a_document_without_ocr_page_is_refused(self, content: str) -> None:
        with pytest.raises(FormatError, match="ocr_page"):
            hocr.parse(content)

    def test_nesting_too_deep_to_read_is_refused(self) -> None:
        depth = 5000
        with pytest.raises(FormatError, match="nested too deeply"):
            hocr.parse(page("<div>" * depth + word("deep") + "</div>" * depth))
