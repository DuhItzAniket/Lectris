import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, apply_edits
from lectris.lexicon import Lexicon
from lectris.text.hyphenation import RULE, RULES, join

SOFT_HYPHEN = chr(0xAD)
HYPHEN = chr(0x2010)
NON_BREAKING_HYPHEN = chr(0x2011)
NOT_SIGN = chr(0xAC)
DOUBLE_OBLIQUE_HYPHEN = chr(0x2E17)


class TestWithoutLexicon:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("the infor-\nmation is here", "the information\nis here"),
            ("an exam-\nple, which", "an example,\nwhich"),
            ("the (infor-\nmation) here", "the (information)\nhere"),
            ("in the docu-\nment's title", "in the document's\ntitle"),
            ("l'infor-\nmation est", "l'information\nest"),
            ("her gold-\nen hair", "her golden\nhair"),
            ("a chick-\nen and a pock-\net watch", "a chicken\nand a pocket\nwatch"),
            ("Infor-\nmation is", "Information\nis"),
            ("the infor-  \n  mation is", "the information\n  is"),
            (f"the infor{HYPHEN}\nmation is", "the information\nis"),
            (f"the infor{NON_BREAKING_HYPHEN}\nmation is", "the information\nis"),
            (f"the spar{NOT_SIGN}\nrows fly", "the sparrows\nfly"),
            (f"die Zei{DOUBLE_OBLIQUE_HYPHEN}\ntung von", "die Zeitung\nvon"),
            (
                "a long infor-\nmation line with a docu-\nment in it",
                "a long information\nline with a document\nin it",
            ),
        ],
    )
    def test_a_word_split_at_a_line_end_is_joined(self, text: str, expected: str) -> None:
        assert join(text).text == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("the infor-\nmation.", "the\ninformation."),
            ("it was the infor-\nmation", "it was the\ninformation"),
        ],
    )
    def test_the_break_moves_before_a_word_that_ends_the_block(
        self, text: str, expected: str
    ) -> None:
        assert join(text).text == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Franco-\nGerman relations",
            "an e-\nmail to",
            "state-of-the-\nart design",
            "NATO-\nled forces",
            "INFOR-\nMATION ABOUT",
            "the covid19-\nrelated cases",
            "the infor-\n2nd edition",
            "a dash - \nthen more",
            "the infor- mation on one line",
            "the infor-\n\nmation in a new paragraph",
            "the infor-\n   \nmation",
            "infor-\nmation",
            "co-\nop-\nera-\ntion",
            "the co-\nop-\neration is",
            "the infor-\nmation-\nrich",
        ],
    )
    def test_without_evidence_the_text_is_left_alone(self, text: str) -> None:
        assert join(text).edits == ()

    @pytest.mark.parametrize(
        "text",
        [
            "pre-\nand post-war prices",
            "Ein-\nund Ausgang",
            "high-\nor low-level",
            "my mother-\nin-law",
            "c'est-\nà-dire",
            "the infor-\nmation-rich source",
            f"the infor-\nmation{NOT_SIGN}rich",
            "Que fait-\nil ici ?",
            "Il peut-\nêtre venu",
            "Qu'est-\nce que c'est",
            "celle-\nci est",
        ],
    )
    def test_conjunctions_clitics_and_compounds_keep_the_hyphen(self, text: str) -> None:
        assert join(text).edits == ()

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (f"the infor{SOFT_HYPHEN}\nMation is", "the inforMation\nis"),
            (f"an e{SOFT_HYPHEN}\nmail to", "an email\nto"),
        ],
    )
    def test_a_soft_hyphen_at_a_line_end_is_always_joined(self, text: str, expected: str) -> None:
        assert join(text).text == expected

    def test_each_join_is_one_edit_in_the_input(self) -> None:
        text = "the infor-\nmation is\nthe docu-\nment"
        revision = join(text)
        assert revision.edits == (
            Edit(RULE, 9, 18, "-\nmation ", "mation\n"),
            Edit(RULE, 24, 31, " docu-\n", "\ndocu"),
        )
        assert revision.text == "the information\nis\nthe\ndocument"


class TestWithLexicon:
    @pytest.mark.parametrize(
        ("text", "words", "expected"),
        [
            ("the sub-\nmarine is", {"submarine": 1}, "the submarine\nis"),
            ("Infor-\nmation is", {"information": 1}, "Information\nis"),
            ("an e-\nmail to", {"email": 1}, "an email\nto"),
            ("an e-\nmail to", {"email": 9, "e-mail": 2}, "an email\nto"),
            ("an e-\nmail to", {"email": 2, "e-mail": 9}, "an e-\nmail to"),
            ("an e-\nmail to", {"email": 1, "e-mail": 1}, "an e-\nmail to"),
            ("a well-\nknown fact", {"well-known": 1, "well": 1}, "a well-\nknown fact"),
            ("a self-\naware man", {"self": 1, "aware": 1}, "a self-\naware man"),
            ("the infor-\nmation is", {"unrelated": 1}, "the information\nis"),
            ("an e-\nmail to", {"unrelated": 1}, "an e-\nmail to"),
            ("Franco-\nGerman ties", {"francogerman": 1}, "Franco-\nGerman ties"),
            ("pre-\nand post-war prices", {"unrelated": 1}, "pre-\nand post-war prices"),
            ("Que fait-\nil ici", {"fait": 1}, "Que fait-\nil ici"),
            ("a ner-\nvous man", {"nervous": 1}, "a nervous\nman"),
            ("a ner-\nvous man", {"unrelated": 1}, "a ner-\nvous man"),
        ],
    )
    def test_the_lexicon_decides(self, text: str, words: dict[str, int], expected: str) -> None:
        assert join(text, lexicon=Lexicon(words)).text == expected

    def test_a_case_sensitive_lexicon_is_consulted_as_written(self) -> None:
        text = "Self-\naware people"
        assert join(text, lexicon=Lexicon(["self", "aware"])).edits == ()
        sensitive = Lexicon(["self", "aware"], case_sensitive=True)
        assert join(text, lexicon=sensitive).text == "Selfaware\npeople"


def test_rules_lists_the_rule() -> None:
    assert (join,) == RULES


TOKENS = [
    "ab-",
    "a-",
    "ab",
    "b",
    "Ab",
    "and",
    "il",
    f"ab{SOFT_HYPHEN}",
    f"ab{HYPHEN}",
    f"ab{NOT_SIGN}",
    "ab.",
    "(ab-",
    "ab-b",
]
texts = st.lists(
    st.lists(st.sampled_from(TOKENS), max_size=3).map(" ".join), min_size=1, max_size=6
).map("\n".join)
lexicons = st.sampled_from(
    [None, Lexicon(["abab", "ab-b", "b"]), Lexicon({"abab": 2, "ab-ab": 3, "ab": 1})]
)


@given(texts, lexicons)
def test_the_rule_contract_holds(text: str, lexicon: Lexicon | None) -> None:
    revision = join(text, lexicon=lexicon)
    assert apply_edits(text, revision.edits) == revision.text
    assert all(edit.rule == RULE for edit in revision.edits)
    assert join(revision.text, lexicon=lexicon).edits == ()
    assert revision.text.count("\n") == text.count("\n")
    blank = [not line.strip() for line in text.split("\n")]
    assert [not line.strip() for line in revision.text.split("\n")] == blank
