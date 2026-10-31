import random
import string
import time
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.distance import ocr_distance
from lectris.errors import FormatError
from lectris.lexicon import Lexicon


class TestBuilding:
    def test_each_occurrence_of_a_word_counts_one(self) -> None:
        lexicon = Lexicon(["the", "cat", "the"])
        assert len(lexicon) == 2
        assert lexicon.frequency("the") == 2
        assert lexicon.frequency("cat") == 1

    def test_a_mapping_gives_the_counts(self) -> None:
        lexicon = Lexicon({"the": 812, "cat": 3, "rare": 0})
        assert lexicon.frequency("the") == 812
        assert "rare" in lexicon
        assert lexicon.frequency("rare") == 0

    def test_case_is_ignored_by_default(self) -> None:
        lexicon = Lexicon({"Paris": 2, "paris": 3})
        assert "PARIS" in lexicon
        assert len(lexicon) == 1
        assert lexicon.frequency("pArIs") == 5
        assert not lexicon.case_sensitive

    def test_a_case_sensitive_lexicon_keeps_the_forms_apart(self) -> None:
        lexicon = Lexicon({"Paris": 2, "paris": 3}, case_sensitive=True)
        assert len(lexicon) == 2
        assert "PARIS" not in lexicon
        assert lexicon.frequency("Paris") == 2

    def test_an_absent_word_has_no_count(self) -> None:
        lexicon = Lexicon(["cat"])
        assert "dog" not in lexicon
        assert lexicon.frequency("dog") == 0
        assert 42 not in lexicon

    @pytest.mark.parametrize("word", ["", " ", "two words", "tab\tword", " padded"])
    def test_a_word_is_one_token(self, word: str) -> None:
        with pytest.raises(ValueError, match="one non-empty token"):
            Lexicon([word])

    def test_a_word_is_a_string(self) -> None:
        with pytest.raises(TypeError, match="string"):
            Lexicon(cast("list[str]", [42]))

    @pytest.mark.parametrize(
        ("count", "error"), [(-1, ValueError), (1.5, TypeError), (True, TypeError)]
    )
    def test_a_count_is_a_non_negative_integer(self, count: object, error: type) -> None:
        with pytest.raises(error, match="count"):
            Lexicon(cast("dict[str, int]", {"cat": count}))


class TestFromLines:
    def test_words_counts_comments_and_blank_lines(self) -> None:
        lexicon = Lexicon.from_lines(
            ["# a word list", "the\t812", "  modern   12  ", "", "   ", "modem", "the 8\n"]
        )
        assert len(lexicon) == 3
        assert lexicon.frequency("the") == 820
        assert lexicon.frequency("modern") == 12
        assert lexicon.frequency("modem") == 1

    @pytest.mark.parametrize("line", ["modern 12 extra", "modern twelve", "modern -3", "a 1.5"])
    def test_a_malformed_line_is_named(self, line: str) -> None:
        with pytest.raises(FormatError, match="line 2: expected a word and an optional count"):
            Lexicon.from_lines(["the", line])


class TestFromFile:
    def test_a_utf8_file_is_read(self, tmp_path: Path) -> None:
        path = tmp_path / "words.txt"
        path.write_text("# French\ncafé 3\nNaïve\n", encoding="utf-8")
        lexicon = Lexicon.from_file(path)
        assert lexicon.frequency("CAFÉ") == 3
        assert "naïve" in lexicon

    def test_a_byte_order_mark_is_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "words.txt"
        path.write_bytes(b"\xef\xbb\xbfthe 5\n")
        assert Lexicon.from_file(str(path)).frequency("the") == 5

    def test_a_malformed_file_names_itself_and_the_line(self, tmp_path: Path) -> None:
        path = tmp_path / "words.txt"
        path.write_text("the\nmodern 12 extra\n", encoding="utf-8")
        with pytest.raises(FormatError, match=r"words\.txt: line 2"):
            Lexicon.from_file(path)

    def test_a_file_that_is_not_utf8_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "latin1.txt"
        path.write_bytes("café\n".encode("latin-1"))
        with pytest.raises(FormatError, match="not UTF-8"):
            Lexicon.from_file(path)

    def test_a_missing_file_is_an_os_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            Lexicon.from_file(tmp_path / "missing.txt")


class TestSuggest:
    def test_distance_then_count_then_alphabet(self) -> None:
        lexicon = Lexicon({"cat": 1, "bat": 5, "hat": 5, "cast": 9, "dog": 100})
        assert lexicon.suggest("cat") == ("cat", "cast", "bat", "hat")
        assert lexicon.suggest("cat", limit=2) == ("cat", "cast")

    def test_an_ocr_confusion_outranks_a_more_frequent_word(self) -> None:
        lexicon = Lexicon({"modern": 1, "modem": 50, "modest": 500})
        assert lexicon.suggest("rnodern") == ("modern", "modem")

    def test_max_distance_bounds_the_results(self) -> None:
        lexicon = Lexicon(["word", "ward", "wordy"])
        assert lexicon.suggest("vvord", max_distance=0.25) == ("word",)
        assert lexicon.suggest("word", max_distance=0) == ("word",)
        assert Lexicon().suggest("word") == ()

    def test_case_insensitive_suggestions_are_lower_case(self) -> None:
        assert Lexicon(["Boston"]).suggest("B0STON") == ("boston",)

    def test_capital_confusions_need_a_case_sensitive_lexicon(self) -> None:
        # "8" and "B" are confused; "8" and "b" are not, and a case-insensitive lexicon compares
        # lower-cased forms.
        assert Lexicon(["BOX"], case_sensitive=True).suggest("8OX", max_distance=0.5) == ("BOX",)
        assert Lexicon(["BOX"]).suggest("8OX", max_distance=0.5) == ()

    def test_words_that_start_with_the_last_code_point_are_skipped_correctly(self) -> None:
        last = chr(0x10FFFF)
        lexicon = Lexicon(["a", last, last + "a", last + "b", last + last], case_sensitive=True)
        assert lexicon.suggest("a", max_distance=0) == ("a",)
        assert lexicon.suggest(last + "c", max_distance=1) == (
            last,
            last + "a",
            last + "b",
            last + last,
        )

    @pytest.mark.parametrize(("max_distance", "limit"), [(-0.5, 5), (float("nan"), 5), (1.0, 0)])
    def test_invalid_arguments_are_refused(self, max_distance: float, limit: int) -> None:
        with pytest.raises(ValueError, match="at least"):
            Lexicon(["word"]).suggest("word", max_distance=max_distance, limit=limit)

    @given(
        st.lists(st.text(alphabet="rnmcldvwV01IlO5Sbhiea", min_size=1, max_size=6), max_size=40),
        st.text(alphabet="rnmcldvwV01IlO5Sbhiea", max_size=6),
        st.sampled_from([0.0, 0.25, 0.5, 1.0, 1.5, 2.0]),
    )
    def test_the_search_finds_exactly_the_words_within_range(
        self, words: list[str], query: str, max_distance: float
    ) -> None:
        lexicon = Lexicon(words, case_sensitive=True)
        expected = sorted(
            (ocr_distance(query, word), -lexicon.frequency(word), word)
            for word in set(words)
            if ocr_distance(query, word) <= max_distance
        )
        found = lexicon.suggest(query, max_distance=max_distance, limit=len(words) + 1)
        assert found == tuple(word for _, _, word in expected)

    def test_a_large_lexicon_is_searched_quickly(self) -> None:
        generator = random.Random(0)  # noqa: S311 - reproducible test words, not secrets
        words = [
            "".join(generator.choices(string.ascii_lowercase, k=generator.randint(3, 12)))
            for _ in range(50_000)
        ]
        lexicon = Lexicon([*words, "information"])
        started = time.perf_counter()
        for query in ("informatiom", "rnodern", "the", "lexicon", "qwertyuiopas"):
            lexicon.suggest(query)
        assert lexicon.suggest("infornation")[0] == "information"
        assert time.perf_counter() - started < 2.0
