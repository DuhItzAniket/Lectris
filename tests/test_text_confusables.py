import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, apply_edits
from lectris.lexicon import Lexicon
from lectris.text.confusables import IN_NUMBERS, IN_WORDS, RULES, in_numbers, in_words


class TestInNumbers:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1O5", "105"),
            ("a total of 2,5OO.", "a total of 2,500."),
            ("in 2O24, sales", "in 2024, sales"),
            ("(1O5%)", "(105%)"),
            ("$1,2O0.5O due", "$1,200.50 due"),
            ("-3.1O", "-3.10"),
            ("1l5 kg", "115 kg"),
            ("1o5 and 2I3", "105 and 213"),
            ("ISO 9OO1", "ISO 9001"),
        ],
    )
    def test_letters_inside_a_number_become_digits(self, text: str, expected: str) -> None:
        assert in_numbers(text).text == expected

    @pytest.mark.parametrize(
        "text",
        [
            "vitamin B12",
            "the I95 north",
            "model l23",
            "flat 10B",
            "THE 1980S",
            "a 50l tank",
            "it was 10o outside",
            "postcode K1A 0B1",
            "a 1S0 code",
            "Part no. 12B34",
            "serial 10S20",
            "in 19B5",
            "an A4 sheet",
            "COVID-19",
            "0x1O5",
            "1O5kg",
            "1O is one digit",
            "at 1O:3O",
            "v1.O",
            "12|34",
            "SOS BOSS IOI",
            "1..O5",
        ],
    )
    def test_codes_and_words_are_left_alone(self, text: str) -> None:
        assert in_numbers(text).edits == ()

    def test_one_edit_per_number(self) -> None:
        revision = in_numbers("from 1O5 to 2O6")
        assert revision.edits == (
            Edit(IN_NUMBERS, 5, 8, "1O5", "105"),
            Edit(IN_NUMBERS, 12, 15, "2O6", "206"),
        )


class TestInWordsWithoutLexicon:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("the c0mputer", "the computer"),
            ("I d0n't know", "I don't know"),
            ("one w0rd", "one word"),
            ("Mr McD0nald", "Mr McDonald"),
        ],
    )
    def test_0_between_letters_becomes_o(self, text: str, expected: str) -> None:
        assert in_words(text).text == expected

    @pytest.mark.parametrize(
        "text",
        [
            "hell0 there",
            "a s1mple test",
            "say he1lo",
            "log1p",
            "ref KX0QZ",
            "0nly once",
            "B0STON",
            "5treet",
            "an mp3 file",
            "h264 video",
            "x86 code",
            "the 4th of",
            "1st place",
            "a 2D plot",
            "B2B sales",
            "so c00l",
            "foo_b0r()",
            "Win10",
            "l10n and i18n",
            "a1b",
        ],
    )
    def test_other_digits_and_positions_need_a_lexicon(self, text: str) -> None:
        assert in_words(text).edits == ()


class TestInWordsWithLexicon:
    LEXICON = Lexicon(
        {
            "word": 50,
            "india": 3,
            "like": 90,
            "oxford": 2,
            "boston": 4,
            "hello": 30,
            "street": 7,
            "simple": 6,
        }
    )

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1ndia", "india"),
            ("a s1mple test", "a simple test"),
            ("he1lo", "hello"),
            ("I 1ike it", "I like it"),
            ("hell0", "hello"),
            ("Hell0", "Hello"),
            ("B0STON", "BOSTON"),
            ("8OSTON", "BOSTON"),
            ("8oston", "Boston"),
            ("5treet", "street"),
            ("0xford", "oxford"),
            ("w0rd", "word"),
        ],
    )
    def test_a_reading_the_lexicon_confirms_is_taken(self, text: str, expected: str) -> None:
        assert in_words(text, lexicon=self.LEXICON).text == expected

    @pytest.mark.parametrize("text", ["c0mputer", "w0rds", "log1p", "1st", "x86"])
    def test_a_reading_the_lexicon_does_not_confirm_is_not(self, text: str) -> None:
        assert in_words(text, lexicon=self.LEXICON).edits == ()

    def test_a_case_sensitive_lexicon_chooses_the_capital(self) -> None:
        lexicon = Lexicon(["Oxford", "India"], case_sensitive=True)
        assert in_words("0xford", lexicon=lexicon).text == "Oxford"
        assert in_words("1ndia", lexicon=lexicon).text == "India"

    def test_the_more_frequent_reading_wins_and_a_tie_leaves_the_token(self) -> None:
        assert in_words("1one", lexicon=Lexicon({"lone": 2, "ione": 5})).text == "ione"
        assert in_words("1one", lexicon=Lexicon({"lone": 5, "ione": 2})).text == "lone"
        assert in_words("1one", lexicon=Lexicon({"lone": 2, "ione": 2})).edits == ()

    def test_a_token_the_lexicon_knows_is_kept(self) -> None:
        lexicon = Lexicon(["n00b", "noob"])
        assert in_words("n00b", lexicon=lexicon).edits == ()

    def test_a_token_with_many_digits_is_not_a_word(self) -> None:
        lexicon = Lexicon(["lillillil"])
        assert in_words("l1ll1ll1l", lexicon=lexicon).text == "lillillil"
        assert in_words("1i11i11i1", lexicon=lexicon).edits == ()

    def test_edits_carry_the_rule(self) -> None:
        revision = in_words("the w0rd", lexicon=self.LEXICON)
        assert revision.edits == (Edit(IN_WORDS, 4, 8, "w0rd", "word"),)


def test_rules_lists_numbers_then_words() -> None:
    assert (in_numbers, in_words) == RULES


texts = st.text(alphabet="0158OolISBabcdD .,'_-\n", max_size=40)
lexicons = st.sampled_from([None, Lexicon(["boss", "obb", "lol", "solo", "bob", "abs"])])


@given(texts)
def test_in_numbers_keeps_the_rule_contract(text: str) -> None:
    revision = in_numbers(text)
    assert apply_edits(text, revision.edits) == revision.text
    assert in_numbers(revision.text).edits == ()
    assert revision.text.count("\n") == text.count("\n")


@given(texts, lexicons)
def test_in_words_keeps_the_rule_contract(text: str, lexicon: Lexicon | None) -> None:
    revision = in_words(text, lexicon=lexicon)
    assert apply_edits(text, revision.edits) == revision.text
    assert in_words(revision.text, lexicon=lexicon).edits == ()
    assert revision.text.count("\n") == text.count("\n")
