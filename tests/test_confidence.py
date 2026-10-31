import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.confidence import (
    METHODS,
    Method,
    Span,
    aggregate,
    block_confidence,
    line_confidence,
    low_confidence_spans,
    page_confidence,
)
from lectris.model import Block, Line, Page, Word

confidences = st.floats(min_value=0.0, max_value=1.0)


class TestAggregate:
    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            ("weighted", (0.9 * 4 + 0.5 * 1) / 5),
            ("mean", 0.7),
            ("min", 0.5),
            ("geometric", (0.9**4 * 0.5) ** (1 / 5)),
        ],
    )
    def test_each_method(self, method: Method, expected: float) -> None:
        assert aggregate([(0.9, 4), (0.5, 1)], method=method) == pytest.approx(expected)

    @pytest.mark.parametrize("method", METHODS)
    def test_unknown_confidences_are_skipped(self, method: Method) -> None:
        assert aggregate([(None, 10), (0.8, 2), (None, 3)], method=method) == 0.8

    @pytest.mark.parametrize("method", METHODS)
    def test_no_known_confidence_is_none(self, method: Method) -> None:
        assert aggregate([], method=method) is None
        assert aggregate([(None, 4), (None, 1)], method=method) is None

    def test_a_zero_confidence_makes_the_geometric_mean_zero(self) -> None:
        values = [(0.0, 1), (0.9, 5)]
        assert aggregate(values, method="geometric") == 0.0
        assert aggregate(values, method="weighted") == pytest.approx(0.75)

    def test_a_zero_weight_does_not_count_in_weighted_methods(self) -> None:
        values = [(0.2, 0), (0.6, 3)]
        assert aggregate(values, method="weighted") == pytest.approx(0.6)
        assert aggregate(values, method="geometric") == pytest.approx(0.6)
        assert aggregate(values, method="mean") == pytest.approx(0.4)
        assert aggregate(values, method="min") == 0.2

    def test_when_every_weight_is_zero_each_value_counts_once(self) -> None:
        values = [(0.2, 0), (0.6, 0)]
        assert aggregate(values, method="weighted") == pytest.approx(0.4)
        assert aggregate(values, method="geometric") == pytest.approx(math.sqrt(0.12))

    def test_an_unknown_method_is_refused(self) -> None:
        with pytest.raises(ValueError, match="method"):
            aggregate([(0.5, 1)], method="median")  # type: ignore[arg-type]

    def test_a_negative_weight_is_refused(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            aggregate([(0.5, -1)])

    @pytest.mark.parametrize("confidence", [-0.1, 1.5, math.nan])
    def test_a_confidence_outside_0_and_1_is_refused(self, confidence: float) -> None:
        with pytest.raises(ValueError, match="confidence"):
            aggregate([(confidence, 1)])


@given(
    st.lists(st.tuples(st.none() | confidences, st.integers(0, 50)), max_size=12),
    st.sampled_from(METHODS),
)
def test_an_aggregate_lies_between_the_known_extremes(
    values: list[tuple[float | None, int]], method: Method
) -> None:
    known = [confidence for confidence, _ in values if confidence is not None]
    result = aggregate(values, method=method)
    if not known:
        assert result is None
    else:
        assert result is not None
        assert min(known) <= result <= max(known)


class TestLineBlockPage:
    def test_a_line_weights_its_words_by_length(self) -> None:
        line = Line((Word("a", confidence=0.5), Word("word", confidence=1.0)))
        assert line_confidence(line) == pytest.approx((0.5 * 1 + 1.0 * 4) / 5)
        assert line_confidence(line, method="min") == 0.5

    def test_a_line_s_own_confidence_wins(self) -> None:
        line = Line((Word("a", confidence=0.5),), confidence=0.3)
        assert line_confidence(line) == 0.3

    def test_a_line_with_no_confidence_is_none(self) -> None:
        assert line_confidence(Line.from_text("no confidences here")) is None

    def test_a_block_weights_its_lines_by_text_length(self) -> None:
        first = Line((Word("a", confidence=0.5), Word("word", confidence=1.0)))  # 0.9, "a word"
        second = Line.from_text("ok", confidence=0.4)
        block = Block((first, second, Line.from_text("unknown")))
        assert block_confidence(block) == pytest.approx((0.9 * 6 + 0.4 * 2) / 8)
        assert block_confidence(block, method="min") == 0.4
        assert block_confidence(Block(())) is None

    def test_a_page_aggregates_all_its_lines(self) -> None:
        first = Line((Word("a", confidence=0.5), Word("word", confidence=1.0)))
        second = Line.from_text("ok", confidence=0.4)
        page = Page((Block((first,)), Block(()), Block((second,))))
        assert page_confidence(page) == pytest.approx((0.9 * 6 + 0.4 * 2) / 8)
        assert page_confidence(Page(())) is None


class TestLowConfidenceSpans:
    def test_spans_merge_neighbours_and_stop_at_line_ends(self) -> None:
        block = Block(
            (
                Line(
                    (
                        Word("The", confidence=0.95),
                        Word("qnick", confidence=0.41),
                        Word("hrown", confidence=0.52),
                        Word("fox", confidence=0.97),
                    )
                ),
                Line((Word("jumps", confidence=0.9), Word("ovcr", confidence=0.3))),
                Line.from_text("the lazy dog", confidence=0.5),
            )
        )
        assert block.text == "The qnick hrown fox\njumps ovcr\nthe lazy dog"
        assert low_confidence_spans(block) == (
            Span(4, 15, "qnick hrown", 0.41),
            Span(26, 30, "ovcr", 0.3),
            Span(31, 43, "the lazy dog", 0.5),
        )

    def test_a_word_s_own_confidence_overrides_its_line_s(self) -> None:
        line = Line((Word("sure", confidence=0.9), Word("unsure")), confidence=0.2)
        assert low_confidence_spans(Block((line,))) == (Span(5, 11, "unsure", 0.2),)

    def test_words_without_any_confidence_are_never_low(self) -> None:
        assert low_confidence_spans(Block((Line.from_text("no confidence at all"),))) == ()

    def test_the_threshold_is_strict(self) -> None:
        line = Line((Word("edge", confidence=0.6), Word("below", confidence=0.59)))
        assert low_confidence_spans(Block((line,))) == (Span(5, 10, "below", 0.59),)
        assert low_confidence_spans(Block((line,)), threshold=0.0) == ()

    def test_empty_words_neither_start_nor_break_a_span(self) -> None:
        line = Line(
            (
                Word("", confidence=0.1),
                Word("x", confidence=0.2),
                Word("", confidence=0.9),
                Word("y", confidence=0.1),
            )
        )
        block = Block((line,))
        assert block.text == " x  y"
        assert low_confidence_spans(block) == (Span(1, 5, "x  y", 0.1),)

    @pytest.mark.parametrize("threshold", [-0.1, 1.1])
    def test_a_threshold_outside_0_and_1_is_refused(self, threshold: float) -> None:
        with pytest.raises(ValueError, match="threshold"):
            low_confidence_spans(Block(()), threshold=threshold)


words = st.builds(Word, st.text(max_size=6), confidence=st.none() | confidences)
lines = st.builds(Line, st.lists(words, max_size=5).map(tuple), confidence=st.none() | confidences)


@given(st.lists(lines, max_size=4).map(tuple), confidences)
def test_span_offsets_are_exact(block_lines: tuple[Line, ...], threshold: float) -> None:
    block = Block(block_lines)
    spans = low_confidence_spans(block, threshold=threshold)
    position = 0
    for span in spans:
        assert position <= span.start < span.end
        assert block.text[span.start : span.end] == span.text
        assert span.confidence < threshold
        position = span.end
