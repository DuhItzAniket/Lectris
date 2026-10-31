import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.distance import OCR_COSTS, damerau_levenshtein, levenshtein, ocr_distance

# Characters that take part in the table's confusions, plus a few that do not.
CONFUSABLE = "rnmcldvwVW01IoOS5B8Z2b6euh|ax"
words = st.text(alphabet="abcxyz", max_size=8)
ocr_words = st.text(alphabet=CONFUSABLE, max_size=8)


class TestLevenshtein:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("", "", 0),
            ("abc", "", 3),
            ("", "abc", 3),
            ("kitten", "sitting", 3),
            ("flaw", "lawn", 2),
            ("ab", "ba", 2),
            ("same", "same", 0),
        ],
    )
    def test_known_values(self, a: str, b: str, expected: int) -> None:
        assert levenshtein(a, b) == expected

    @given(words, words)
    def test_it_is_symmetric_and_zero_only_for_equal_strings(self, a: str, b: str) -> None:
        assert levenshtein(a, b) == levenshtein(b, a)
        assert (levenshtein(a, b) == 0) == (a == b)

    @given(words, words, words)
    def test_it_obeys_the_triangle_inequality(self, a: str, b: str, c: str) -> None:
        assert levenshtein(a, c) <= levenshtein(a, b) + levenshtein(b, c)

    @given(words, words)
    def test_it_is_bounded_by_the_lengths(self, a: str, b: str) -> None:
        assert abs(len(a) - len(b)) <= levenshtein(a, b) <= max(len(a), len(b))


class TestDamerauLevenshtein:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("ab", "ba", 1),
            ("form", "from", 1),
            ("abcdef", "abdcef", 1),
            ("", "ab", 2),
            # The optimal string alignment variant: the unrestricted distance would be 2.
            ("ca", "abc", 3),
        ],
    )
    def test_known_values(self, a: str, b: str, expected: int) -> None:
        assert damerau_levenshtein(a, b) == expected

    @given(words, words)
    def test_a_transposition_saves_at_most_half(self, a: str, b: str) -> None:
        distance = damerau_levenshtein(a, b)
        assert distance == damerau_levenshtein(b, a)
        assert distance <= levenshtein(a, b) <= 2 * distance


class TestOcrDistance:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("modern", "rnodern", 0.25),
            ("word", "vvord", 0.25),
            ("WORD", "VVORD", 0.25),
            ("B0ston", "Boston", 0.5),
            ("tlie", "the", 0.5),
            ("dear", "clear", 0.5),
            ("l1I", "lll", 0.5),
            ("cat", "dog", 3.0),
            ("", "abc", 3.0),
            ("same", "same", 0.0),
        ],
    )
    def test_known_values(self, a: str, b: str, expected: float) -> None:
        assert ocr_distance(a, b) == expected

    def test_a_confusion_ranks_above_an_unrelated_edit(self) -> None:
        assert ocr_distance("rnodern", "modern") < ocr_distance("rnodern", "modest")

    def test_the_default_table_is_symmetric_and_read_only(self) -> None:
        for (seen, meant), cost in OCR_COSTS.items():
            assert OCR_COSTS[meant, seen] == cost
            assert 0 < cost < 1
        with pytest.raises(TypeError):
            OCR_COSTS["a", "b"] = 0.5  # type: ignore[index]

    def test_a_custom_table_is_read_in_its_own_direction(self) -> None:
        costs = {("ab", "x"): 0.125}
        assert ocr_distance("ab", "x", costs=costs) == 0.125
        assert ocr_distance("x", "ab", costs=costs) == 2.0
        assert ocr_distance("rn", "m", costs={}) == 2.0

    @pytest.mark.parametrize(
        "costs",
        [
            {("", "a"): 0.5},
            {("a", "a"): 0.5},
            {("a", "b"): -0.5},
            {("a", "b"): math.nan},
            {("a", "b"): math.inf},
        ],
    )
    def test_an_invalid_table_is_refused(self, costs: dict[tuple[str, str], float]) -> None:
        with pytest.raises(ValueError, match="cost"):
            ocr_distance("a", "b", costs=costs)

    @given(ocr_words, ocr_words)
    def test_it_never_exceeds_levenshtein(self, a: str, b: str) -> None:
        assert ocr_distance(a, b) <= levenshtein(a, b)

    @given(ocr_words, ocr_words)
    def test_it_is_symmetric_and_zero_only_for_equal_strings(self, a: str, b: str) -> None:
        assert ocr_distance(a, b) == ocr_distance(b, a)
        assert (ocr_distance(a, b) == 0) == (a == b)

    def test_it_is_not_a_metric(self) -> None:
        # Two confusions that share a character do not chain: "u" read as "n", then "rn" as "m".
        assert ocr_distance("ru", "m") > ocr_distance("ru", "rn") + ocr_distance("rn", "m")
