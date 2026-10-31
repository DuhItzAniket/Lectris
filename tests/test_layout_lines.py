import pytest
from hypothesis import given
from hypothesis import strategies as st

from layout_pages import (
    make_column,
    make_line,
    scale_word,
    scan_column,
    scrambled,
    skew_line,
    texts,
    words_of,
)
from lectris.layout.lines import group_words
from lectris.model import Box, Line, Word, union_of


class TestOneColumn:
    def test_words_in_any_order_become_lines_from_top_to_bottom(self) -> None:
        page = make_column(["the first line", "a second line", "and the third"], 50, 100)
        lines = group_words(scrambled(words_of(page)))
        assert texts(lines) == ["the first line", "a second line", "and the third"]

    def test_a_lines_box_is_the_union_of_its_words(self) -> None:
        (line,) = group_words(words_of([make_line("three short words", 50, 100)]))
        assert line.box == union_of(word.box for word in line.words) == Box(50, 100, 220, 120)
        assert line.confidence is None

    def test_words_keep_their_confidence(self) -> None:
        word = Word("sure", Box(0, 0, 40, 20), confidence=0.75)
        (line,) = group_words([word, Word("not", Box(50, 0, 80, 20))])
        assert line.words[0] is word

    def test_a_wide_space_of_a_justified_line_does_not_split_it(self) -> None:
        # Over two word heights between words: wide, but under a gutter.
        line = make_line("loosely set line", 50, 100, width=230)
        assert texts(group_words(words_of([line]))) == ["loosely set line"]

    def test_lines_that_touch_stay_apart(self) -> None:
        page = make_column(["upper line here", "lower line here"], 50, 100, pitch=20)
        assert texts(group_words(words_of(page))) == ["upper line here", "lower line here"]

    def test_descenders_reaching_into_the_next_line_do_not_merge_it(self) -> None:
        upper = [Word("gyp", Box(50, 100, 80, 126)), Word("sum", Box(90, 100, 120, 120))]
        lower = [Word("Text", Box(50, 122, 90, 142)), Word("below", Box(100, 122, 150, 142))]
        assert texts(group_words(upper + lower)) == ["gyp sum", "Text below"]

    def test_a_skewed_line_stays_one_line(self) -> None:
        words = [
            Word(f"w{i}", Box(50 + 40 * i, 100 + 2 * i, 80 + 40 * i, 120 + 2 * i)) for i in range(8)
        ]
        lines = group_words(scrambled(words))
        assert texts(lines) == ["w0 w1 w2 w3 w4 w5 w6 w7"]


class TestOffsetWords:
    def test_subscripts_and_superscripts_stay_on_the_line(self) -> None:
        words = [
            Word("H", Box(50, 100, 60, 120)),
            Word("2", Box(61, 110, 67, 125)),
            Word("O", Box(68, 100, 80, 120)),
            Word("x", Box(90, 100, 100, 120)),
            Word("2", Box(101, 94, 107, 108)),
        ]
        assert texts(group_words(scrambled(words))) == ["H 2 O x 2"]

    def test_punctuation_lower_than_the_words_stays_on_the_line(self) -> None:
        words = [
            Word("end", Box(50, 100, 80, 120)),
            Word(",", Box(81, 114, 85, 124)),
            Word("then", Box(95, 100, 135, 120)),
            Word(".", Box(136, 116, 139, 119)),
        ]
        assert texts(group_words(words)) == ["end , then ."]

    def test_a_tall_word_inside_a_line_does_not_pull_in_the_next_line(self) -> None:
        # A rule read as a letter, as tall as three lines, in the middle of the first one.
        first = make_line("aaa bbb ccc", 50, 100)
        rule = Word("|", Box(170, 100, 172, 190))
        rest = make_line("ddd eee", 182, 100)
        second = make_line("fff ggg hhh iii jjj", 50, 130)
        words = [*words_of([first]), rule, *words_of([rest, second])]
        assert texts(group_words(words)) == ["aaa bbb ccc | ddd eee", "fff ggg hhh iii jjj"]


class TestColumns:
    def test_columns_that_share_a_height_are_not_merged(self) -> None:
        left = make_column(["left one text", "left two text"], 50, 100)
        right = make_column(["right one text", "right two text"], 260, 100)  # a gap of 80
        lines = group_words(scrambled(words_of(left + right)))
        assert texts(lines) == [
            "left one text",
            "right one text",
            "left two text",
            "right two text",
        ]

    def test_max_gap_sets_how_wide_a_gutter_must_be(self) -> None:
        left, right = make_line("left text", 50, 100), make_line("right text", 190, 100)
        words = words_of([left, right])  # a gap of 50, two and a half word heights
        assert texts(group_words(words)) == ["left text right text"]
        assert texts(group_words(words, max_gap=2)) == ["left text", "right text"]

    def test_three_columns(self) -> None:
        columns = [make_column([f"c{c} one", f"c{c} two"], 50 + 200 * c, 100) for c in range(3)]
        lines = group_words(scrambled(words_of(line for column in columns for line in column)))
        assert texts(lines) == ["c0 one", "c1 one", "c2 one", "c0 two", "c1 two", "c2 two"]


class TestSkew:
    @pytest.mark.parametrize("degrees", [-3.0, 1.0, 1.75, 2.25, 3.0])
    def test_long_lines_of_a_skewed_scan_stay_whole(self, degrees: float) -> None:
        # Lines 2000 wide climb or fall by up to 105 over their length, three times their height.
        skewed = [
            skew_line(line, degrees, (1100, 500))
            for line in scan_column("row", 100, 200, 12, width=2000, words=20)
        ]
        lines = group_words(scrambled(words_of(skewed)))
        assert [line.words[0].text for line in lines] == [f"row{i:02d}" for i in range(12)]
        assert all(len(line.words) == 21 for line in lines)

    def test_an_infinite_max_gap_separates_lines_by_height_only(self) -> None:
        words = words_of([make_line("far", 0, 100), make_line("apart", 900, 100)])
        lower = words_of([make_line("below", 0, 130)])
        lines = group_words(words + lower, max_gap=float("inf"))
        assert texts(lines) == ["far apart", "below"]


class TestWithoutBoxes:
    def test_words_without_boxes_form_the_last_line_in_input_order(self) -> None:
        words = [Word("loose"), *words_of([make_line("boxed words", 50, 100)]), Word("ones")]
        lines = group_words(words)
        assert texts(lines) == ["boxed words", "loose ones"]
        assert lines[-1].box is None

    def test_only_words_without_boxes(self) -> None:
        assert group_words([Word("no"), Word("boxes")]) == (Line((Word("no"), Word("boxes"))),)

    def test_no_words(self) -> None:
        assert group_words([]) == ()


class TestOptions:
    def test_min_overlap_decides_how_far_a_word_may_be_offset(self) -> None:
        words = [Word("base", Box(50, 100, 90, 120)), Word("low", Box(100, 112, 130, 132))]
        assert texts(group_words(words)) == ["base", "low"]
        assert texts(group_words(words, min_overlap=0.4)) == ["base low"]

    @pytest.mark.parametrize(
        ("min_overlap", "max_gap"), [(0.0, 3.0), (1.5, 3.0), (0.5, -1.0), (0.5, float("nan"))]
    )
    def test_invalid_options_are_refused(self, min_overlap: float, max_gap: float) -> None:
        with pytest.raises(ValueError, match=r"min_overlap|max_gap"):
            group_words([], min_overlap=min_overlap, max_gap=max_gap)


@st.composite
def word_layouts(draw: st.DrawFn) -> list[Word]:
    """Words on a loose grid: rows of words, some boxes missing, in any order."""
    words: list[Word] = []
    for row in range(draw(st.integers(0, 6))):
        x = draw(st.integers(0, 100))
        for column in range(draw(st.integers(1, 6))):
            width = draw(st.integers(5, 60))
            top = 30 * row + draw(st.integers(-4, 4))
            boxed = draw(st.booleans()) or draw(st.booleans())
            box = Box(x, top, x + width, top + draw(st.integers(8, 24))) if boxed else None
            words.append(Word(f"r{row}c{column}", box))
            x += width + draw(st.integers(5, 120))
    return draw(st.permutations(words))


class TestProperties:
    @given(word_layouts())
    def test_every_word_lands_in_exactly_one_line(self, words: list[Word]) -> None:
        lines = group_words(words)
        assert sorted(id(word) for word in words_of(lines)) == sorted(id(word) for word in words)
        boxed = [line for line in lines if line.box is not None]
        for line in boxed:
            assert line.box == union_of(word.box for word in line.words)
            starts = [word.box.x0 for word in line.words if word.box is not None]
            assert starts == sorted(starts)
        tops = [(line.box.y0, line.box.x0) for line in boxed if line.box is not None]
        assert tops == sorted(tops)

    @given(word_layouts(), st.integers(-8, 8))
    def test_scaling_the_page_does_not_change_the_lines(
        self, words: list[Word], exponent: int
    ) -> None:
        # Random pages have exact ties between a gap and its threshold, which may round the other
        # way once scaled: power-of-two factors scale exactly. Any factor is checked below, on a
        # page without such ties.
        scaled = [scale_word(word, 2.0**exponent) for word in words]
        assert texts(group_words(scaled)) == texts(group_words(words))

    @given(st.floats(min_value=0.05, max_value=50))
    def test_a_page_at_any_resolution_gives_the_same_lines(self, factor: float) -> None:
        left = make_column(["one two three", "four five six", "seven eight"], 50, 100)
        right = make_column(["nine ten", "eleven twelve", "x2 y3"], 260, 105)
        words = scrambled(words_of(left + right))
        scaled = [scale_word(word, factor) for word in words]
        assert texts(group_words(scaled)) == texts(group_words(words))
