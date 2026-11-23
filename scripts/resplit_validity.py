"""H3: does the risk guarantee hold across random calibration/test splits? (protocol §5)

The pages of two pairs manifests (cal and dev) are pooled. Each page is cleaned once per profile
with a calibrated pack under ``PARITY``, and its candidates get their probability (the pack's
acceptance model, fitted on other pages) and their exact marginal effect. From these, each
page's estimated loss and net effect at every threshold of the grid are tabulated once. Then, for
each of ``--resplits`` random splits of the pooled pages into a calibration part (the size of the
cal manifest) and a test part:

- Learn-then-Test certifies thresholds on the calibration part (``models.risk``), and the most
  useful certified one is chosen (ADR-0009), as ``lectris calibrate`` does;
- the test part's mean loss at that threshold is compared with ``alpha``: above it, the split is
  a **violation**; H3 expects at most ``delta`` of the splits to be violations;
- the **oracle** is the most permissive threshold whose test loss is at most ``alpha``, chosen on
  the test part itself; the recall gap is the share of the oracle's repaired characters the
  chosen threshold does not repair.

Losses are estimated from each candidate's effect where ``PARITY`` proposed it (the same
approximation ``lectris calibrate`` makes); full runs on one split are LX-RISK-001's. Aggregates
only.

    uv run python scripts/resplit_validity.py --id LX-RISK-002 --pack P --cal CAL --dev DEV \\
        --out reports/LX-RISK-002
"""

import argparse
import json
import math
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lectris.eval.calibrate import PageCandidates, page_candidates
from lectris.eval.experiment import load_pairs
from lectris.models import pack
from lectris.models.risk import grid, hoeffding_bentkus


@dataclass(frozen=True)
class Tables:
    """Per page and threshold: the estimated loss, the net effect and the characters fixed; and
    per page, the characters its candidates could fix."""

    losses: list[list[float]]
    nets: list[list[int]]
    fixed: list[list[int]]
    fixable: list[int]


def tables(
    pages: Sequence[PageCandidates], model: pack.ModelPack, thresholds: Sequence[float]
) -> Tables:
    """The tables of ``pages`` at ``thresholds``."""
    if model.acceptance is None:
        raise pack.PackError("the pack has no acceptance model")
    losses, nets, fixed, fixable = [], [], [], []
    for page in pages:
        scored = [(model.acceptance.probability(i.candidate), i.effect) for i in page.candidates]
        reference = max(1, page.reference_chars)
        losses.append(
            [min(1.0, sum(max(e, 0) for p, e in scored if p >= t) / reference) for t in thresholds]
        )
        nets.append([sum(e for p, e in scored if p >= t) for t in thresholds])
        fixed.append([sum(-e for p, e in scored if p >= t and e < 0) for t in thresholds])
        fixable.append(sum(-e for _, e in scored if e < 0))
    return Tables(losses, nets, fixed, fixable)


def certify(found: Tables, pages: Sequence[int], budget: pack.Budget, steps: int) -> list[int]:
    """The grid indexes fixed-sequence testing certifies on ``pages``."""
    certified = []
    for k in range(steps):
        mean = sum(found.losses[i][k] for i in pages) / len(pages)
        if hoeffding_bentkus(mean, len(pages), budget.alpha) > budget.delta:
            break
        certified.append(k)
    return certified


def validate(
    found: Tables,
    budget: pack.Budget,
    thresholds: Sequence[float],
    *,
    calibration_size: int,
    resplits: int,
    seed: int,
) -> dict[str, Any]:
    """One profile's validity over ``resplits`` random splits (the module's documentation)."""
    generator = random.Random(seed)  # noqa: S311 - resampling, not secrets
    order = list(range(len(found.losses)))
    violations = without = 0
    test_losses: list[float] = []
    gaps: list[float] = []
    chosen: list[float] = []
    for _ in range(resplits):
        generator.shuffle(order)
        calibration, test = order[:calibration_size], order[calibration_size:]
        certified = certify(found, calibration, budget, len(thresholds))
        if not certified:
            without += 1
            continue
        best = min(
            certified, key=lambda k: (sum(found.nets[i][k] for i in calibration), -thresholds[k])
        )
        loss = sum(found.losses[i][best] for i in test) / len(test)
        violations += loss > budget.alpha
        test_losses.append(loss)
        chosen.append(thresholds[best])
        within = [
            k
            for k in range(len(thresholds))
            if sum(found.losses[i][k] for i in test) / len(test) <= budget.alpha
        ]
        oracle = max(within, key=lambda k: -thresholds[k]) if within else best
        total = max(1, sum(found.fixable[i] for i in test))
        ours = sum(found.fixed[i][best] for i in test) / total
        theirs = sum(found.fixed[i][oracle] for i in test) / total
        gaps.append((theirs - ours) / theirs if theirs else 0.0)
    runs = max(1, len(test_losses))
    return {
        "alpha": budget.alpha,
        "delta": budget.delta,
        "resplits": resplits,
        "no_threshold": without,
        "violations": violations,
        "violation_share": violations / runs,
        "binomial_upper_95": _upper(violations, runs),
        "test_loss_mean": sum(test_losses) / runs,
        "test_loss_max": max(test_losses, default=0.0),
        "threshold_mean": sum(chosen) / runs,
        "recall_gap_mean": sum(gaps) / runs,
        "pages": len(found.losses),
        "calibration_pages": calibration_size,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--id", required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--cal", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resplits", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1337)
    arguments = parser.parse_args(argv)

    model = pack.load(arguments.pack)
    if model.risk is None:
        sys.stderr.write("the pack is not calibrated\n")
        return 1
    cal, dev = load_pairs(arguments.cal), load_pairs(arguments.dev)
    thresholds = grid(100)
    results = {
        profile: validate(
            tables(page_candidates((*cal, *dev), model, profile), model, thresholds),
            budget,
            thresholds,
            calibration_size=len(cal),
            resplits=arguments.resplits,
            seed=arguments.seed,
        )
        for profile, budget in sorted(model.risk.items())
    }
    result = {"id": arguments.id, "seed": arguments.seed, "profiles": results}
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (arguments.out / "report.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    sys.stdout.write(markdown(result))
    return 0


def _upper(k: int, n: int) -> float:
    """A 95% upper bound for a binomial share (the Wilson score bound)."""
    z = 1.96
    p = k / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + spread) / (1 + z * z / n)


def markdown(result: dict[str, Any]) -> str:
    rows = [
        f"# {result['id']}",
        "",
        "H3: the risk guarantee across random calibration/test splits of the pooled cal and dev "
        "pages, with losses estimated from each candidate's marginal effect. Generated by "
        "`scripts/resplit_validity.py`; aggregates only.",
        "",
        "| Profile | alpha | delta | Re-splits | No threshold | Violations | Share [95% upper] "
        "| Mean test loss | Max test loss | Mean threshold | Recall gap to the oracle |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    rows.extend(
        f"| {name} | {p['alpha']} | {p['delta']} | {p['resplits']} | {p['no_threshold']} | "
        f"{p['violations']} | {p['violation_share']:.3f} [{p['binomial_upper_95']:.3f}] | "
        f"{p['test_loss_mean']:.5f} | {p['test_loss_max']:.5f} | {p['threshold_mean']:.3f} | "
        f"{100 * p['recall_gap_mean']:.1f}% |"
        for name, p in result["profiles"].items()
    )
    rows += [
        "",
        "A violation is a split whose test loss at the chosen threshold exceeds alpha; H3 expects "
        "a share of at most delta. The oracle is the most permissive threshold whose test loss is "
        "within alpha, chosen on the test pages; the recall gap is the share of the oracle's "
        "repaired characters the chosen threshold does not repair.",
        "",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
