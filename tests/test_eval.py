import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris import clean
from lectris.cli import main
from lectris.decide import Threshold
from lectris.edits import Candidate
from lectris.errors import FormatError
from lectris.eval import experiment, truth
from lectris.eval.matching import iou, match_lines
from lectris.eval.scoring import _reference_joins, lay_out, normalised, raw, score_page
from lectris.eval.stats import bootstrap, ratio
from lectris.eval.truth import TruthLine, TruthPage
from lectris.model import Block, Box, Document, Line, Page
from lectris.profiles import get

NONE = experiment.NONE


def box(y: float, x1: float = 500) -> Box:
    return Box(0, y, x1, y + 30)


def page_of(*lines: tuple[str, Box | None]) -> Document:
    return Document((Page((Block(tuple(Line.from_text(text, box=b) for text, b in lines)),)),))


def truth_of(*lines: tuple[str, Box | None]) -> TruthPage:
    return TruthPage("p1", tuple(TruthLine(text, b) for text, b in lines))


class TestMatching:
    def test_iou(self) -> None:
        assert iou(Box(0, 0, 10, 10), Box(0, 0, 10, 10)) == 1.0
        assert iou(Box(0, 0, 10, 10), Box(5, 0, 15, 10)) == pytest.approx(1 / 3)
        assert iou(Box(0, 0, 10, 10), Box(20, 0, 30, 10)) == 0.0

    def test_lines_are_matched_one_to_one_by_overlap(self) -> None:
        ocr = [box(100), box(0), Box(0, 0, 500, 60), None]
        truth_boxes = [box(0), box(100), box(200)]
        matching = match_lines(ocr, truth_boxes)
        assert matching.pairs == ((0, 1), (1, 0))  # the tall line overlaps line 0 less
        assert matching.ocr_unmatched == (2, 3)
        assert matching.truth_unmatched == (2,)
        assert matching.truth_of(1) == 0
        assert matching.truth_of(3) is None

    def test_below_the_threshold_nothing_is_matched(self) -> None:
        assert match_lines([Box(0, 0, 10, 10)], [Box(6, 0, 16, 10)]).pairs == ()

    @pytest.mark.parametrize("threshold", [0, 1.5])
    def test_the_threshold_is_checked(self, threshold: float) -> None:
        with pytest.raises(ValueError, match="IoU threshold"):
            match_lines([], [], threshold=threshold)


class TestTracks:
    def test_raw_folds_whitespace_and_composes(self) -> None:
        assert raw(" a\n\tb  é ") == "a b é"

    def test_normalised_applies_the_transforms(self) -> None:
        assert normalised("ﬁne “so”…") == 'fine "so"...'


class TestScorePage:
    def test_reading_order_is_not_an_error(self) -> None:
        document = page_of(("second line", box(100)), ("first line", box(0)))
        score = score_page(
            clean(document), truth_of(("first line", box(0)), ("second line", box(100)))
        )
        assert (score.chars.before, score.chars.after, score.matched_lines) == (0, 0, 2)

    def test_a_fix_is_labelled_and_counted(self) -> None:
        document = page_of(("They counted 1O5 hives.", box(0)))
        score = score_page(clean(document), truth_of(("They counted 105 hives.", box(0))))
        assert (score.chars.reference, score.chars.before, score.chars.after) == (23, 1, 0)
        (label,) = score.labels
        assert (label.edit.rule, label.effect, label.label) == ("confusables.in_numbers", -1, "fix")
        assert (score.fixed_chars, score.harm_chars, score.harm_rate) == (1, 0, 0.0)

    def test_a_harm_is_labelled_and_makes_the_harm_rate(self) -> None:
        document = page_of(("Part 1O5 fits.", box(0)))  # the truth really says 1O5
        score = score_page(clean(document), truth_of(("Part 1O5 fits.", box(0))))
        assert [label.label for label in score.labels] == ["harm"]
        assert (score.chars.before, score.chars.after) == (0, 1)
        assert score.harm_rate == pytest.approx(1 / 14)

    def test_transforms_are_neutral_and_unwrapping_is_layout(self) -> None:
        document = page_of(("A ﬁne survey of", box(0)), ("the river.", box(40)))
        score = score_page(
            clean(document), truth_of(("A fine survey of", box(0)), ("the river.", box(40)))
        )
        assert {label.label for label in score.labels} == {"neutral", "layout"}
        assert {label.edit.rule for label in score.labels if label.label == "layout"} == {
            "unwrap.join_lines"
        }
        assert (score.chars.before, score.chars.after) == (0, 0)
        assert score.raw_chars.before == 2  # the ligature counts in the raw track
        assert score.raw_chars.after == 0

    def test_a_correct_dehyphenation_is_layout_not_harm(self) -> None:
        # Line-level ground truth keeps the printed line-end hyphen (R-15).
        document = page_of(("The growers count the hives each spr-", box(0)), ("ing.", box(40)))
        truth_page = truth_of(("The growers count the hives each spr-", box(0)), ("ing.", box(40)))
        score = score_page(clean(document), truth_page)
        assert clean(document).text.endswith("each spring.")
        assert {label.edit.rule: label.label for label in score.labels} == {
            "hyphenation.join": "layout",
            "unwrap.join_lines": "layout",
        }
        assert (score.chars.before, score.chars.after, score.harm_chars) == (0, 0, 0)

    def test_an_ocr_error_at_a_line_end_still_counts(self) -> None:
        # The OCR misread the hyphen, so LECTRIS cannot rejoin the word; the reference is.
        document = page_of(("each spr~", box(0)), ("ing.", box(40)))
        score = score_page(clean(document), truth_of(("each spr-", box(0)), ("ing.", box(40))))
        assert score.chars.before == 1
        assert score.chars.after == 2  # "spr~ ing." against "spring."

    def test_the_reference_follows_the_systems_policy(self) -> None:
        document = page_of(("each spr-", box(0)), ("ing.", box(40)))
        truth_page = truth_of(("each spr-", box(0)), ("ing.", box(40)))
        score = score_page(clean(document, policy=NONE), truth_page)
        assert (score.chars.before, score.chars.after) == (0, 0)  # neither side rejoins

    def test_the_reference_is_rejoined_where_the_system_rejoined(self) -> None:
        # A policy that decides on the OCR text and the ground truth differently (as the risk
        # policy does: the pack scores only the OCR's candidates) must not lay the reference out
        # differently: the join the system made is carried over, so only the misread counts.
        def score(candidate: Candidate) -> float:
            return 1.0 if "0" in candidate.after else 0.0

        document = page_of(("the infor-", box(0)), ("mati0n is", box(40)))
        truth_page = truth_of(("the infor-", box(0)), ("mation is", box(40)))
        result = clean(document, policy=Threshold(score, 0.5))
        assert result.blocks[0].text == "the informati0n is"
        found = score_page(result, truth_page)
        assert (found.chars.before, found.chars.after) == (1, 1)

    def test_a_join_carries_over_only_between_matched_neighbours(self) -> None:
        assert _reference_joins(frozenset({0, 2}), (0, 1, 2, 3)) == {0, 2}
        assert _reference_joins(frozenset({0, 2}), (0, 2, 3)) == {1}  # line 1 has no truth
        assert _reference_joins(frozenset({1}), (0, 2)) == frozenset()

    def test_lay_out_joins_at_the_given_junctions_only(self) -> None:
        steps = get("conservative").steps
        text = "the infor-\nmation and the exam-\nple"
        assert lay_out(text, steps, NONE, joins=frozenset({1})) == (
            "the infor-\nmation and the\nexample"
        )
        assert lay_out(text, steps, NONE) == text  # no joins given: the policy decides

    def test_unmatched_lines_are_insertions_and_deletions(self) -> None:
        document = page_of(("kept", box(0)), ("speck", box(300)))
        score = score_page(
            clean(document, profile="conservative"),
            truth_of(("kept", box(0)), ("lost line", box(100))),
        )
        # "speck" and the space before it are inserted (6), "lost line" deleted (9)
        assert (score.chars.reference, score.chars.before, score.chars.after) == (13, 15, 15)
        assert (score.matched_lines, score.ocr_lines, score.truth_lines) == (1, 2, 2)

    def test_without_boxes_the_page_is_one_block(self) -> None:
        result = clean("They counted 1O5\nhives.")
        score = score_page(result, truth_of(("They counted 105", None), ("hives.", None)))
        assert (score.chars.before, score.chars.after) == (1, 0)
        labels = [label.label for label in score.labels if label.label != "neutral"]
        assert labels == ["layout", "fix"]  # the unwrapping, then 1O5

    def test_the_none_policy_changes_only_by_transforms(self) -> None:
        document = page_of(("They counted 1O5 hives.", box(0)))
        score = score_page(
            clean(document, policy=NONE), truth_of(("They counted 105 hives.", box(0)))
        )
        assert (score.chars.before, score.chars.after, score.labels) == (1, 1, ())

    def test_words(self) -> None:
        document = page_of(("They counted 1O5 hives.", box(0)))
        score = score_page(clean(document), truth_of(("They counted 105 hives.", box(0))))
        assert (score.words.reference, score.words.before, score.words.after) == (4, 1, 0)


class TestBootstrap:
    def test_the_estimate_and_a_deterministic_interval(self) -> None:
        units = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        mean = bootstrap(units, lambda s: sum(s) / len(s), resamples=200, seed=7)
        assert mean.estimate == 3.5
        assert mean.low < 3.5 < mean.high
        assert mean == bootstrap(units, lambda s: sum(s) / len(s), resamples=200, seed=7)
        assert not mean.excludes_zero or mean.low > 0

    def test_a_constant_has_no_spread(self) -> None:
        found = bootstrap([2.0] * 10, lambda s: sum(s) / len(s))
        assert (found.estimate, found.low, found.high) == (2.0, 2.0, 2.0)
        assert found.excludes_zero

    @pytest.mark.parametrize(
        ("units", "options", "message"),
        [
            ([], {}, "at least one unit"),
            ([1.0], {"resamples": 0}, "resamples is at least 1"),
            ([1.0], {"level": 1.0}, "the level is in"),
        ],
    )
    def test_arguments_are_checked(
        self, units: list[float], options: dict[str, Any], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            bootstrap(units, sum, **options)

    def test_ratio(self) -> None:
        assert ratio([1, 2], [10, 10]) == 0.15
        assert ratio([], []) == 0.0

    @given(st.lists(st.floats(-100, 100), min_size=1, max_size=20))
    def test_the_interval_holds_the_resampled_values(self, units: list[float]) -> None:
        found = bootstrap(units, max, resamples=50)
        assert min(units) <= found.low <= found.high <= max(units)


class TestTruth:
    def test_round_trip_and_errors(self) -> None:
        page = TruthPage("a1", (TruthLine("one", Box(0, 0, 1, 1)), TruthLine("two")), 10, 20)
        assert truth.parse(truth.dumps(page)) == page
        assert page.text == "one\ntwo"
        with pytest.raises(FormatError, match=r"lines\[0\]: 'text' is missing"):
            truth.parse('{"page": "a", "lines": [{}]}')


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def glypharis_page(text: str) -> dict[str, Any]:
    return {
        "glypharis_version": "1.0.0",
        "model_version": "glypharis-1.0.0",
        "width": 600,
        "height": 200,
        "lines": [{"text": text, "confidence": 0.9, "det_score": 0.9, "bbox": [0, 0, 500, 30]}],
    }


@pytest.fixture
def config(tmp_path: Path) -> Path:
    pages = []
    for page, ocr, correct in [
        ("a", "They counted 1O5 hives.", "They counted 105 hives."),
        ("b", "Part 1O5 fits.", "Part 1O5 fits."),
        ("c", "Bees came late.", "Bees came late."),
    ]:
        write_json(tmp_path / "engine" / f"{page}.json", glypharis_page(ocr))
        write_json(
            tmp_path / "truth" / f"{page}.json",
            {"page": page, "lines": [{"text": correct, "box": [0, 0, 500, 30]}]},
        )
        pages.append(
            {"page": page, "engine": f"../engine/{page}.json", "truth": f"../truth/{page}.json"}
        )
    write_json(tmp_path / "manifests" / "pairs.json", {"pages": pages})
    return write_json(
        tmp_path / "configs" / "LX-TEST-001.json",
        {
            "id": "LX-TEST-001",
            "question": "A dry run on three hand-made pages.",
            "pairs": "../manifests/pairs.json",
            "systems": [
                {"name": "B0", "profile": "standard", "policy": "none"},
                {"name": "B1", "profile": "standard", "policy": "parity"},
            ],
            "resamples": 100,
        },
    )


class TestExperiment:
    def test_a_dry_run_writes_its_report(
        self, config: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["experiment", "run", str(config), "-o", str(tmp_path / "reports")]) == 0
        folder = tmp_path / "reports" / "LX-TEST-001"
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        assert str(folder / "report.json") in capsys.readouterr().out
        assert report["pages"] == 3
        assert report["lines"] == {"ocr": 3, "truth": 3, "matched": 3}
        b0, b1 = report["results"]["B0"], report["results"]["B1"]
        assert (b0["fixes"], b0["harms"]) == (0, 0)
        assert (b1["fixes"], b1["harms"], b1["precision"]) == (1, 1, 0.5)
        assert b1["by_rule"] == {
            "confusables.in_numbers": {"fix": 1, "harm": 1, "neutral": 0, "layout": 0, "effect": 0}
        }
        assert b0["by_rule"] == {}
        assert (
            b1["cer"]["estimate"]
            == b0["cer"]["estimate"]
            == report["uncorrected"]["cer"]["estimate"]
        )
        assert b1["pages_worse"] == pytest.approx(1 / 3)
        markdown = (folder / "report.md").read_text(encoding="utf-8")
        assert markdown.startswith("# LX-TEST-001")
        assert "| B1 |" in markdown
        assert "They counted" not in markdown + json.dumps(report)  # aggregates only

    def test_paired_comparisons(self, config: Path, tmp_path: Path) -> None:
        data = json.loads(config.read_text(encoding="utf-8")) | {"compare": [["B1", "B0"]]}
        config.write_text(json.dumps(data), encoding="utf-8")
        report = experiment.run(experiment.load_config(config))
        comparison = report["comparisons"]["B1 vs B0"]
        assert comparison["fixed"]["estimate"] > 0  # B1 repaired 1O5, B0 nothing
        assert comparison["harmed"]["estimate"] > 0  # and broke the real 1O5
        assert "## Paired comparisons" in experiment.markdown(report)
        bad = data | {"compare": [["B1", "nobody"]]}
        config.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(FormatError, match="no system called 'nobody'"):
            experiment.load_config(config)

    def test_the_report_is_the_same_on_every_run(self, config: Path) -> None:
        first = experiment.run(experiment.load_config(config))
        assert experiment.run(experiment.load_config(config)) == first

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"systems": []}, "at least one system"),
            ({"systems": [{"name": "x"}, {"name": "x"}]}, "each system's name is given once"),
            ({"systems": [{"name": "x", "profile": "fast"}]}, "no profile called 'fast'"),
            ({"systems": [{"name": "x", "policy": "magic"}]}, "one of parity, none"),
            ({"resamples": -1}, "resamples: a whole number"),
        ],
    )
    def test_a_bad_configuration_is_refused(
        self, config: Path, change: dict[str, Any], message: str
    ) -> None:
        data = json.loads(config.read_text(encoding="utf-8")) | change
        config.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(FormatError, match=message):
            experiment.load_config(config)

    def test_a_threshold_policy_can_be_used_in_code(self) -> None:
        policy = Threshold(lambda _: 0.2, 0.5)
        document = page_of(("They counted 1O5 hives.", box(0)))
        assert clean(document, policy=policy).text == "They counted 1O5 hives."
