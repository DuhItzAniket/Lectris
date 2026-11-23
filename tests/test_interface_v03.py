"""The v0.3 interface (Phase 8): the guarantee, review flags, reports with decisions, --pack."""

import json
from pathlib import Path

import pytest

from lectris import clean, report
from lectris.cli import main
from lectris.decide import Guarantee, Threshold
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document, Engine, Line, Page
from lectris.models import pack
from lectris.models.acceptance import Acceptance

WORDS = Lexicon({"the": 9, "hives": 5, "bees": 5, "came": 3, "late": 3})


@pytest.fixture
def calibrated() -> pack.ModelPack:
    fitted = pack.fit(
        [("the hives", "the hves")], ["the bees came late", "the hives"],
        engine="glypharis", model="glypharis_v1", order=3, min_count=1,
    )  # fmt: skip
    # p = sigmoid(4 * word_gain - 1): a candidate that makes a known word out of an unknown one
    acceptance = Acceptance(("word_gain",), (0.0,), (1.0,), (4.0,), -1.0)
    return pack.ModelPack(
        fitted.engine, fitted.model, fitted.language, fitted.channel, WORDS, fitted.sources,
        acceptance=acceptance,
        risk={
            "standard": pack.Budget(0.02, 0.1, 0.9, 400, 0.3),
            "conservative": pack.Budget(0.01, 0.1, None, 400, None),
        },
    )  # fmt: skip


def document(engine: Engine | None = None) -> Document:
    line = Line(Line.from_text("The bees came to the hves late", box=Box(0, 0, 500, 30)).words,
                Box(0, 0, 500, 30), 0.6)  # fmt: skip
    return Document((Page((Block((line,)),)),), engine=engine)


GLYPHARIS = Engine("glypharis", "1.0", "glypharis_v1")


class TestGuarantee:
    def test_a_risk_policy_carries_its_guarantee(self, calibrated: pack.ModelPack) -> None:
        policy = calibrated.policy("standard")
        assert policy.guarantee == Guarantee(0.02, 0.1, 0.9, "glypharis", "glypharis_v1")
        result = clean(document(GLYPHARIS), policy=policy, pack=calibrated)
        assert result.guarantee == policy.guarantee
        assert result.guarantee_applies
        assert "hives" in result.text

    def test_it_does_not_apply_to_another_engine(self, calibrated: pack.ModelPack) -> None:
        policy = calibrated.policy("standard")
        other = clean(document(Engine("tesseract", "5", "eng")), policy=policy, pack=calibrated)
        assert not other.guarantee_applies
        assert not clean(document(), policy=policy, pack=calibrated).guarantee_applies

    def test_other_policies_have_none(self) -> None:
        assert clean(document()).guarantee is None
        assert not clean(document()).guarantee_applies

    def test_no_certified_threshold_accepts_nothing(self, calibrated: pack.ModelPack) -> None:
        policy = calibrated.policy("conservative")
        assert policy.guarantee is not None
        assert policy.guarantee.threshold is None
        result = clean(document(GLYPHARIS), policy=policy, pack=calibrated)
        assert "hves" in result.text

    def test_errors(self, calibrated: pack.ModelPack) -> None:
        with pytest.raises(pack.PackError, match="no risk budget"):
            calibrated.policy("aggressive")


class TestFlags:
    def test_declined_but_plausible_candidates_are_flagged(
        self, calibrated: pack.ModelPack
    ) -> None:
        strict = Threshold(calibrated.acceptance.probability, 0.999)  # type: ignore[union-attr]
        result = clean(document(GLYPHARIS), policy=strict, pack=calibrated)
        flags = result.flags()
        assert [(f.rule, f.before, f.after) for f in flags] == [("lexical.word", "hves", "hives")]
        assert flags[0].probability > 0.3
        assert result.flags(threshold=0.9999) == ()

    def test_parity_has_no_flags(self, calibrated: pack.ModelPack) -> None:
        assert clean(document(GLYPHARIS), pack=calibrated).flags() == ()


class TestReports:
    def test_json_has_the_guarantee_decisions_and_flags(self, calibrated: pack.ModelPack) -> None:
        result = clean(document(GLYPHARIS), policy=calibrated.policy("standard"), pack=calibrated)
        data = report.to_dict(result)
        assert data["guarantee"] == {
            "alpha": 0.02, "delta": 0.1, "threshold": 0.9, "engine": "glypharis",
            "model": "glypharis_v1", "applies": True,
        }  # fmt: skip
        decisions = [d for block in data["blocks"] for d in block["decisions"]]
        accepted = [d for d in decisions if d["accepted"]]
        assert accepted[0]["after"] == "hives"
        assert accepted[0]["probability"] >= 0.9
        assert "word_gain" in accepted[0]["features"]
        assert data["flags"] == []
        json.dumps(data)  # plain data

    def test_markdown_states_the_guarantee(self, calibrated: pack.ModelPack) -> None:
        result = clean(document(), policy=calibrated.policy("standard"), pack=calibrated)
        text = report.to_markdown(result)
        assert "harm rate at most 0.02" in text
        assert "does NOT apply" in text

    def test_without_a_risk_policy_the_guarantee_is_null(self) -> None:
        assert report.to_dict(clean(document()))["guarantee"] is None


class TestCleanCommand:
    @pytest.fixture
    def files(self, tmp_path: Path, calibrated: pack.ModelPack) -> tuple[Path, Path]:
        packed = tmp_path / "p.lectris.json.gz"
        pack.save(calibrated, packed)
        page = {
            "glypharis_version": "1.0", "model_version": "glypharis_v1",
            "lines": [{"text": "The bees came to the hves late", "confidence": 0.6,
                       "bbox": [0, 0, 500, 30]}],
        }  # fmt: skip
        source = tmp_path / "page.json"
        source.write_text(json.dumps(page), encoding="utf-8")
        return packed, source

    def test_a_calibrated_pack_uses_the_risk_policy(
        self, files: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        packed, source = files
        assert main(["clean", str(source), "--pack", str(packed)]) == 0
        captured = capsys.readouterr()
        assert "hives" in captured.out
        assert captured.err == ""

    def test_parity_with_a_pack(
        self, files: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        packed, source = files
        assert main(["clean", str(source), "--pack", str(packed), "--policy", "parity"]) == 0
        assert "hves" in capsys.readouterr().out

    def test_another_engine_gets_a_warning(
        self, tmp_path: Path, files: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        packed, _ = files
        plain = tmp_path / "plain.txt"
        plain.write_text("The bees came to the hves late\n", encoding="utf-8")
        assert main(["clean", str(plain), "--pack", str(packed)]) == 0
        assert "guarantee does not apply" in capsys.readouterr().err

    def test_risk_needs_a_pack(
        self, files: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, source = files
        assert main(["clean", str(source), "--policy", "risk"]) == 1
        assert "needs --pack" in capsys.readouterr().err
