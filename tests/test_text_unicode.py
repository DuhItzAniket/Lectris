import itertools
import sys
import time
import unicodedata
from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, Revision, apply_edits
from lectris.text import unicode
from lectris.text.unicode import compatibility, invisible, ligatures, nfc


def assert_contract(text: str, revision: Revision, rule: str) -> None:
    """Edits name the rule, are sorted and apart, and turn ``text`` into the revision's text."""
    assert apply_edits(text, revision.edits) == revision.text
    assert all(edit.rule == rule for edit in revision.edits)
    assert all(a.end <= b.start for a, b in itertools.pairwise(revision.edits))


def text_with(targets: str) -> st.SearchStrategy[str]:
    """Text that mixes ``targets``, plain letters, spaces and line breaks with any character."""
    alphabet = st.one_of(st.sampled_from(targets + "ab \n"), st.characters(codec="utf-8"))
    return st.text(alphabet=alphabet, max_size=40)


COMBINING = (
    "ea\u0301\u0300\u0302\u0323\u0345\u1100\u1161\u11a8\u0b47\u0b3e\u0f73\u0f71\u0f72\u212b\u0958"
)
LIGATURES = "\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06\u0132\u00e6\u0153"
INVISIBLE = "\u00ad\u200b\u200c\u200d\u2060\ufeff\u200f\u0628\u0915 \t"
LONG_INPUTS = [
    (invisible, "a" + "\u200d" * 50_000 + "b"),
    (invisible, "\u200d\u200e" * 25_000),
    (nfc, "a" + "\u0301" * 50_000),
]
COMPATIBLE = "\uff01\uff21\uff5e\u00a0\u2009\u202f\u3000\u1680\u00b2\u2026\t"


class TestNfc:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("cafe\u0301", "caf\u00e9"),  # a letter and a combining accent
            ("\u212bngstr\u00f6m", "\u00c5ngstr\u00f6m"),  # a singleton: the angstrom sign
            ("a\u0302\u0323", "\u1ead"),  # stacked marks put in canonical order
            ("\u1100\u1161\u11a8", "\uac01"),  # Hangul jamo compose across starters
            ("\u0b47\u0b3e", "\u0b4b"),  # an Oriya vowel sign of two starters
            ("x\u0f73", "x\u0f71\u0f72"),  # a starter that decomposes to marks only
        ],
    )
    def test_text_becomes_nfc(self, text: str, expected: str) -> None:
        revision = nfc(text)
        assert revision.text == expected == unicodedata.normalize("NFC", text)
        assert_contract(text, revision, "unicode.nfc")

    def test_each_changed_sequence_is_one_edit(self) -> None:
        assert nfc("cafe\u0301 cre\u0300me").edits == (
            Edit("unicode.nfc", 3, 5, "e\u0301", "\u00e9"),
            Edit("unicode.nfc", 8, 10, "e\u0300", "\u00e8"),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "D\u00e9j\u00e0 vu, na\u00efve,\na\u00f1o, Stra\u00dfe, \u00e9t\u00e9",
            "\ufb01nal x\u00b2 \u00bd \uff21",  # compatibility characters are NFC already
        ],
    )
    def test_text_already_in_nfc_is_unchanged(self, text: str) -> None:
        assert not nfc(text).changed

    @given(text_with(COMBINING))
    def test_properties(self, text: str) -> None:
        revision = nfc(text)
        assert revision.text == unicodedata.normalize("NFC", text)
        assert_contract(text, revision, "unicode.nfc")
        assert nfc(revision.text).edits == ()
        assert revision.text.count("\n") == text.count("\n")


class TestLigatures:
    def test_each_ligature_becomes_its_letters(self) -> None:
        text = "\ufb00 \ufb01 \ufb02 \ufb03 \ufb04 \ufb05 \ufb06"
        assert ligatures(text).text == "ff fi fl ffi ffl \u017ft st"

    def test_each_ligature_is_one_edit(self) -> None:
        assert ligatures("o\ufb03ce \ufb02ow").edits == (
            Edit("unicode.ligatures", 1, 2, "\ufb03", "ffi"),
            Edit("unicode.ligatures", 5, 6, "\ufb02", "fl"),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "\u00c6sir, \u00e6ther, c\u0153ur, \u0152uvre, office",  # letters
            "\u0132sselmeer, \u0133s",  # the Dutch IJ
        ],
    )
    def test_letters_are_left_alone(self, text: str) -> None:
        assert not ligatures(text).changed

    @given(text_with(LIGATURES))
    def test_properties(self, text: str) -> None:
        revision = ligatures(text)
        assert_contract(text, revision, "unicode.ligatures")
        assert ligatures(revision.text).edits == ()
        assert not any("\ufb00" <= character <= "\ufb06" for character in revision.text)
        assert revision.text.count("\n") == text.count("\n")


class TestInvisible:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("\ufeffco\u200boper\u2060ate", "cooperate"),
            ("f\u200ci and f\u200di", "fi and fi"),  # joiners between Latin letters
            ("A\uff21\u200dB", "A\uff21B"),  # fullwidth Latin is Latin
            ("hy\u00adphen\u00adation", "hyphenation"),  # soft hyphens inside a line
            ("exam\u00ad\u200b  \nple", "exam\u00ad  \nple"),  # the line-end one stays
            ("exam\u00ad", "exam"),  # at the end of the block: no line to rejoin
            ("exam\u00ad\n\nple", "exam\n\nple"),  # a blank line: nothing to rejoin
            ("exam\u00ad\u00ad\nple", "exam\u00ad\nple"),  # only the last one is kept
        ],
    )
    def test_invisible_characters_are_removed(self, text: str, expected: str) -> None:
        revision = invisible(text)
        assert revision.text == expected
        assert_contract(text, revision, "unicode.invisible")

    def test_a_soft_hyphen_that_ends_a_line_is_kept_for_hyphenation(self) -> None:
        assert not invisible("exam\u00ad\nple").changed

    def test_adjacent_changes_are_one_edit(self) -> None:
        assert invisible("x\u200d\u200by z\u00adw").edits == (
            Edit("unicode.invisible", 1, 3, "\u200d\u200b", ""),
            Edit("unicode.invisible", 6, 7, "\u00ad", ""),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",  # Persian ZWNJ
            "\u0915\u094d\u200d\u0937",  # a Devanagari conjunct with ZWJ
            chr(0x1F468) + "\u200d" + chr(0x1F469) + "\u200d" + chr(0x1F467),  # an emoji family
            "a\u200eb, \u2067\u05e9\u05dc\u05d5\u05dd\u2069 means hello",  # bidi
        ],
    )
    def test_characters_that_shape_text_are_left_alone(self, text: str) -> None:
        assert not invisible(text).changed

    @given(text_with(INVISIBLE))
    def test_properties(self, text: str) -> None:
        revision = invisible(text)
        assert_contract(text, revision, "unicode.invisible")
        assert invisible(revision.text).edits == ()
        assert not set("\u200b\u2060\ufeff") & set(revision.text)
        for index, character in enumerate(revision.text):
            if character == "\u00ad":  # only one that ends a line remains
                assert revision.text[index + 1 :].lstrip(" \t").startswith("\n")
        assert revision.text.count("\n") == text.count("\n")


class TestCompatibility:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("\uff21\uff42\uff43\uff11 \uff08\uff41\uff09\uff0c", "Abc1 (a),"),
            ("10\u00a0km, Bonjour\u202f!", "10 km, Bonjour !"),  # no-break spaces
            ("1\u2009000\u2009000 and\u3000more", "1 000 000 and more"),
        ],
    )
    def test_forms_become_ascii(self, text: str, expected: str) -> None:
        revision = compatibility(text)
        assert revision.text == expected
        assert_contract(text, revision, "unicode.compatibility")

    def test_a_run_of_forms_is_one_edit(self) -> None:
        assert compatibility("a\u00a0\u00a0b").edits == (
            Edit("unicode.compatibility", 1, 3, "\u00a0\u00a0", "  "),
        )

    @pytest.mark.parametrize(
        "text",
        [
            "x\u00b2 + \u00bd, 1\u00aa, Brand\u2122",  # NFKC would change what these say
            "wait\u2026 \ufb01ne",  # the ellipsis and ligatures belong to other rules
            "\u1680 tab\tand\nline",  # the Ogham space mark is visible
        ],
    )
    def test_meaningful_characters_are_left_alone(self, text: str) -> None:
        assert not compatibility(text).changed

    def test_every_unicode_space_but_the_ogham_mark_becomes_a_space(self) -> None:
        spaces = [
            chr(code)
            for code in range(sys.maxunicode + 1)
            if unicodedata.category(chr(code)) == "Zs"
        ]
        changed = [space for space in spaces if compatibility(space).changed]
        assert changed == [space for space in spaces if space not in " \u1680"]
        assert {compatibility(space).text for space in changed} == {" "}

    @given(text_with(COMPATIBLE))
    def test_properties(self, text: str) -> None:
        revision = compatibility(text)
        assert_contract(text, revision, "unicode.compatibility")
        assert compatibility(revision.text).edits == ()
        assert revision.text.count("\n") == text.count("\n")
        assert len(revision.text) == len(text)


def test_the_rules_in_order_compose_what_earlier_rules_uncover() -> None:
    assert (invisible, compatibility, ligatures, nfc) == unicode.RULES
    text = "\uff21\u0301"
    for rule in unicode.RULES:
        text = rule(text).text
    assert text == "\u00c1"


@pytest.mark.parametrize(("rule", "text"), LONG_INPUTS)
def test_long_input_takes_linear_time(rule: Callable[[str], Revision], text: str) -> None:
    start = time.perf_counter()
    rule(text)
    assert time.perf_counter() - start < 2  # generous for slow CI; quadratic took minutes
