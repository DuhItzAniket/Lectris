import pytest

from lectris import clean
from lectris.errors import FormatError
from lectris.eval import truth
from lectris.eval.scoring import drop_dont_care, score_page
from lectris.eval.truth import TruthLine, TruthPage
from lectris.model import Block, Box, Document, Line, Page


def box(y: float, x0: float = 0, x1: float = 500) -> Box:
    return Box(x0, y, x1, y + 30)


def document(*lines: tuple[str, Box | None]) -> Document:
    return Document((Page((Block(tuple(Line.from_text(text, box=b) for text, b in lines)),)),))


def texts(doc: Document) -> list[str]:
    return [line.text for page in doc.pages for line in page.lines]


PAGE = TruthPage(
    "p",
    (
        TruthLine("Bees came late.", box(0)),
        TruthLine("", box(100), care=False),  # an illegible line
        TruthLine("graffiti", box(200), care=False),  # handwriting
    ),
)


class TestDropDontCare:
    def test_lines_on_dont_care_ground_truth_are_dropped(self) -> None:
        doc = document(("Bees came late.", box(0)), ("~~", box(100)), ("grafiti", box(200)))
        assert texts(drop_dont_care(doc, PAGE)) == ["Bees came late."]

    def test_a_line_mostly_inside_a_dont_care_line_is_dropped(self) -> None:
        doc = document(("Bees came late.", box(0)), ("gr", box(205, 0, 100)))
        assert texts(drop_dont_care(doc, PAGE)) == ["Bees came late."]

    def test_lines_that_count_are_matched_first(self) -> None:
        page = TruthPage(
            "p", (TruthLine("kept", box(0)), TruthLine("", Box(0, 0, 500, 31), care=False))
        )
        doc = document(("kept", box(0)))
        assert texts(drop_dont_care(doc, page)) == ["kept"]

    def test_without_dont_care_lines_the_document_is_unchanged(self) -> None:
        doc = document(("a", box(0)))
        assert drop_dont_care(doc, TruthPage("p", (TruthLine("a", box(0)),))) is doc

    def test_blocks_left_empty_are_removed(self) -> None:
        doc = Document(
            (
                Page(
                    (
                        Block((Line.from_text("Bees came late.", box=box(0)),)),
                        Block((Line.from_text("~~", box=box(100)),)),
                    )
                ),
            )
        )
        assert len(drop_dont_care(doc, PAGE).pages[0].blocks) == 1


class TestScoringCountsOnlyCareLines:
    def test_a_dont_care_line_is_never_a_miss(self) -> None:
        doc = document(("Bees came late.", box(0)))
        score = score_page(clean(drop_dont_care(doc, PAGE)), PAGE)
        assert (score.chars.reference, score.chars.before, score.truth_lines) == (15, 0, 1)


class TestTruthCare:
    def test_care_round_trips_and_is_written_only_when_false(self) -> None:
        assert truth.parse(truth.dumps(PAGE)) == PAGE
        assert '"care": false' in truth.dumps(PAGE)
        assert truth.dumps(PAGE).count('"care"') == 2
        assert PAGE.counted.lines == (PAGE.lines[0],)

    def test_care_is_a_boolean(self) -> None:
        with pytest.raises(FormatError, match=r"lines\[0\]\.care: true or false"):
            truth.parse('{"page": "p", "lines": [{"text": "a", "care": 1}]}')
