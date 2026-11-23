import json
import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.cli import main
from lectris.lexicon import Lexicon
from lectris.model import Document, Engine
from lectris.models import pack
from lectris.models.channel import Channel, errors, uniform_log_likelihood
from lectris.models.charlm import BOUNDARY, CharLM

TEXTS = [
    "the bees came late this year",
    "the growers count the hives each spring",
    "the river rose in the spring",
    "bees and hives and the river",
]


@pytest.fixture(scope="module")
def model() -> CharLM:
    return CharLM.fit(TEXTS, order=4)


class TestCharLM:
    def test_probabilities_sum_to_one(self, model: CharLM) -> None:
        vocabulary = sorted(set("".join(TEXTS)))
        for context in ["", "th", "the ", "zzz", "spri"]:
            unseen = model.prob("☃", context)
            assert sum(model.prob(c, context) for c in vocabulary) + unseen == pytest.approx(1)
            assert unseen > 0

    def test_seen_text_is_likelier_than_noise(self, model: CharLM) -> None:
        assert model.score("the hives") > model.score("xq zvvkj")
        assert model.perplexity(["the bees"]) < model.perplexity(["qzx jvw"])

    def test_the_context_matters(self, model: CharLM) -> None:
        assert model.prob("e", "th") > model.prob("e", "zq")

    def test_round_trip(self, model: CharLM) -> None:
        again = CharLM.from_data(json.loads(json.dumps(model.to_data())))
        assert again.to_data() == model.to_data()
        assert again.score("the river") == pytest.approx(model.score("the river"))

    def test_pruning_keeps_a_distribution(self) -> None:
        pruned = CharLM.fit(TEXTS, order=4, prune=True)
        assert pruned.size < CharLM.fit(TEXTS, order=4).size
        vocabulary = sorted(set("".join(TEXTS)))
        total = sum(pruned.prob(c, "the ") for c in vocabulary) + pruned.prob("☃", "the ")
        assert total == pytest.approx(1)

    def test_errors(self) -> None:
        with pytest.raises(ValueError, match="the order is 2 or more"):
            CharLM.fit(TEXTS, order=1)
        with pytest.raises(ValueError, match="boundary mark"):
            CharLM.fit([f"a{BOUNDARY}b"])
        assert math.isinf(CharLM.fit(TEXTS).perplexity([]))

    @given(st.lists(st.text(alphabet="abc ", min_size=1, max_size=12), min_size=1, max_size=6))
    def test_any_model_is_a_distribution(self, texts: list[str]) -> None:
        model = CharLM.fit(texts, order=3)
        seen = set("".join(texts))  # the seen characters, and one character never seen
        for context in ["", "a", "ab", "cc"]:
            total = sum(model.prob(c, context) for c in seen) + model.prob("z", context)
            assert total == pytest.approx(1)


PAIRS = (
    ("modern", "rnodern"),
    ("modem", "rnodem"),
    ("the 105 hives", "the 1O5 hives"),
    ("a quiet year", "a quietyear"),
    ("the bees", "the bees"),
)


class TestChannel:
    def test_errors_group_short_runs(self) -> None:
        assert ("m", "rn") in errors("modem", "rnodem")
        assert errors("a b", "ab") == [("a", "a"), (" ", ""), ("b", "b")]
        assert all(len(a) <= 2 and len(b) <= 2 for a, b in errors("abcdef", "uvwxyz"))

    def test_seen_confusions_are_likely(self) -> None:
        channel = Channel.fit(PAIRS)
        assert channel.prob("m", "rn") > channel.prob("m", "q")
        assert channel.prob("0", "O") > channel.prob("0", "Q")
        assert channel.log_likelihood("modem", "rnodem") > channel.log_likelihood("modem", "qodem")
        assert channel.top(3)[0][:2] == ("m", "rn")

    def test_an_unseen_character_is_not_read_with_certainty(self) -> None:
        channel = Channel.fit(PAIRS)
        assert channel.prob("x", "") < 0.1  # "x" never occurs in the intended texts
        seen = Channel.fit([("hives", "hves")] * 3)  # the engine often loses this "i"
        assert seen.log_likelihood("hxves", "hves") < seen.log_likelihood("hives", "hves")

    def test_probabilities_of_an_intended_character_sum_to_at_most_one(self) -> None:
        channel = Channel.fit(PAIRS)
        forms = {b for a, b in errors("modern", "rnodern")} | {"", "m", "o", "0", "O"}
        assert sum(channel.prob("m", form) for form in forms) <= 1

    def test_round_trip(self) -> None:
        channel = Channel.fit(PAIRS)
        again = Channel.from_data(json.loads(json.dumps(channel.to_data())))
        assert again.to_data() == channel.to_data()

    def test_uniform_baseline(self) -> None:
        exact = uniform_log_likelihood("abc", "abc", 0.1, 10)
        assert exact == pytest.approx(3 * math.log(0.9))
        assert uniform_log_likelihood("abc", "abd", 0.1, 10) < exact


class TestPack:
    @pytest.fixture
    def fitted(self, tmp_path: Path) -> pack.ModelPack:
        book = tmp_path / "book.txt"
        book.write_text("The bees came late.\nThe hives were full.\n", encoding="utf-8")
        return pack.fit(
            PAIRS, TEXTS, engine="glypharis", model="glypharis_v1", texts=[book],
            order=3, min_count=1,
        )  # fmt: skip

    def test_save_and_load(self, fitted: pack.ModelPack, tmp_path: Path) -> None:
        path = tmp_path / "p.lectris.json.gz"
        pack.save(fitted, path)
        loaded = pack.load(path)
        assert loaded.to_data() == fitted.to_data()
        assert loaded.lexicon.frequency("bees") == fitted.lexicon.frequency("bees") > 0
        assert [s.name for s in loaded.sources] == ["book.txt"]

    def test_the_same_pack_is_the_same_bytes(self, fitted: pack.ModelPack, tmp_path: Path) -> None:
        pack.save(fitted, tmp_path / "a.gz")
        pack.save(fitted, tmp_path / "b.gz")
        assert (tmp_path / "a.gz").read_bytes() == (tmp_path / "b.gz").read_bytes()

    def test_matches_its_engine_and_model(self, fitted: pack.ModelPack) -> None:
        assert fitted.matches(Document((), engine=Engine("glypharis", "1.0.0", "glypharis_v1")))
        assert not fitted.matches(Document((), engine=Engine("glypharis", "1.0.0", "other")))
        assert not fitted.matches(Document(()))

    def test_max_chars_limits_the_text_read(self, tmp_path: Path) -> None:
        book = tmp_path / "book.txt"
        book.write_text("abc " * 100, encoding="utf-8")
        small = pack.fit([], [], engine="e", model="m", texts=[book], max_chars=4, min_count=1)
        assert small.lexicon.counts() == {"abc": 1}

    def test_not_a_pack(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.gz"
        bad.write_bytes(b"not gzip")
        with pytest.raises(pack.PackError, match="not a LECTRIS model pack"):
            pack.load(bad)
        other = tmp_path / "other.gz"
        import gzip  # noqa: PLC0415

        other.write_bytes(gzip.compress(json.dumps({"manifest": {"format": "x"}}).encode()))
        with pytest.raises(pack.PackError, match="the pack format is 'x'"):
            pack.load(other)

    def test_words(self) -> None:
        assert pack.words("Don't stop: the well-known 1O5 apples, l0ng (quoted)") == [
            "don't", "stop", "the", "well-known", "apples", "quoted",
        ]  # fmt: skip


def test_lexicon_counts_round_trip() -> None:
    lexicon = Lexicon({"Bees": 2, "hives": 1})
    assert lexicon.counts() == {"bees": 2, "hives": 1}
    assert Lexicon(lexicon.counts()).counts() == lexicon.counts()


def test_the_fit_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    engine = {
        "glypharis_version": "1.0.0",
        "model_version": "glypharis_v1",
        "lines": [{"text": "They counted 1O5 hives.", "bbox": [0, 0, 400, 30]}],
    }
    truth = {"page": "p1", "lines": [{"text": "They counted 105 hives.", "box": [0, 0, 400, 30]}]}
    (tmp_path / "e.json").write_text(json.dumps(engine), encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps(truth), encoding="utf-8")
    manifest = tmp_path / "pairs.json"
    manifest.write_text(
        json.dumps({"pages": [{"page": "p1", "engine": "e.json", "truth": "t.json"}]}),
        encoding="utf-8",
    )
    books = tmp_path / "books"
    books.mkdir()
    (books / "a.txt").write_text("The hives hum.\n", encoding="utf-8")
    out = tmp_path / "p.lectris.json.gz"
    arguments = ["fit", "--pairs", str(manifest), "--engine", "glypharis", "--model",
                 "glypharis_v1", "--text", str(books), "--order", "3", "-o", str(out)]  # fmt: skip
    assert main(arguments) == 0
    assert "1 line pairs" in capsys.readouterr().out
    loaded = pack.load(out)
    assert loaded.channel.prob("0", "O") > loaded.channel.prob("0", "Q")
    assert [s.role for s in loaded.sources] == ["channel, language, lexicon", "language, lexicon"]
