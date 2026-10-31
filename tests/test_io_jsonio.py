import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.errors import FormatError
from lectris.io import jsonio
from lectris.model import Block, Box, Document, Line, Page, Word

DATA = Path(__file__).parent / "data" / "io"


def parse_data(data: Any) -> Document:
    return jsonio.parse(json.dumps(data))


def one_line(line: dict[str, Any]) -> dict[str, Any]:
    """A document in LECTRIS's form whose one page has one block of the line ``line``."""
    return {"pages": [{"blocks": [{"lines": [line]}]}]}


@pytest.fixture(scope="module")
def sample() -> Document:
    return jsonio.parse((DATA / "document.json").read_text(encoding="utf-8"))


class TestOwnForm:
    def test_pages_are_numbered_by_number_or_position(self, sample: Document) -> None:
        assert [(p.number, p.width, p.height) for p in sample.pages] == [
            (4, 1240, 1754),
            (2, None, None),
        ]
        assert sample.pages[1].blocks == ()

    def test_words_boxes_and_confidences(self, sample: Document) -> None:
        line = sample.pages[0].blocks[0].lines[0]
        assert line.box == Box(100, 120, 880, 160)
        assert line.confidence == 0.9
        assert line.words[2] == Word("late", Box(470, 125, 560, 160))
        assert line.words[-1] == Word("year.", None, 0.88)
        assert line.text == "Orchards bloom late this year."  # the blank word is dropped

    def test_an_absent_box_is_the_union_and_null_is_none(self, sample: Document) -> None:
        first, second = sample.pages[0].blocks
        assert first.lines[1].box == Box(100, 180, 420, 220)
        assert second.box == Box(100, 300, 520, 340)
        assert second.lines[1].box is None

    def test_a_line_of_text_is_split_into_words_without_boxes(self, sample: Document) -> None:
        line = sample.pages[0].blocks[1].lines[0]
        assert line.words == (Word("Bees"), Word("came"), Word("late"), Word("too."))
        assert line.confidence is None

    def test_unknown_keys_are_ignored(self) -> None:
        data = one_line({"text": "kept", "note": "extra"}) | {"producer": "test"}
        assert parse_data(data).text == "kept"

    def test_empty_lines_and_blocks_are_dropped(self) -> None:
        data = {"pages": [{"blocks": [{"lines": [{"words": [{"text": " "}]}]}, {"lines": []}]}]}
        assert parse_data(data) == Document((Page(()),))


class TestFlatForm:
    def test_the_lines_are_one_block_on_one_page(self) -> None:
        document = jsonio.parse((DATA / "flat_lines.json").read_text(encoding="utf-8"))
        (page,) = document.pages
        (block,) = page.blocks
        assert block.text == "Tide tables\nHigh water at 06:42\nLow water at 12:55"
        assert block.box == Box(40, 30, 420, 150)  # the union of the lines' boxes
        assert block.lines[0].box == Box(40, 30, 300, 70)
        assert block.lines[0].confidence == 0.97
        assert block.lines[2].box is None

    def test_a_top_level_array_is_a_list_of_lines(self) -> None:
        document = parse_data([{"text": "first", "bbox": [0, 0, 5, 5]}, {"text": "second"}])
        assert document == Document(
            (
                Page(
                    (
                        Block(
                            (
                                Line.from_text("first", box=Box(0, 0, 5, 5)),
                                Line.from_text("second"),
                            ),
                            Box(0, 0, 5, 5),
                        ),
                    )
                ),
            )
        )

    @pytest.mark.parametrize("data", [[], {"lines": []}, [{"text": "  "}, {"words": []}]])
    def test_no_lines_is_a_page_without_blocks(self, data: Any) -> None:
        assert parse_data(data) == Document((Page(()),))


class TestDumps:
    def test_the_sample_round_trips(self, sample: Document) -> None:
        assert jsonio.parse(jsonio.dumps(sample)) == sample

    def test_every_key_is_written(self) -> None:
        document = Document((Page((Block((Line((Word("Ånd", Box(1, 2, 3, 4)),)),)),)),))
        assert json.loads(jsonio.dumps(document)) == {
            "pages": [
                {
                    "number": 1,
                    "width": None,
                    "height": None,
                    "blocks": [
                        {
                            "box": None,
                            "lines": [
                                {
                                    "box": None,
                                    "confidence": None,
                                    "words": [
                                        {"text": "Ånd", "box": [1, 2, 3, 4], "confidence": None}
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

    def test_indent_and_unicode(self) -> None:
        document = Document((Page((Block((Line((Word("Ånd"),)),)),)),))
        compact = jsonio.dumps(document, indent=None)
        assert "\n" not in compact
        assert "Ånd" in compact
        assert jsonio.dumps(document).count("\n") > 10


finite = st.floats(allow_nan=False, allow_infinity=False)
word_texts = st.text(
    st.characters(exclude_categories=("Cs", "Cc", "Zl", "Zp")), min_size=1, max_size=8
).filter(lambda text: text == text.strip())
confidences = st.none() | st.floats(0, 1)


@st.composite
def boxes(draw: st.DrawFn) -> Box | None:
    if draw(st.booleans()):
        return None
    x0, x1 = sorted((draw(finite), draw(finite)))
    y0, y1 = sorted((draw(finite), draw(finite)))
    return Box(x0, y0, x1, y1)


words = st.builds(Word, word_texts, boxes(), confidences)
lines = st.builds(Line, st.lists(words, min_size=1, max_size=4).map(tuple), boxes(), confidences)
blocks = st.builds(Block, st.lists(lines, min_size=1, max_size=3).map(tuple), boxes())
sizes = st.none() | st.floats(0, 1e6)
pages = st.builds(
    Page, st.lists(blocks, max_size=3).map(tuple), sizes, sizes, st.integers(-5, 10_000)
)
documents = st.builds(Document, st.lists(pages, max_size=3).map(tuple))


@given(documents)
def test_dumps_and_parse_round_trip(document: Document) -> None:
    assert jsonio.parse(jsonio.dumps(document)) == document
    assert jsonio.parse(jsonio.dumps(document, indent=None)) == document


class TestMalformed:
    @pytest.mark.parametrize(
        ("content", "message"),
        [
            ("", "not valid JSON"),
            ('{"pages": [}', "not valid JSON"),
            ('{"lines": [{"text": "x", "confidence": NaN}]}', "NaN is not a number JSON allows"),
            ('"text"', "the top level is a string"),
            ("{}", "needs 'pages' or 'lines'"),
            ('{"pages": [], "lines": []}', "both 'pages' and 'lines'"),
            ('{"pages": {}}', r"^pages: expected an array, not an object"),
            ("[1]", r"^\[0\]: expected an object, not a number"),
            ("[" * 100_000 + "]" * 100_000, "not valid JSON"),
        ],
    )
    def test_invalid_documents_are_refused(self, content: str, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            jsonio.parse(content)

    @pytest.mark.parametrize(
        ("data", "message"),
        [
            ({"pages": [{}]}, r"^pages\[0\]: 'blocks' is missing"),
            ({"pages": [{"blocks": [{}]}]}, r"^pages\[0\]\.blocks\[0\]: 'lines' is missing"),
            ({"pages": [{"number": "1", "blocks": []}]}, r"^pages\[0\]\.number: .* a string"),
            ({"pages": [{"number": True, "blocks": []}]}, r"^pages\[0\]\.number: .* a boolean"),
            ({"pages": [{"width": -1, "blocks": []}]}, r"^pages\[0\]\.width: .* not negative"),
            (one_line({}), r"^pages\[0\]\.blocks\[0\]\.lines\[0\]: a line needs"),
            (one_line({"text": "a", "words": []}), r"lines\[0\]: a line gives .* not both"),
            (one_line({"text": 5}), r"lines\[0\]\.text: expected a string, not a number"),
            (one_line({"words": [{"box": None}]}), r"words\[0\]: 'text' is missing"),
            (one_line({"words": [{"text": "a", "box": [0, 0, 1]}]}), r"words\[0\]\.box: a box"),
            (one_line({"text": "a", "box": [0, 0, True, 1]}), r"lines\[0\]\.box\[2\]: .* boolean"),
            (one_line({"text": "a", "box": [5, 0, 1, 1]}), r"lines\[0\]\.box: .*x0 <= x1"),
            (one_line({"text": "a", "box": [0, 0, 10**400, 1]}), r"box\[2\]: .* out of range"),
            (one_line({"text": "a", "confidence": 93}), r"lines\[0\]\.confidence: .*between"),
            ([{"text": "a"}, {"text": "b", "bbox": "0 0 1 1"}], r"^\[1\]\.bbox: a box is"),
            ({"lines": [{"text": "a", "confidence": "high"}]}, r"^lines\[0\]\.confidence: "),
        ],
    )
    def test_errors_name_the_path(self, data: Any, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            parse_data(data)

    def test_the_path_reaches_deep_values(self) -> None:
        good = {"text": "fine"}
        bad = {"words": [good, {"text": "x", "confidence": -0.5}]}
        data = {"pages": [{"blocks": []}, {"blocks": [{"lines": [good]}, {"lines": [good, bad]}]}]}
        with pytest.raises(FormatError, match=r"^pages\[1\]\.blocks\[1\]\.lines\[1\]\.words\[1\]"):
            parse_data(data)
