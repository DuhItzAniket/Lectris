from collections import Counter
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.metrics import (
    ErrorCounts,
    cer,
    char_errors,
    confusions,
    wer,
    word_errors,
)


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        diagonal, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            diagonal, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, diagonal + (x != y))
    return row[-1]


@pytest.mark.parametrize(
    ("reference", "hypothesis", "counts", "rate"),
    [
        ("kitten", "sitting", ErrorCounts(2, 0, 1, 6), 3 / 6),
        ("abc", "abc", ErrorCounts(0, 0, 0, 3), 0.0),
        ("abc", "", ErrorCounts(0, 3, 0, 3), 1.0),
        ("ab", "abcdef", ErrorCounts(0, 0, 4, 2), 2.0),
        ("tool box", "too1box", ErrorCounts(1, 1, 0, 8), 2 / 8),
        ("", "", ErrorCounts(0, 0, 0, 0), 0.0),
    ],
)
def test_character_errors(
    reference: str, hypothesis: str, counts: ErrorCounts, rate: float
) -> None:
    assert char_errors(reference, hypothesis) == counts
    assert cer(reference, hypothesis) == pytest.approx(rate)


@pytest.mark.parametrize(
    ("reference", "hypothesis", "counts", "rate"),
    [
        ("the cat sat on the mat", "the cat sit on mat", ErrorCounts(1, 1, 0, 6), 2 / 6),
        ("one two", "one  two\nthree", ErrorCounts(0, 0, 1, 2), 1 / 2),
        ("one two", "", ErrorCounts(0, 2, 0, 2), 1.0),
    ],
)
def test_word_errors(reference: str, hypothesis: str, counts: ErrorCounts, rate: float) -> None:
    assert word_errors(reference, hypothesis) == counts
    assert wer(reference, hypothesis) == pytest.approx(rate)


def test_an_empty_reference_has_no_rate_unless_the_hypothesis_is_empty() -> None:
    assert char_errors("", "abc") == ErrorCounts(0, 0, 3, 0)
    with pytest.raises(ValueError, match="empty reference"):
        cer("", "abc")
    with pytest.raises(ValueError, match="empty reference"):
        wer(" ", "word")
    assert wer("", "  ") == 0.0


def test_normalize_composes_and_collapses_whitespace() -> None:
    decomposed = "cafe\u0301  au\tlait "
    assert cer("café au lait", decomposed) == pytest.approx(5 / 12)
    assert cer("café au lait", decomposed, normalize=True) == 0.0
    assert wer("café au lait", decomposed) == pytest.approx(1 / 3)
    assert wer("café au lait", decomposed, normalize=True) == 0.0


def test_case_is_kept_unless_ignored() -> None:
    assert cer("Hello", "hello") == pytest.approx(1 / 5)
    assert cer("Hello", "hello", ignore_case=True) == 0.0
    assert wer("The Cat", "the cat", ignore_case=True) == 0.0
    assert char_errors("Straße", "STRASSE", ignore_case=True) == ErrorCounts(0, 0, 0, 7)


def test_confusions_count_substituted_pairs() -> None:
    assert confusions("SOLID", "S0L1D") == Counter({("O", "0"): 1, ("I", "1"): 1})
    assert confusions("ill fill", "i11 fi11") == Counter({("l", "1"): 4})
    assert confusions("m", "rn") == Counter({("m", "n"): 1})
    assert confusions("Abc", "abc", ignore_case=True) == Counter()


class TestErrorCounts:
    def test_errors_and_rate(self) -> None:
        counts = ErrorCounts(substitutions=2, deletions=1, insertions=3, reference_length=4)
        assert counts.errors == 6
        assert counts.rate == 1.5

    @pytest.mark.parametrize("values", [(-1, 0, 0, 3), (0, 0, -1, 3), (0, 0, 0, -1), (2, 2, 0, 3)])
    def test_impossible_counts_are_refused(self, values: tuple[int, int, int, int]) -> None:
        with pytest.raises(ValueError, match=r"0 or more|do not fit"):
            ErrorCounts(*values)


texts = st.text(alphabet="ab c", max_size=25)


@given(texts, texts)
def test_errors_are_the_levenshtein_distance(reference: str, hypothesis: str) -> None:
    characters = char_errors(reference, hypothesis)
    assert characters.errors == levenshtein(reference, hypothesis)
    assert characters.errors == char_errors(hypothesis, reference).errors
    assert characters.reference_length == len(reference)
    words = word_errors(reference, hypothesis)
    assert words.errors == levenshtein(reference.split(), hypothesis.split())


@given(texts)
def test_a_text_against_itself_has_no_errors(text: str) -> None:
    assert char_errors(text, text) == ErrorCounts(0, 0, 0, len(text))
    assert cer(text, text) == 0.0
