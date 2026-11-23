"""Calibrating a model pack: its acceptance model and each profile's risk-controlled threshold.

``calibrate(pack, fit, cal)`` (architecture §11; ADR-0002):

1. **Training data.** Every page of the ``fit`` pairs is cleaned with the pack under ``PARITY``
   with the ``standard`` profile, and every candidate (accepted or not, layout rules aside) is
   labelled by its exact marginal effect (``scoring.label_candidates``): 1 if it brings its block
   closer to the reference, else 0.
2. **Acceptance.** A logistic regression on those examples (``models.acceptance``).
3. **Risk.** For each profile, every page of the ``cal`` pairs is cleaned the same way with that
   profile, and its candidates get their probabilities. A page's loss at a threshold is the
   characters broken by the harmful candidates whose probability reaches it, over the page's
   reference length (at most 1). Learn-then-Test (``models.risk``) certifies the thresholds whose
   mean loss is below the profile's ``alpha`` with confidence ``1 - delta``, and the one used is
   the certified threshold with the largest estimated CER reduction on the cal pages (the most
   negative sum of the accepted candidates' effects; the strictest on a tie, ADR-0009).
4. **Calibration.** The expected calibration error and the Brier score of the probabilities on
   the ``cal`` candidates of the ``standard`` profile.

The loss at a threshold is estimated from each candidate's effect where ``PARITY`` proposed it:
a policy that accepts other candidates changes the text later stages see, and overlapping
candidates exclude each other. So the estimate is an approximation of the risk ``risk_policy``
runs at; the guarantee's validity is measured with full runs on held-out pages (protocol §5).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from lectris import io
from lectris.decide import PARITY, Threshold
from lectris.eval import truth as truth_io
from lectris.eval.experiment import Pair
from lectris.eval.scoring import LabelledCandidate, drop_dont_care, label_candidates
from lectris.models.acceptance import Acceptance, calibration
from lectris.models.pack import Budget, ModelPack
from lectris.models.risk import certified, grid
from lectris.pipeline import clean

BUDGETS: Final = {"conservative": 0.01, "standard": 0.02, "aggressive": 0.05}
"""Each profile's harm-rate budget ``alpha`` (ADR-0008: what 430 calibration pages can certify)."""

DELTA: Final = 0.1
"""The confidence the budgets are held with is ``1 - DELTA``."""


@dataclass(frozen=True, slots=True)
class PageCandidates:
    """One page's labelled candidates, and its reference length."""

    page: str
    candidates: tuple[LabelledCandidate, ...]
    reference_chars: int


def page_candidates(
    pairs: Sequence[Pair], pack: ModelPack, profile: str, *, iou_threshold: float = 0.5
) -> list[PageCandidates]:
    """Each page cleaned with ``pack`` under ``PARITY``, with its labelled candidates."""
    found = []
    for pair in pairs:
        truth = truth_io.read(pair.truth)
        document = drop_dont_care(io.read(pair.engine), truth, iou_threshold=iou_threshold)
        result = clean(document, profile=profile, policy=PARITY, pack=pack)
        labelled = label_candidates(result, truth, iou_threshold=iou_threshold)
        chars = sum(len(line.text) for line in truth.counted.lines)
        found.append(PageCandidates(pair.page, tuple(labelled), chars))
    return found


def page_losses(
    pages: Sequence[PageCandidates], acceptance: Acceptance
) -> list[list[tuple[float, int]]]:
    """Each page's candidates as ``(probability, harm)``, ``harm`` the characters it breaks."""
    return [
        [(acceptance.probability(item.candidate), max(item.effect, 0)) for item in page.candidates]
        for page in pages
    ]


def most_useful(
    thresholds: Sequence[float], pages: Sequence[PageCandidates], acceptance: Acceptance
) -> float | None:
    """Among ``thresholds``, the one with the most negative net effect; the highest on a tie."""
    if not thresholds:
        return None
    effects: list[tuple[float, float]] = []
    probability = {
        id(item): acceptance.probability(item.candidate)
        for page in pages
        for item in page.candidates
    }
    for threshold in thresholds:
        total = sum(
            item.effect
            for page in pages
            for item in page.candidates
            if probability[id(item)] >= threshold
        )
        effects.append((total, -threshold))
    best = min(effects)
    return -best[1]


def loss_at(
    threshold: float, scored: Sequence[Sequence[tuple[float, int]]], pages: Sequence[PageCandidates]
) -> list[float]:
    """Each page's estimated loss at ``threshold`` (see the module's documentation)."""
    return [
        min(1.0, sum(harm for p, harm in items if p >= threshold) / max(1, page.reference_chars))
        for items, page in zip(scored, pages, strict=True)
    ]


def calibrate(
    pack: ModelPack,
    fit: Sequence[Pair],
    cal: Sequence[Pair],
    *,
    budgets: Mapping[str, float] = BUDGETS,
    delta: float = DELTA,
    steps: int = 100,
    l2: float = 1.0,
    exclude: Sequence[str] = (),
) -> ModelPack:
    """``pack`` with its acceptance model, risk budgets and calibration (module documentation).

    ``exclude`` names features the acceptance model is fitted without (an ablation: the model
    then never sees them, whatever candidates carry)."""
    training = page_candidates(fit, pack, "standard")
    left_out = set(exclude)
    examples = [
        (
            {k: v for k, v in item.candidate.features if k not in left_out},
            1 if item.fixes else 0,
        )
        for page in training
        for item in page.candidates
    ]
    acceptance = Acceptance.fit(examples, l2=l2)
    risk: dict[str, Budget] = {}
    summary: dict[str, object] = {
        "fit_pages": len(fit),
        "fit_candidates": len(examples),
        "fit_fixes": sum(label for _, label in examples),
        "cal_pages": len(cal),
        "l2": l2,
        "grid_steps": steps,
        "excluded_features": sorted(left_out),
    }
    for profile, alpha in sorted(budgets.items()):
        pages = page_candidates(cal, pack, profile)
        scored = page_losses(pages, acceptance)

        def losses(
            threshold: float,
            scored: Sequence[Sequence[tuple[float, int]]] = scored,
            pages: Sequence[PageCandidates] = pages,
        ) -> list[float]:
            return loss_at(threshold, scored, pages)

        valid = certified(losses, grid(steps), alpha=alpha, delta=delta)
        risk[profile] = Budget(
            alpha,
            delta,
            most_useful(valid, pages, acceptance),
            len(pages),
            valid[-1] if valid else None,
        )
        if profile == "standard":
            probabilities = [p for items in scored for p, _ in items]
            labels = [1 if item.fixes else 0 for page in pages for item in page.candidates]
            if probabilities:
                measured = calibration(probabilities, labels)
                summary |= {
                    "cal_candidates": len(probabilities),
                    "cal_fixes": sum(labels),
                    "ece": measured.ece,
                    "brier": measured.brier,
                    "reliability": [list(row) for row in measured.bins],
                }
    return replace(pack, acceptance=acceptance, risk=risk, calibration=summary)


def risk_policy(pack: ModelPack, profile: str) -> Threshold:
    """The ``risk`` policy of ``profile`` (``ModelPack.policy``)."""
    return pack.policy(profile)
