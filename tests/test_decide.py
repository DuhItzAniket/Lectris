from itertools import combinations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.decide import PARITY, Threshold, decide
from lectris.edits import Candidate, apply_edits


def candidate(start: int, end: int, after: str, text: str, *, v01: float = 1.0) -> Candidate:
    return Candidate("demo.rule", start, end, text[start:end], after, (("v01", v01),))


def by_score(scores: dict[str, float]) -> Threshold:
    return Threshold(lambda c: scores[c.after], 0.5)


class TestParity:
    def test_it_accepts_what_v01_applies_and_declines_the_rest(self) -> None:
        text = "1O5 and l0ng"
        revision = decide(
            text, [candidate(1, 2, "0", text), candidate(9, 10, "o", text, v01=0.0)], PARITY
        )
        assert revision.text == "105 and l0ng"
        assert [(d.accepted, d.reason) for d in revision.decisions] == [
            (True, "the v0.1 rule applies it"),
            (False, "the v0.1 rule declines it"),
        ]
        assert [edit.after for edit in revision.edits] == ["0"]

    def test_no_candidates_is_no_change(self) -> None:
        revision = decide("text", [])
        assert (revision.text, revision.edits, revision.decisions) == ("text", (), ())


class TestThreshold:
    def test_it_accepts_what_reaches_the_threshold(self) -> None:
        text = "modem rnodem"
        revision = decide(
            text,
            [candidate(0, 5, "modern", text), candidate(6, 12, "modem", text)],
            by_score({"modern": 0.4, "modem": 0.9}),
        )
        assert revision.text == "modem modem"
        first, second = revision.decisions
        assert (first.accepted, first.probability, first.threshold) == (False, 0.4, 0.5)
        assert (second.accepted, second.reason) == (True, "its probability reaches the threshold")

    @pytest.mark.parametrize("threshold", [-0.1, 1.1])
    def test_a_threshold_is_a_probability(self, threshold: float) -> None:
        with pytest.raises(ValueError, match="a threshold is between 0 and 1"):
            Threshold(lambda _: 0.5, threshold)

    def test_a_score_outside_0_and_1_is_refused(self) -> None:
        with pytest.raises(ValueError, match="a score is a probability"):
            decide("ab", [candidate(0, 1, "x", "ab")], Threshold(lambda _: 1.5, 0.5))


class TestOverlaps:
    def test_the_better_of_two_overlapping_candidates_wins(self) -> None:
        text = "rnodem"
        whole = candidate(0, 6, "modern", text)  # 0.6 * 6
        part = candidate(0, 2, "m", text)  # 0.9 * 2
        revision = decide(text, [part, whole], by_score({"modern": 0.6, "m": 0.9}))
        assert revision.text == "modern"
        reasons = {d.candidate.after: (d.accepted, d.reason) for d in revision.decisions}
        assert reasons["m"] == (False, "it overlaps a better candidate")

    def test_a_tie_leaves_the_text_as_it_was(self) -> None:
        text = "ab"
        revision = decide(
            text,
            [candidate(0, 2, "xy", text), candidate(0, 2, "yx", text)],
            by_score({"xy": 0.5, "yx": 0.5}),
        )
        accepted = [d.candidate.after for d in revision.decisions if d.accepted]
        assert len(accepted) == 1  # one of the two, never both
        assert revision.text in {"xy", "yx"}

    def test_insertions_at_the_edge_of_a_span_do_not_overlap_it(self) -> None:
        text = "ab"
        revision = decide(
            text,
            [candidate(0, 0, "<", text), candidate(0, 2, "AB", text), candidate(2, 2, ">", text)],
        )
        assert revision.text == "<AB>"

    def test_two_insertions_at_one_place_overlap(self) -> None:
        text = "ab"
        revision = decide(text, [candidate(1, 1, "x", text), candidate(1, 1, "yy", text)])
        assert revision.text == "ayyb"  # the larger expected change

    def test_an_insertion_inside_a_span_overlaps_it(self) -> None:
        text = "abc"
        revision = decide(text, [candidate(1, 1, "x", text), candidate(0, 3, "ABC", text)])
        assert revision.text == "ABC"

    def test_a_candidate_that_does_not_match_the_text_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected 'zz' at 0"):
            decide("ab", [Candidate("demo.rule", 0, 2, "zz", "y")])


@st.composite
def proposals(draw: st.DrawFn) -> tuple[str, list[Candidate]]:
    text = draw(st.text(alphabet="abc", min_size=1, max_size=8))
    found: list[Candidate] = []
    for _ in range(draw(st.integers(0, 6))):
        start = draw(st.integers(0, len(text)))
        end = draw(st.integers(start, min(len(text), start + 3)))
        after = draw(st.text(alphabet="xyz", max_size=3))
        if text[start:end] == after:
            continue
        score = draw(st.sampled_from([0.0, 0.3, 0.5, 0.7, 1.0]))
        found.append(Candidate("demo.rule", start, end, text[start:end], after, (("s", score),)))
    return text, found


def overlap(a: Candidate, b: Candidate) -> bool:
    if a.start == a.end == b.start == b.end:
        return True
    if a.start == a.end:
        return b.start < a.start < b.end
    if b.start == b.end:
        return a.start < b.start < a.end
    return a.start < b.end and b.start < a.end


def total(chosen: list[Candidate]) -> float:
    return sum(c.feature("s") * max(len(c.before), len(c.after), 1) for c in chosen)


@given(proposals())
def test_the_accepted_set_is_the_best_and_obeys_the_edit_contract(
    proposal: tuple[str, list[Candidate]],
) -> None:
    text, found = proposal
    policy = Threshold(lambda c: c.feature("s"), 0.5)
    revision = decide(text, found, policy)
    accepted = [d.candidate for d in revision.decisions if d.accepted]
    assert apply_edits(text, revision.edits) == revision.text
    assert [e.start for e in revision.edits] == sorted(e.start for e in revision.edits)
    assert len(revision.decisions) == len(found)
    assert all(c.feature("s") >= 0.5 for c in accepted)
    assert not any(overlap(a, b) for a, b in combinations(accepted, 2))
    passing = [c for c in found if c.feature("s") >= 0.5]
    best = max(
        (
            total(list(subset))
            for size in range(len(passing) + 1)
            for subset in combinations(passing, size)
            if not any(overlap(a, b) for a, b in combinations(subset, 2))
        ),
        default=0.0,
    )
    assert total(accepted) == pytest.approx(best)
