import json
import math
import random
from pathlib import Path
from typing import Any

import pytest

from lectris.cli import main
from lectris.decide import Threshold
from lectris.edits import Candidate
from lectris.eval.calibrate import PageCandidates, most_useful, risk_policy
from lectris.eval.scoring import LabelledCandidate
from lectris.models import pack
from lectris.models.acceptance import Acceptance, calibration
from lectris.models.risk import certified, grid, hoeffding_bentkus, learn_then_test


def examples(n: int = 400, seed: int = 7) -> list[tuple[dict[str, float], int]]:
    """Synthetic candidates whose label follows a known logistic model of two features."""
    generator = random.Random(seed)  # noqa: S311 - a simulation, not secrets
    found = []
    for _ in range(n):
        a, b = generator.gauss(0, 1), generator.gauss(0, 1)
        p = 1 / (1 + math.exp(-(2.0 * a - 1.0 * b + 0.5)))
        found.append(({"a": a, "b": b}, 1 if generator.random() < p else 0))
    return found


class TestAcceptance:
    def test_it_recovers_the_signs_and_ranks(self) -> None:
        model = Acceptance.fit(examples(), l2=0.1)
        weights = dict(zip(model.names, model.weights, strict=True))
        assert weights["a"] > 0 > weights["b"]
        assert abs(weights["a"]) > abs(weights["b"])
        high = Candidate("demo.rule", 0, 1, "x", "y", (("a", 2.0), ("b", -1.0)))
        low = Candidate("demo.rule", 0, 1, "x", "y", (("a", -2.0), ("b", 1.0)))
        assert model.probability(high) > 0.9
        assert model.probability(low) < 0.1

    def test_it_is_calibrated_on_its_own_distribution(self) -> None:
        model = Acceptance.fit(examples(2000, seed=1), l2=0.1)
        held_out = examples(2000, seed=2)
        probabilities = [model.logit(f) for f, _ in held_out]
        probabilities = [1 / (1 + math.exp(-z)) for z in probabilities]
        assert calibration(probabilities, [y for _, y in held_out]).ece < 0.05

    def test_missing_features_are_zero_and_constants_are_harmless(self) -> None:
        data = [({"a": 1.0, "c": 5.0}, 1), ({"a": -1.0, "c": 5.0}, 0)] * 10
        model = Acceptance.fit(data)
        assert model.probability(Candidate("demo.rule", 0, 1, "x", "y", (("a", 1.0),))) > 0.5

    def test_round_trip_and_determinism(self) -> None:
        model = Acceptance.fit(examples())
        assert Acceptance.from_data(json.loads(json.dumps(model.to_data()))) == model
        assert Acceptance.fit(examples()) == model

    def test_errors(self) -> None:
        with pytest.raises(ValueError, match="needs examples"):
            Acceptance.fit([])
        with pytest.raises(ValueError, match="labels are 0 or 1"):
            Acceptance.fit([({"a": 1.0}, 2)])


class TestCalibration:
    def test_perfect_and_bad(self) -> None:
        assert calibration([0.0, 0.0, 1.0, 1.0], [0, 0, 1, 1], bins=2).ece == 0
        assert calibration([1.0, 1.0], [0, 0], bins=1).ece == 1
        assert calibration([0.5], [1]).brier == 0.25
        with pytest.raises(ValueError, match="as many labels"):
            calibration([0.5], [])


class TestHoeffdingBentkus:
    def test_zero_loss_on_n_pages_cannot_certify_below_the_limit(self) -> None:
        n, delta = 430, 0.1
        limit = 1 - delta ** (1 / n)
        assert hoeffding_bentkus(0.0, n, limit * 0.9) > delta
        assert hoeffding_bentkus(0.0, n, limit * 1.5) < delta

    def test_a_mean_at_or_above_alpha_is_never_rejected(self) -> None:
        assert hoeffding_bentkus(0.05, 1000, 0.05) == 1.0

    def test_more_pages_give_smaller_p_values(self) -> None:
        assert hoeffding_bentkus(0.001, 2000, 0.01) < hoeffding_bentkus(0.001, 200, 0.01)

    @pytest.mark.parametrize(
        ("args", "message"), [((0.0, 10, 0.0), "alpha"), ((0.0, 0, 0.1), "one")]
    )
    def test_arguments(self, args: tuple[float, int, float], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            hoeffding_bentkus(*args)


class TestLearnThenTest:
    def test_the_certified_set_and_the_most_permissive(self) -> None:
        losses = {1.0: [0.0] * 500, 0.5: [0.001] * 500, 0.0: [0.5] * 500}
        found = certified(lambda t: losses[t], (1.0, 0.5, 0.0), alpha=0.01, delta=0.1)
        assert found == (1.0, 0.5)
        assert learn_then_test(lambda t: losses[t], (1.0, 0.5, 0.0), alpha=0.01, delta=0.1) == 0.5

    def test_none_when_even_the_strictest_fails(self) -> None:
        assert learn_then_test(lambda _: [0.0] * 10, (1.0,), alpha=0.01, delta=0.1) is None

    def test_losses_are_checked(self) -> None:
        with pytest.raises(ValueError, match=r"losses are in \[0, 1\]"):
            certified(lambda _: [2.0], (1.0,), alpha=0.1, delta=0.1)
        with pytest.raises(ValueError, match="delta"):
            certified(lambda _: [0.0], (1.0,), alpha=0.1, delta=1.0)

    def test_grid(self) -> None:
        assert grid(4) == (1.0, 0.75, 0.5, 0.25, 0.0)

    def test_the_guarantee_holds_in_simulation(self) -> None:
        """Phase 7's exit criterion: with pages drawn from a known distribution, the risk of the
        chosen threshold exceeds alpha in at most about delta of the repetitions."""
        alpha, delta, pages, repetitions = 0.05, 0.1, 300, 300
        thresholds = grid(20)

        def true_risk(t: float) -> float:  # each page loses 1 with probability 0.2 * (1 - t)
            return 0.2 * (1 - t)

        generator = random.Random(1337)  # noqa: S311 - a simulation, not secrets
        violations = 0
        for _ in range(repetitions):
            draws = [generator.random() for _ in range(pages)]

            def losses(t: float, draws: list[float] = draws) -> list[float]:
                return [1.0 if u < true_risk(t) else 0.0 for u in draws]

            chosen = learn_then_test(losses, thresholds, alpha=alpha, delta=delta)
            if chosen is not None and true_risk(chosen) > alpha:
                violations += 1
        assert violations / repetitions <= delta + 0.03  # binomial slack for 300 repetitions


def labelled(page: str, effect: int, a: float) -> LabelledCandidate:
    candidate = Candidate("demo.rule", 0, 1, "x", "y", (("a", a),))
    return LabelledCandidate(page, 0, 0, candidate, False, effect, 100)


class TestMostUseful:
    def test_it_picks_the_certified_threshold_with_the_best_net_effect(self) -> None:
        model = Acceptance(("a",), (0.0,), (1.0,), (1.0,), 0.0)  # p = sigmoid(a)
        pages = [
            PageCandidates(
                "p", (labelled("p", -3, 3.0), labelled("p", 2, 0.0), labelled("p", 1, -3.0)), 100
            )
        ]
        # accepting at 0.9: -3; at 0.5: -1; at 0.0: 0
        assert most_useful((0.9, 0.5, 0.0), pages, model) == 0.9
        assert most_useful((), pages, model) is None

    def test_a_tie_goes_to_the_strictest(self) -> None:
        model = Acceptance(("a",), (0.0,), (1.0,), (1.0,), 0.0)
        pages = [PageCandidates("p", (labelled("p", 0, 0.0),), 100)]
        assert most_useful((0.9, 0.4), pages, model) == 0.9


class TestRiskPolicy:
    def test_it_needs_a_calibrated_pack(self) -> None:
        fitted = pack.fit([], ["a b"], engine="e", model="m", order=2, min_count=1)
        with pytest.raises(pack.PackError, match="not calibrated"):
            risk_policy(fitted, "standard")

    def test_the_threshold_comes_from_the_profile_budget(self) -> None:
        fitted = pack.fit([], ["a b"], engine="e", model="m", order=2, min_count=1)
        model = Acceptance(("a",), (0.0,), (1.0,), (1.0,), 0.0)
        calibrated = pack.ModelPack(
            fitted.engine, fitted.model, fitted.language, fitted.channel, fitted.lexicon,
            fitted.sources, acceptance=model,
            risk={"standard": pack.Budget(0.02, 0.1, 0.7, 10, 0.2),
                  "conservative": pack.Budget(0.01, 0.1, None, 10, None)},
        )  # fmt: skip
        policy = risk_policy(calibrated, "standard")
        assert isinstance(policy, Threshold)
        assert policy.threshold == 0.7
        refusing = risk_policy(calibrated, "conservative")
        assert not refusing.judge(Candidate("demo.rule", 0, 1, "x", "y", (("a", 9.0),)))[0]
        with pytest.raises(pack.PackError, match="no risk budget"):
            risk_policy(calibrated, "aggressive")

    def test_a_calibrated_pack_round_trips(self, tmp_path: Path) -> None:
        fitted = pack.fit([], ["a b"], engine="e", model="m", order=2, min_count=1)
        calibrated = pack.ModelPack(
            fitted.engine, fitted.model, fitted.language, fitted.channel, fitted.lexicon,
            fitted.sources, acceptance=Acceptance(("a",), (0.0,), (1.0,), (1.0,), 0.0),
            risk={"standard": pack.Budget(0.02, 0.1, 0.7, 10, 0.2)}, calibration={"ece": 0.01},
        )  # fmt: skip
        pack.save(calibrated, tmp_path / "c.gz")
        assert pack.load(tmp_path / "c.gz").to_data() == calibrated.to_data()


def write(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_calibrate_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pages = []
    for i, (ocr, truth) in enumerate(
        [("the hves came", "the hives came"), ("bees and hves", "bees and hives")] * 3
    ):
        write(tmp_path / f"e{i}.json", {"glypharis_version": "1", "model_version": "m",
              "lines": [{"text": ocr, "bbox": [0, 0, 300, 30]}]})  # fmt: skip
        write(tmp_path / f"t{i}.json", {"page": f"p{i}",
              "lines": [{"text": truth, "box": [0, 0, 300, 30]}]})  # fmt: skip
        pages.append({"page": f"p{i}", "engine": f"e{i}.json", "truth": f"t{i}.json"})
    manifest = write(tmp_path / "pairs.json", {"pages": pages})
    books = tmp_path / "books"
    books.mkdir()
    (books / "a.txt").write_text("the hives came\nbees and hives\n" * 5, encoding="utf-8")
    raw = tmp_path / "p.gz"
    assert main(["fit", "--pairs", str(manifest), "--engine", "glypharis", "--model", "m",
                 "--text", str(books), "--order", "3", "-o", str(raw)]) == 0  # fmt: skip
    out = tmp_path / "c.gz"
    assert main(["calibrate", "--pack", str(raw), "--fit", str(manifest), "--cal",
                 str(manifest), "-o", str(out)]) == 0  # fmt: skip
    calibrated = pack.load(out)
    assert calibrated.acceptance is not None
    assert calibrated.risk is not None
    assert set(calibrated.risk) == {"conservative", "standard", "aggressive"}
    assert "standard: alpha 0.02" in capsys.readouterr().out
