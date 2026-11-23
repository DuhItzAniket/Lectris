"""Baseline B2 (protocol §6): the lexicon corrector."""

from lectris import clean
from lectris.edits import Candidate
from lectris.eval.experiment import LEXICON, POLICIES
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document, Line, Page
from lectris.models import pack
from lectris.propose import Lexical

WORDS = Lexicon({"the": 9, "hives": 5, "hides": 2, "bees": 5, "late": 3})


def test_lexical_candidates_carry_their_rank() -> None:
    found = Lexical(WORDS)("the hves")
    assert [(c.after, c.feature("lexical_rank", -1)) for c in found] == [("hives", 0.0)]
    both = Lexical(WORDS)("the hiaes")
    assert [(c.after, c.feature("lexical_rank", -1)) for c in both] == [
        ("hives", 0.0),
        ("hides", 1.0),
    ]


def test_the_policy_accepts_only_the_first_lexical_candidate() -> None:
    first = Candidate("lexical.word", 0, 4, "hves", "hives", (("lexical_rank", 0.0),))
    second = Candidate("lexical.word", 0, 4, "hves", "hides", (("lexical_rank", 1.0),))
    other = Candidate("confusables.in_numbers", 0, 1, "O", "0", (("v01", 1.0),))
    assert LEXICON.judge(first)[0]
    assert not LEXICON.judge(second)[0]
    assert not LEXICON.judge(other)[0]
    assert POLICIES["lexicon"] is LEXICON


def test_b2_with_a_pack_corrects_unknown_words_and_nothing_else() -> None:
    fitted = pack.fit([], ["the bees came late"], engine="e", model="m", order=2, min_count=1)
    model = pack.ModelPack(
        fitted.engine, fitted.model, fitted.language, fitted.channel, WORDS, fitted.sources
    )
    line = Line.from_text("the hves came late, 1O5", box=Box(0, 0, 400, 30))
    result = clean(Document((Page((Block((line,)),)),)), policy=LEXICON, pack=model)
    assert result.text == "the hives came late, 1O5"  # 1O5 is left: B2 makes no v0.1 repairs
