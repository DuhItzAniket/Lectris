import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.quality import Features, features, is_noise, score

LANGUAGE = [
    "The quick brown fox jumps over the lazy dog.",
    "Le cœur a ses raisons que la raison ne connaît point.",
    "Il y a un chat à la porte.",
    "Die Würde des Menschen ist unantastbar.",
    "Größe: 12 cm",
    "Chapter 3",
    "Table 2.",
    "INTRODUCTION",
    "XIV",
    "I.",
    "A",
    "e.g.",
    "(a)",
    "[12]",
    "§ 5",
    "Total 1,250.00 USD",
    "12.04.1998",
    "+49 (0)30 1234-5678",
    "1000000",
    "- 12 -",
    "- 3 -",
    "J. R. R. Tolkien",
    "www.example.com",
    "BBC NBC CNN",
    "LaTeX",
    "Hmmmm.",
    "Introduction .......... 1",
    "Index . . . . . . . . . . . . 245",
    "Index ........................................ 312",
    "def main(argv: list[str]) -> int:",
    "for (int i = 0; i < n; i++) {",
    "x = y + 1;",
    "} else {",
    # One-character tokens that are content: formulas, abbreviations, table rows, labels.
    "x = y + z",
    "V = I R",
    "a = b + c",
    "R & D",
    "Q & A",
    "| a | b |",
    "A B C D",
    "x y z",
    "1 : 1",
]

NOISE = [
    "~~~ ,,, ' ' |||",
    ".:;:.:;",
    "lllllllll",
    "@#%&*",
    "i i i ! l ; :",
    "' . , ' .",
    "J\\ ,(' r~ ;. -",
    "IIIIIIII",
    "_______________",
    "____",
    "|||||",
]


@pytest.mark.parametrize("text", LANGUAGE)
def test_language_is_not_noise(text: str) -> None:
    assert not is_noise(text)


@pytest.mark.parametrize("text", NOISE)
def test_noise_is_noise(text: str) -> None:
    assert is_noise(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The quick brown fox jumps over the lazy dog.", 1.0),
        ("- 12 -", 1.0),  # "-" is an operator, "12" content
        ("- 3 -", 1 - 4 / 15),  # 2/3 of the characters are symbols
        ("x = y + z", 1 - 0.6 * 0.2),  # 3 of 5 tokens lone lowercase letters
        ("x y z", 0.4),  # only lone lowercase letters: the single-character penalty alone
        ("1 : 1", 0.7),  # only thin glyphs: the thin-glyph penalty alone
        ("i i i ! l ; :", 0.1),  # both: only lone lowercase letters and marks, all thin
        ("BBC NBC CNN", 0.7),  # no vowel in 9 letters
        ("LaTeX", 0.6),  # 2 case switches in 5 letters
        ("@#%&*", 0.0),  # only symbols, and one token
        ("lllllllll", 0.0),  # one letter repeated, no vowel
        ("* * *", 0.0),  # a spaced leader: one symbol
    ],
)
def test_scores(text: str, expected: float) -> None:
    assert score(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "   ", "\t\n", "\u200b"])
def test_text_with_nothing_visible_scores_1_and_is_not_noise(text: str) -> None:
    assert score(text) == 1.0
    assert not is_noise(text)


def test_the_threshold_decides() -> None:
    assert not is_noise("x y z")
    assert is_noise("x y z", threshold=0.5)
    assert not is_noise("@#%&*", threshold=0.0)


@pytest.mark.parametrize("text", ["x y z", "u v w", "a b c d e f g h", "x ? y ( z"])
def test_the_single_character_penalty_alone_leaves_0_4(text: str) -> None:
    assert score(text) == pytest.approx(0.4)


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_a_threshold_outside_0_and_1_is_refused(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        is_noise("text", threshold=threshold)


class TestFeatures:
    def test_counts(self) -> None:
        measured = features("Hello, wörld!! 42")
        assert measured == Features(
            length=14,
            letters=10,
            digits=2,
            symbols=2,  # "," and "!!" collapsed to one "!"
            tokens=3,
            vowels=3,
            single_char_tokens=0,
            thin_glyphs=5,  # l l , l !
            longest_run=2,
            longest_thin_run=2,  # the l l of Hello
            case_switches=0,
        )
        assert measured.letter_ratio == pytest.approx(10 / 14)
        assert measured.digit_ratio == pytest.approx(2 / 14)
        assert measured.symbol_ratio == pytest.approx(2 / 14)
        assert measured.vowel_ratio == pytest.approx(3 / 10)
        assert measured.mean_token_length == pytest.approx(14 / 3)
        assert measured.thin_glyph_ratio == pytest.approx(5 / 14)

    def test_nothing_visible_gives_zeros(self) -> None:
        measured = features(" \n ")
        assert measured == Features(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        assert measured.letter_ratio == measured.vowel_ratio == measured.single_char_ratio == 0.0
        assert measured.mean_token_length == 0.0

    @pytest.mark.parametrize(
        "variant", ["Index .......... 245", "Index . . . . . 245", "Index ....  .... 245"]
    )
    def test_a_leader_counts_as_one_symbol_and_one_token(self, variant: str) -> None:
        assert features(variant) == features("Index . 245")

    def test_decomposed_and_invisible_characters_do_not_count(self) -> None:
        assert features("cafe\u0301 au lait") == features("café au lait")
        assert features("in\u200bvisible\u00ad") == features("invisible")

    @pytest.mark.parametrize(
        ("text", "run"), [("Aaaah", 4), ("Schifffahrt", 3), ("1000000", 0), ("----", 0)]
    )
    def test_the_longest_run_is_of_one_letter_ignoring_case(self, text: str, run: int) -> None:
        assert features(text).longest_run == run

    @pytest.mark.parametrize(("text", "switches"), [("LaTeX", 2), ("McDonald", 1), ("Hello", 0)])
    def test_case_switches_are_lower_then_upper(self, text: str, switches: int) -> None:
        assert features(text).case_switches == switches

    def test_vowels_include_accents_and_ligatures(self) -> None:
        measured = features("éÀœøy")
        assert (measured.letters, measured.vowels) == (5, 5)

    def test_single_digits_are_not_single_character_tokens(self) -> None:
        measured = features("1 2 3 a ;")
        assert (measured.tokens, measured.single_char_tokens) == (5, 2)
        assert measured.single_char_ratio == pytest.approx(2 / 5)

    def test_lone_capitals_and_operators_are_not_single_character_tokens(self) -> None:
        measured = features("A = b | ; - x & Q")
        assert (measured.tokens, measured.single_char_tokens) == (9, 3)  # b ; x


@given(st.text(max_size=80))
def test_a_score_is_between_0_and_1(text: str) -> None:
    measured = features(text)
    assert measured.letters + measured.digits + measured.symbols == measured.length
    assert 0.0 <= score(text) <= 1.0


@pytest.mark.parametrize("interjection", ["Mmmm", "Zzzz", "Ahhhh", "Hmmmm.", "Brrr!", "Shhh"])
def test_an_interjection_is_not_noise(interjection: str) -> None:
    assert not is_noise(interjection)


@pytest.mark.parametrize("specks", ["lllllllll", "IIIIIIII", "iiiii", "zzzzzzzzzzzz"])
def test_a_run_of_thin_letters_or_a_very_long_run_is_noise(specks: str) -> None:
    assert is_noise(specks)


def test_the_thin_run_counts_only_i_and_l() -> None:
    assert features("Hmmmm lllll").longest_thin_run == 5
    assert features("Hmmmm").longest_thin_run == 0
    assert features("Hmmmm").longest_run == 4
