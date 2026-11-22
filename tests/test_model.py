import math

import pytest

from lectris.model import Block, Box, Document, Engine, Line, Page, Word, union_of


class TestBox:
    def test_size(self) -> None:
        box = Box(10, 20, 40, 30)
        assert (box.width, box.height, box.area) == (30, 10, 300)
        assert box.center == (25, 25)

    @pytest.mark.parametrize(
        "coordinates",
        [(5, 0, 4, 1), (0, 5, 1, 4), (math.nan, 0, 1, 1), (0, 0, math.inf, 1)],
    )
    def test_an_inverted_or_infinite_box_is_refused(
        self, coordinates: tuple[float, float, float, float]
    ) -> None:
        with pytest.raises(ValueError, match="box"):
            Box(*coordinates)

    def test_a_degenerate_box_is_allowed(self) -> None:
        assert Box(3, 3, 3, 3).area == 0

    def test_union(self) -> None:
        assert Box(0, 0, 10, 10).union(Box(5, -5, 20, 8)) == Box(0, -5, 20, 10)

    def test_intersection(self) -> None:
        assert Box(0, 0, 10, 10).intersection(Box(5, 5, 20, 20)) == Box(5, 5, 10, 10)

    @pytest.mark.parametrize("other", [Box(10, 0, 20, 10), Box(20, 20, 30, 30)])
    def test_boxes_that_touch_or_are_apart_do_not_intersect(self, other: Box) -> None:
        assert Box(0, 0, 10, 10).intersection(other) is None

    def test_union_of_skips_missing_boxes(self) -> None:
        assert union_of([None, Box(0, 0, 1, 1), None, Box(2, 2, 3, 3)]) == Box(0, 0, 3, 3)
        assert union_of([None, None]) is None
        assert union_of([]) is None


class TestConfidence:
    @pytest.mark.parametrize("confidence", [-0.01, 1.01, 93.0])
    def test_a_confidence_outside_0_and_1_is_refused(self, confidence: float) -> None:
        with pytest.raises(ValueError, match="confidence"):
            Word("word", confidence=confidence)
        with pytest.raises(ValueError, match="confidence"):
            Line((), confidence=confidence)

    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0, None])
    def test_a_confidence_in_range_or_unknown_is_kept(self, confidence: float | None) -> None:
        assert Word("word", confidence=confidence).confidence == confidence


class TestDetection:
    def test_a_line_keeps_its_polygon_and_detection_score(self) -> None:
        polygon = ((0.0, 1.0), (10.0, 0.0), (10.0, 5.0), (0.0, 6.0))
        line = Line((Word("tilted"),), polygon=polygon, detection=0.8)
        assert (line.polygon, line.detection) == (polygon, 0.8)
        assert Line((Word("plain"),)).polygon is None

    @pytest.mark.parametrize("score", [-0.01, 1.01])
    def test_a_detection_score_outside_0_and_1_is_refused(self, score: float) -> None:
        with pytest.raises(ValueError, match="a detection score is between 0 and 1"):
            Line((), detection=score)

    @pytest.mark.parametrize(
        ("polygon", "message"),
        [
            (((0.0, 0.0), (1.0, 1.0)), "at least 3 points, not 2"),
            (((0.0, 0.0), (1.0, 1.0), (math.nan, 2.0)), "pairs of finite numbers"),
            (((0.0, 0.0), (1.0, 1.0), (2.0,)), "pairs of finite numbers"),
        ],
    )
    def test_a_polygon_needs_three_finite_points(
        self, polygon: tuple[tuple[float, float], ...], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            Line((), polygon=polygon)


class TestEngine:
    def test_a_document_can_name_its_engine(self) -> None:
        engine = Engine("glypharis", "1.0.0", "glypharis-1.0.0")
        assert Document((), engine=engine).engine == engine
        assert Document(()).engine is None
        assert Engine("tesseract") == Engine("tesseract", None, None)

    @pytest.mark.parametrize(
        ("name", "version", "model", "message"),
        [
            ("", None, None, "an engine has a name"),
            ("  ", None, None, "an engine has a name"),
            ("glypharis", "", None, "None when unknown, not empty"),
            ("glypharis", "1.0.0", "", "None when unknown, not empty"),
        ],
    )
    def test_names_and_versions_are_not_empty(
        self, name: str, version: str | None, model: str | None, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            Engine(name, version, model)


class TestText:
    def test_a_line_joins_its_words_with_one_space(self) -> None:
        line = Line((Word("Recovered"), Word("text")))
        assert line.text == "Recovered text"

    def test_a_line_from_text_splits_on_whitespace(self) -> None:
        line = Line.from_text("  two\twords ", confidence=0.9)
        assert [word.text for word in line.words] == ["two", "words"]
        assert line.confidence == 0.9

    def test_blocks_pages_and_documents_join_their_parts(self) -> None:
        first = Block((Line.from_text("one line"), Line.from_text("and another")))
        second = Block((Line.from_text("a second block"),))
        page = Page((first, Block(()), second))
        assert first.text == "one line\nand another"
        assert page.text == "one line\nand another\n\na second block"
        assert len(page.lines) == 3
        document = Document((page, Page(()), Page((second,), number=3)))
        assert document.text == "one line\nand another\n\na second block\n\na second block"
