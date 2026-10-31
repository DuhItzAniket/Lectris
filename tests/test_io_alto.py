from pathlib import Path

import pytest

from lectris.errors import FormatError
from lectris.io import alto
from lectris.model import Block, Box, Document, Line, Page, Word

DATA = Path(__file__).parent / "data" / "io"
_BOX = Box(0, 0, 10, 10)


def document(lines: str, *, namespace: str = alto.NAMESPACES[2], page: str = "") -> str:
    """An ALTO document of one page, one block and the given ``TextLine`` elements."""
    xmlns = f' xmlns="{namespace}"' if namespace else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<alto{xmlns}><Layout>\n'
        f'<Page ID="P1" PHYSICAL_IMG_NR="1"{page}><PrintSpace>\n'
        f'<TextBlock ID="B1">\n{lines}\n</TextBlock>\n'
        "</PrintSpace></Page></Layout></alto>\n"
    )


def string(content: str, *, wc: str | None = None, box: bool = True) -> str:
    """A ``String`` element; with ``box``, at ``0 0 10 10``."""
    position = ' HPOS="0" VPOS="0" WIDTH="10" HEIGHT="10"' if box else ""
    confidence = f' WC="{wc}"' if wc is not None else ""
    return f'<String CONTENT="{content}"{position}{confidence}/>'


def with_doctype(content: str, doctype: str) -> str:
    """``content`` with ``doctype`` before its root element."""
    return content.replace("<alto", f"{doctype}\n<alto", 1)


def parse_file(name: str) -> Document:
    return alto.parse((DATA / name).read_bytes())


class TestVersion2:
    def test_structure_and_text(self) -> None:
        sample = parse_file("alto_v2.xml")
        (page,) = sample.pages
        assert (page.number, page.width, page.height) == (1, 1000, 1400)
        assert sample.text == ("The ferry leaves at dawn and returns be-\nfore the market opens.")

    def test_boxes_are_hpos_vpos_width_height(self) -> None:
        (block,) = parse_file("alto_v2.xml").pages[0].blocks
        assert block.box == Box(80, 100, 865, 200)
        assert block.lines[1].box == Box(80, 160, 510, 200)
        assert block.lines[1].words[0] == Word("fore", Box(80, 160, 160, 200), 0.92)

    def test_a_hyphen_joins_the_last_word_and_its_box(self) -> None:
        line = parse_file("alto_v2.xml").pages[0].blocks[0].lines[0]
        assert line.words[-1] == Word("be-", Box(805, 100, 865, 140), 0.94)
        assert len(line.words) == 8  # SP elements are not words


class TestVersion3:
    def test_pages_are_numbered_by_physical_image_number(self) -> None:
        sample = parse_file("alto_v3.xml")
        assert [page.number for page in sample.pages] == [7, 8]

    def test_composed_blocks_hold_text_blocks(self) -> None:
        first = parse_file("alto_v3.xml").pages[0]
        assert [block.text for block in first.blocks] == [
            "Market Day",
            "Stalls open at six,\nfish first, then bread.",
            "By noon the square empties.",
        ]

    def test_without_position_a_line_and_block_take_their_words_box(self) -> None:
        (block,) = parse_file("alto_v3.xml").pages[1].blocks
        assert block.lines[0].box == Box(100, 118, 460, 164)
        assert block.box == Box(100, 118, 460, 164)


class TestVersion4:
    def test_spaces_are_read_in_reading_order(self) -> None:
        (page,) = parse_file("alto_v4.xml").pages
        assert [block.text for block in page.blocks] == [
            "Field Notes",
            "Hedgerows shelter wrens and spar\N{NOT SIGN}\n"
            "rows in the colder months, writes Zo\N{LATIN SMALL LETTER E WITH DIAERESIS}.",
            "3",
        ]

    def test_coordinates_stay_in_the_measurement_unit(self) -> None:
        (page,) = parse_file("alto_v4.xml").pages
        assert (page.width, page.height) == (2100, 2970)  # mm10, not converted
        assert page.blocks[2].box == Box(1030, 2850, 1070, 2900)

    def test_missing_attributes(self) -> None:
        words = parse_file("alto_v4.xml").pages[0].blocks[1].lines[1].words
        assert words[0] == Word("rows", Box(200, 420, 370, 480), None)  # no WC
        assert words[1] == Word("in")  # HPOS and WIDTH only: no box
        assert [word.text for word in words[2:4]] == ["the", "colder"]  # empty CONTENT dropped


class TestNamespaces:
    @pytest.mark.parametrize("namespace", [*alto.NAMESPACES, ""])
    def test_every_version_is_read(self, namespace: str) -> None:
        lines = f"<TextLine>{string('Same', wc='0.5')}<SP/>{string('text', box=False)}</TextLine>"
        expected = Document(
            (
                Page(
                    (
                        Block(
                            (Line((Word("Same", Box(0, 0, 10, 10), 0.5), Word("text")), _BOX),),
                            _BOX,
                        ),
                    )
                ),
            )
        )
        assert alto.parse(document(lines, namespace=namespace)) == expected

    def test_a_namespace_prefix_is_read(self) -> None:
        content = (
            f'<a:alto xmlns:a="{alto.NAMESPACES[1]}"><a:Layout><a:Page><a:PrintSpace>'
            '<a:TextBlock><a:TextLine><a:String CONTENT="prefixed"/></a:TextLine></a:TextBlock>'
            "</a:PrintSpace></a:Page></a:Layout></a:alto>"
        )
        assert alto.parse(content).text == "prefixed"


class TestHyphens:
    def test_a_hyphen_without_content_is_a_dash(self) -> None:
        content = document(f"<TextLine>{string('sea')}<HYP/></TextLine>")
        assert alto.parse(content).pages[0].lines[0].words == (Word("sea-", Box(0, 0, 10, 10)),)

    def test_a_hyphen_alone_on_a_line_is_a_word(self) -> None:
        hyphen = '<HYP CONTENT="-" HPOS="5" VPOS="5" WIDTH="4" HEIGHT="2"/>'
        content = document(f"<TextLine>{hyphen}</TextLine>")
        assert alto.parse(content).pages[0].lines[0].words == (Word("-", Box(5, 5, 9, 7)),)

    @pytest.mark.parametrize(
        ("word_box", "hyphen", "expected"),
        [
            (True, '<HYP CONTENT="-"/>', _BOX),
            (False, '<HYP CONTENT="-" HPOS="10" VPOS="0" WIDTH="3" HEIGHT="10"/>', None),
        ],
    )
    def test_a_box_is_joined_only_when_both_have_one(
        self, word_box: bool, hyphen: str, expected: Box | None
    ) -> None:
        content = document(f"<TextLine>{string('shore', wc='1', box=word_box)}{hyphen}</TextLine>")
        assert alto.parse(content).pages[0].lines[0].words == (Word("shore-", expected, 1.0),)


class TestPages:
    def test_without_a_physical_image_number_a_page_is_numbered_by_position(self) -> None:
        block = f"<TextBlock><TextLine>{string('x')}</TextLine></TextBlock>"
        page = f"<Page><PrintSpace>{block}</PrintSpace></Page>"
        content = f"<alto><Layout>{page}{page}</Layout></alto>"
        assert [p.number for p in alto.parse(content).pages] == [1, 2]

    def test_a_whole_float_is_a_page_number(self) -> None:
        content = document("", page="").replace('PHYSICAL_IMG_NR="1"', 'PHYSICAL_IMG_NR="12.0"')
        (page,) = alto.parse(content).pages
        assert (page.number, page.blocks) == (12, ())

    def test_bytes_follow_the_encoding_declaration(self) -> None:
        content = document(
            f"<TextLine>{string('caf\N{LATIN SMALL LETTER E WITH ACUTE}')}</TextLine>"
        )
        latin = content.replace("UTF-8", "ISO-8859-1").encode("latin-1")
        assert alto.parse(latin).text == "caf\N{LATIN SMALL LETTER E WITH ACUTE}"
        assert alto.parse(content.replace("UTF-8", "UTF-16").encode("utf-16")).text == (
            "caf\N{LATIN SMALL LETTER E WITH ACUTE}"
        )

    def test_a_standalone_document_with_an_external_dtd_is_read_without_it(self) -> None:
        content = with_doctype(
            document(f"<TextLine>{string('safe')}</TextLine>"),
            '<!DOCTYPE alto SYSTEM "file:///no/such/file.dtd">',
        ).replace('encoding="UTF-8"', 'encoding="UTF-8" standalone="yes"')
        assert alto.parse(content).text == "safe"


def text_block(text: str) -> str:
    return f"<TextBlock><TextLine>{string(text)}</TextLine></TextBlock>"


def page_of(children: str) -> list[str]:
    """The texts of the blocks of a one-page document whose ``Page`` holds ``children``."""
    content = f"<alto><Layout><Page>{children}</Page></Layout></alto>"
    return [block.text for block in alto.parse(content).pages[0].blocks]


class TestBlocksOutsideSpaces:
    def test_blocks_directly_in_the_page_are_read_in_document_order(self) -> None:
        composed = f"<ComposedBlock>{text_block('second')}{text_block('third')}</ComposedBlock>"
        assert page_of(text_block("first") + composed + text_block("fourth")) == [
            "first",
            "second",
            "third",
            "fourth",
        ]

    def test_they_keep_their_place_among_the_spaces(self) -> None:
        children = (
            f"<TopMargin>{text_block('header')}</TopMargin>"
            + text_block("loose")
            + f"<BottomMargin>{text_block('footer')}</BottomMargin>"
            + f"<PrintSpace>{text_block('body')}</PrintSpace>"
        )
        # The spaces are still read in reading order: the print space before the bottom margin.
        assert page_of(children) == ["header", "loose", "body", "footer"]


class TestMalformed:
    @pytest.mark.parametrize(
        ("content", "message"),
        [
            ("<alto><Layout>", "not well-formed XML"),
            ("", "not well-formed XML"),
            ("<html><body/></html>", "root element is <html>"),
            ('<alto xmlns="http://schema.ccs-gmbh.com/ALTO"/>', "namespace"),
            ("<alto><Layout/></alto>", "no Layout/Page"),
            (document("", page=' WIDTH="wide"'), "WIDTH is not a number"),
            (document("", page=' HEIGHT="INF"'), "HEIGHT is not a number"),
            (document("").replace('"1"', '"2.5"'), "PHYSICAL_IMG_NR is not a whole number"),
            (document(f"<TextLine>{string('x', wc='1.5')}</TextLine>"), "from 0 to 1"),
            (document(f"<TextLine>{string('x', wc='high')}</TextLine>"), "WC is not a number"),
            (
                document('<TextLine HPOS="0" VPOS="0" WIDTH="-4" HEIGHT="2"/>'),
                "TextLine .*x0 <= x1",
            ),
        ],
    )
    def test_malformed_input_is_refused(self, content: str, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            alto.parse(content)

    def test_the_error_names_the_element_and_its_line(self) -> None:
        content = document('<TextLine>\n<String ID="S9" CONTENT="x" WC="?"/></TextLine>')
        with pytest.raises(FormatError, match=r"String 'S9' \(input line 6\): WC"):
            alto.parse(content)

    @pytest.mark.parametrize(
        "doctype",
        [
            '<!DOCTYPE alto [<!ENTITY river "Severn">]>',
            '<!DOCTYPE alto [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>',
            '<!DOCTYPE alto [<!ENTITY secret SYSTEM "file:///etc/hostname">]>',
            '<!DOCTYPE alto [<!ENTITY % parameter "x">]>',
        ],
    )
    def test_entity_declarations_are_refused(self, doctype: str) -> None:
        content = with_doctype(document(f"<TextLine>{string('&amp;')}</TextLine>"), doctype)
        with pytest.raises(FormatError, match="declares the entity"):
            alto.parse(content)

    @pytest.mark.parametrize(
        "doctype",
        ['<!DOCTYPE alto SYSTEM "alto.dtd">', '<!DOCTYPE alto PUBLIC "-//X//ALTO" "alto.dtd">'],
    )
    def test_a_document_that_needs_its_external_dtd_is_refused(self, doctype: str) -> None:
        # Expat would drop the undeclared "&river;" from CONTENT without a word.
        content = with_doctype(document(f"<TextLine>{string('&river;')}</TextLine>"), doctype)
        with pytest.raises(FormatError, match="external DTD"):
            alto.parse(content)

    @pytest.mark.parametrize("standalone", [True, False])
    def test_an_undeclared_entity_is_refused(self, standalone: bool) -> None:
        content = document(f"<TextLine>{string('&river;')}</TextLine>")
        if standalone:
            content = with_doctype(content, '<!DOCTYPE alto SYSTEM "alto.dtd">').replace(
                'encoding="UTF-8"', 'encoding="UTF-8" standalone="yes"'
            )
        with pytest.raises(FormatError, match="undefined entity"):
            alto.parse(content)
