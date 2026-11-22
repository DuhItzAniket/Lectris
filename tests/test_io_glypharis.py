import json
from pathlib import Path
from typing import Any

import pytest

from lectris import clean, io
from lectris.errors import FormatError
from lectris.io import glypharis, jsonio
from lectris.io.detect import detect
from lectris.model import Box, Document, Engine, Word

DATA = Path(__file__).parent / "data" / "io"
SAMPLE = DATA / "glypharis.json"


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def sample() -> Document:
    return glypharis.parse(SAMPLE.read_text(encoding="utf-8"))


def parse_data(data: Any) -> Document:
    return glypharis.parse(json.dumps(data))


def page_of(*lines: dict[str, Any], **top: Any) -> dict[str, Any]:
    return {"glypharis_version": "1.0.0", "lines": list(lines)} | top


class TestTheSample:
    def test_the_engine_and_the_page(self, sample: Document) -> None:
        assert sample.engine == Engine("glypharis", "1.0.0", "glypharis-1.0.0")
        (page,) = sample.pages
        assert (page.width, page.height, page.number) == (1240, 1754, 1)
        assert len(page.blocks) == 1

    def test_lines_in_order_with_their_scores(self, sample: Document) -> None:
        lines = sample.pages[0].lines
        assert [line.text for line in lines] == [
            "Orchards bloom late this year.",
            "The growers count the hives each spr-",
            "ing and keep the record.",
            "Bees came late too.",
        ]  # the line GLYPHARIS read as empty is dropped
        first = lines[0]
        assert first.box == Box(100, 118.5, 880, 161)
        assert first.confidence == 0.962
        assert first.detection == 0.913
        assert first.polygon == ((100, 121), (880, 118.5), (880, 158.5), (100, 161))

    def test_words_are_the_text_split_without_boxes(self, sample: Document) -> None:
        last = sample.pages[0].lines[-1]
        assert last.words == (Word("Bees"), Word("came"), Word("late"), Word("too."))

    def test_it_is_detected_and_read_by_io(self, sample: Document) -> None:
        assert detect(SAMPLE.read_bytes()) == "glypharis"
        assert io.read(SAMPLE) == sample
        assert io.read(SAMPLE, format="glypharis") == sample


class TestTheContract:
    """Every key GLYPHARIS 1.0 writes is either read or deliberately ignored, and the sample
    holds every one of them, so a key GLYPHARIS adds or renames shows up here."""

    def test_top_level_keys(self, raw: dict[str, Any]) -> None:
        assert set(raw) == glypharis.READ | glypharis.IGNORED
        assert not glypharis.READ & glypharis.IGNORED

    def test_line_keys(self, raw: dict[str, Any]) -> None:
        keys = set().union(*(line.keys() for line in raw["lines"]))
        assert keys == glypharis.LINE_READ | glypharis.LINE_IGNORED
        assert not glypharis.LINE_READ & glypharis.LINE_IGNORED

    def test_ignored_keys_change_nothing(self, raw: dict[str, Any], sample: Document) -> None:
        stripped = {key: raw[key] for key in glypharis.READ}
        stripped["lines"] = [
            {key: line[key] for key in glypharis.LINE_READ if key in line} for line in raw["lines"]
        ]
        assert parse_data(stripped) == sample

    def test_unknown_keys_are_ignored(self, raw: dict[str, Any], sample: Document) -> None:
        extended = raw | {"pages_seen": 1}
        extended["lines"] = [line | {"chars": []} for line in raw["lines"]]
        assert parse_data(extended) == sample


class TestBackwardCompatibility:
    def test_the_flat_json_reading_gives_the_same_words_and_boxes(self, sample: Document) -> None:
        flat = jsonio.parse(SAMPLE.read_text(encoding="utf-8"))
        assert [(line.words, line.box, line.confidence) for line in flat.pages[0].lines] == [
            (line.words, line.box, line.confidence) for line in sample.pages[0].lines
        ]

    @pytest.mark.parametrize("profile", ["conservative", "standard", "aggressive"])
    def test_cleaning_gives_the_same_text_as_before(self, sample: Document, profile: str) -> None:
        flat = jsonio.parse(SAMPLE.read_text(encoding="utf-8"))
        assert clean(sample, profile=profile).text == clean(flat, profile=profile).text

    def test_cleaning_keeps_the_engine_and_the_lines_scores(self, sample: Document) -> None:
        result = clean(sample)
        assert result.text == (
            "Orchards bloom late this year. The growers count the hives each spring and keep "
            "the record.\n\nBees came late too."
        )
        assert result.document.engine == sample.engine
        lines = result.document.pages[0].lines
        assert [line.detection for line in lines] == [0.913, 0.897, 0.902, 0.884]
        assert lines[0].polygon == sample.pages[0].lines[0].polygon


class TestValues:
    def test_a_missing_bbox_is_the_polygons_bounds(self) -> None:
        polygon = [[10, 22], [90, 20], [91, 40], [11, 42]]
        line = parse_data(page_of({"text": "a", "polygon": polygon})).pages[0].lines[0]
        assert line.box == Box(10, 20, 91, 42)

    def test_without_bbox_and_polygon_a_line_has_no_box(self) -> None:
        line = parse_data(page_of({"text": "a"})).pages[0].lines[0]
        assert (line.box, line.polygon, line.confidence, line.detection) == (None, None, None, None)

    def test_null_scores_are_none(self) -> None:
        data = page_of({"text": "a", "confidence": None, "det_score": None, "polygon": None})
        line = parse_data(data).pages[0].lines[0]
        assert (line.confidence, line.detection, line.polygon) == (None, None, None)

    @pytest.mark.parametrize("model", [None, ""])
    def test_no_model_version(self, model: str | None) -> None:
        data = page_of({"text": "a"}) | ({} if model is None else {"model_version": model})
        assert parse_data(data).engine == Engine("glypharis", "1.0.0", None)

    def test_no_lines_is_an_empty_page(self) -> None:
        document = parse_data(page_of(width=10, height=20))
        assert document.pages[0].blocks == ()
        assert (document.pages[0].width, document.pages[0].height) == (10, 20)

    def test_keys_in_another_order_need_the_format(self) -> None:
        content = json.dumps({"lines": [{"text": "a b"}], "glypharis_version": "1.0.0"})
        assert detect(content) == "json"
        assert io.parse(content, format="glypharis").engine == Engine("glypharis", "1.0.0")


class TestMalformed:
    @pytest.mark.parametrize(
        ("data", "message"),
        [
            ([], r"the top level: expected an object, not an array"),
            ({"lines": []}, r"'glypharis_version' is missing"),
            ({"glypharis_version": 1, "lines": []}, r"glypharis_version: expected a string"),
            ({"glypharis_version": " ", "lines": []}, r"glypharis_version: the version is not"),
            ({"glypharis_version": "1.0.0"}, r"'lines' is missing"),
            (page_of(model_version=3), r"model_version: expected a string, not a number"),
            (page_of(width=-1), r"\.width: a page's size is not negative"),
            (page_of({"confidence": 0.5}), r"lines\[0\]: 'text' is missing"),
            (page_of({"text": 7}), r"lines\[0\]\.text: expected a string, not a number"),
            (page_of({"text": "a", "confidence": 1.5}), r"lines\[0\]\.confidence: a confidence"),
            (
                page_of({"text": "a", "det_score": -0.1}),
                r"lines\[0\]\.det_score: a detection score is between 0 and 1",
            ),
            (page_of({"text": "a", "bbox": [1, 2, 3]}), r"lines\[0\]\.bbox: a box is an array"),
            (page_of({"text": "a", "bbox": [3, 2, 1, 4]}), r"lines\[0\]\.bbox: a box needs"),
            (
                page_of({"text": "a", "polygon": [[0, 0], [1, 1]]}),
                r"lines\[0\]\.polygon: a polygon is an array of at least 3 points",
            ),
            (
                page_of({"text": "a", "polygon": [[0, 0], [1, 1], [2]]}),
                r"lines\[0\]\.polygon\[2\]: a point is an array \[x, y\]",
            ),
            (
                page_of({"text": "a", "polygon": [[0, 0], [1, 1], [2, True]]}),
                r"lines\[0\]\.polygon\[2\]\[1\]: expected a number, not a boolean",
            ),
        ],
    )
    def test_errors_name_the_value(self, data: Any, message: str) -> None:
        with pytest.raises(FormatError, match=message):
            parse_data(data)

    def test_not_json(self) -> None:
        with pytest.raises(FormatError, match="not valid JSON"):
            glypharis.parse('{"glypharis_version": ')
