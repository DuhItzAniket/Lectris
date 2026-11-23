import math

import pytest

from lectris import clean
from lectris.decide import Threshold
from lectris.edits import Candidate, OffsetMap
from lectris.evidence import BlockLines, Evidence
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document, Engine, Line, Page
from lectris.models import pack
from lectris.propose import Lexical, Segmentation, core_of, in_case_of, words_in

WORDS = Lexicon(
    {"the": 50, "bees": 9, "hives": 8, "came": 7, "late": 7, "quiet": 5, "year": 6, "a": 20,
     "river": 4, "spring": 4, "modern": 3, "modem": 1, "count": 3}
)  # fmt: skip
PAIRS = (
    ("the hives", "the hves"),
    ("the bees came", "the bees carne"),
    ("a quiet year", "a quietyear"),
    ("the river", "the river"),
)
TEXTS = ("the bees came late", "the hives", "a quiet year", "the river in spring")


@pytest.fixture(scope="module")
def model() -> pack.ModelPack:
    fitted = pack.fit(PAIRS, TEXTS, engine="glypharis", model="glypharis_v1", order=3, min_count=1)
    return pack.ModelPack(
        fitted.engine, fitted.model, fitted.language, fitted.channel, WORDS, fitted.sources
    )


class TestWords:
    def test_words_in_skip_punctuation_and_mixed_tokens(self) -> None:
        assert [w for _, _, w in words_in("(Bees) 1O5 hves, l0ng quiet.")] == [
            "Bees", "hves", "quiet",
        ]  # fmt: skip
        assert next(words_in("  (hves)"))[:2] == (3, 7)

    def test_case_and_core(self) -> None:
        assert (in_case_of("hives", "HVES"), in_case_of("hives", "Hves")) == ("HIVES", "Hives")
        assert in_case_of("a", "A") == "A"
        assert core_of("(hves),") == "hves"


class TestLexical:
    def test_a_lost_character_is_proposed_back(self) -> None:
        found = Lexical(WORDS)("the hves were full")
        assert [(c.start, c.end, c.before, c.after) for c in found] == [(4, 8, "hves", "hives")]
        assert found[0].feature("v01", default=-1) == 0.0

    def test_substitutions_and_insertions_and_case(self) -> None:
        assert {c.after for c in Lexical(WORDS)("Bres")} == {"Bees"}
        assert {c.after for c in Lexical(WORDS)("yeaar")} == {"year"}

    def test_words_short_tokens_and_mixed_tokens_are_left_alone(self) -> None:
        assert Lexical(WORDS)("the bees came late, 1O5 ab hv") == ()

    def test_the_most_frequent_come_first_up_to_the_limit(self) -> None:
        found = Lexical(WORDS, limit=1)("modew")
        assert [c.after for c in found] == ["modem"]


class TestSegmentation:
    def test_a_missing_space(self) -> None:
        found = Segmentation(WORDS)("a quietyear here")
        assert [(c.rule, c.start, c.end, c.after) for c in found] == [
            ("segmentation.split", 7, 7, " ")
        ]

    def test_a_spurious_space(self) -> None:
        found = Segmentation(WORDS)("the hiv es")
        assert [(c.rule, c.start, c.end, c.before, c.after) for c in found] == [
            ("segmentation.merge", 7, 8, " ", "")
        ]

    def test_two_words_are_never_merged(self) -> None:
        assert Segmentation(Lexicon({"the": 1, "rest": 1, "therest": 1}))("the rest") == ()


class TestEvidence:
    def test_features(self, model: pack.ModelPack) -> None:
        text = "the hves came"
        candidate = Candidate("lexical.word", 4, 8, "hves", "hives", (("v01", 0.0),))
        line = Line.from_text(text, confidence=0.4)
        line = Line(line.words, confidence=0.4, detection=0.8)
        (scored,) = Evidence(model).score(
            text, [candidate], OffsetMap(), BlockLines.of(text, [line])
        )
        names = [name for name, _ in scored.features]
        assert names == sorted(names)
        assert scored.feature("v01", default=-1) == 0.0
        assert scored.feature("rule=lexical.word") == 1.0
        assert scored.feature("word_before") == 0.0
        assert scored.feature("word_after") == pytest.approx(math.log1p(8))
        unlikely = Candidate("lexical.word", 4, 8, "hves", "hxves")
        (other,) = Evidence(model).score(text, [unlikely], OffsetMap(), BlockLines.of(text, [line]))
        assert scored.feature("channel") > other.feature("channel")  # "i" lost is seen, "x" not
        assert (scored.feature("line_confidence"), scored.feature("detection")) == (0.4, 0.8)
        assert scored.feature("engine_missing") == 0.0
        assert all(math.isfinite(value) for _, value in scored.features)

    def test_without_lines_the_engine_is_missing(self, model: pack.ModelPack) -> None:
        candidate = Candidate("lexical.word", 0, 4, "hves", "hives")
        (scored,) = Evidence(model).score(
            "hves", [candidate], OffsetMap(), BlockLines.of("hves", [])
        )
        assert scored.feature("engine_missing") == 1.0
        assert scored.feature("line_confidence") == 1.0

    def test_the_offsets_find_the_line_a_span_came_from(self, model: pack.ModelPack) -> None:
        lines = [
            Line(Line.from_text("the bees").words, confidence=0.9),
            Line(Line.from_text("the hves").words, confidence=0.3),
        ]
        block = BlockLines.of("the bees\nthe hves", lines)
        text = "the bees the hves"  # after unwrapping
        offsets = OffsetMap.from_edits([])  # unwrapping replaced \\n by " ", same length
        candidate = Candidate("lexical.word", 13, 17, "hves", "hives")
        (scored,) = Evidence(model).score(text, [candidate], offsets, block)
        assert scored.feature("line_confidence") == 0.3

    def test_a_split_reads_the_weaker_word(self, model: pack.ModelPack) -> None:
        candidate = Candidate("segmentation.split", 7, 7, "", " ")
        (scored,) = Evidence(model).score(
            "a quietyear", [candidate], OffsetMap(), BlockLines.of("", [])
        )
        assert scored.feature("word_after") == pytest.approx(math.log1p(5))
        assert scored.feature("insertion") == 1.0


class TestCleanWithAPack:
    def document(self) -> Document:
        lines = (
            Line(Line.from_text("The bees came late to the hves", box=Box(0, 0, 500, 30)).words,
                 Box(0, 0, 500, 30), 0.6, None, 0.9),
            Line(Line.from_text("in a quietyear.", box=Box(0, 40, 300, 70)).words,
                 Box(0, 40, 300, 70), 0.7, None, 0.9),
        )  # fmt: skip
        return Document((Page((Block(lines),)),), engine=Engine("glypharis", "1.0", "glypharis_v1"))

    def test_parity_holds_with_a_pack(self, model: pack.ModelPack) -> None:
        document = self.document()
        with_pack = clean(document, pack=model)
        assert with_pack.text == clean(document).text
        rules = [j.decision.candidate.rule for j in with_pack.decisions()]
        assert "lexical.word" in rules
        assert "segmentation.split" in rules
        new = [j for j in with_pack.decisions() if j.decision.candidate.rule == "lexical.word"]
        assert not any(j.decision.accepted for j in new)
        assert new[0].decision.candidate.feature("line_confidence") == 0.6

    def test_a_threshold_policy_accepts_the_lexicon_candidates(self, model: pack.ModelPack) -> None:
        policy = Threshold(lambda c: 1.0 if c.feature("word_gain") > 0 else 0.0, 0.5)
        result = clean(self.document(), pack=model, policy=policy)
        assert "hives" in result.text
        assert "quiet year" in result.text

    def test_the_stages_are_recorded(self, model: pack.ModelPack) -> None:
        result = clean(self.document(), pack=model)
        stages = [rule for rule, _ in result.blocks[0].revisions]
        assert stages[-2:] == ["lexical.word", "segmentation"]
