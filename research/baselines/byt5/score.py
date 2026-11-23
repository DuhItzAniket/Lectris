"""B3, step 4: score ByT5 against LECTRIS on the same dev pages (protocol §6; H5).

- **CER:** every system's output is cleaned and scored by ``lectris.eval`` against references laid
  out as that system lays out its text. ByT5's corrected lines go through LECTRIS with no guess
  accepted (the transforms and layout only, as B0), so the layout is the same as B0's.
- **Repaired and broken characters:** LECTRIS's from its edit labels. ByT5 rewrites whole lines,
  so each rewritten line is one edit, labelled by its exact effect on that line's distance to its
  ground truth (normalised track): below zero it repairs, above zero it breaks. A rewritten OCR
  line with no ground truth adds its change in length. The harm rate is the characters broken per
  reference character, as for LECTRIS.
- **Harm matching (H5):** ByT5 keeps a line's correction only when its mean byte log probability
  reaches a threshold ``tau``; over a grid of ``tau``, the most permissive ByT5 whose harm rate is
  at most LECTRIS-standard's is compared with it, CER paired over pages.

Aggregates only.

    uv run python score.py --id LX-BASE-002 --pairs DEV --b3 B3DEV --pack P --out OUT
"""

import argparse
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lectris import clean
from lectris.decide import PARITY
from lectris.eval import truth as truth_io
from lectris.eval.experiment import NONE, load_pairs
from lectris.eval.matching import match_lines
from lectris.eval.scoring import drop_dont_care, normalised, score_page
from lectris.eval.stats import bootstrap, ratio
from lectris.io import glypharis
from lectris.metrics import char_errors
from lectris.models import pack


def b3_document(corrected: dict[str, Any], tau: float) -> str:
    """The corrected page with each line's correction kept only if its log probability >= tau."""
    data = json.loads(json.dumps(corrected))
    for line in data["lines"]:
        if line.get("b3_logprob", 0.0) < tau:
            line["text"] = line.get("b3_source", line["text"])
    return json.dumps(data)


def b3_effects(original: str, corrected: str, truth: truth_io.TruthPage) -> tuple[int, int]:
    """(repaired, broken) characters of ByT5's line rewrites on one page."""
    before = drop_dont_care(glypharis.parse(original), truth)
    after = drop_dont_care(glypharis.parse(corrected), truth)
    old = [line for page in before.pages for line in page.lines]
    new = [line for page in after.pages for line in page.lines]
    if len(old) != len(new):
        raise ValueError("the corrected page lost or gained lines")
    counted = truth.counted
    matching = match_lines([line.box for line in old], [line.box for line in counted.lines])
    of = dict(matching.pairs)
    repaired = broken = 0
    for i, (a, b) in enumerate(zip(old, new, strict=True)):
        if a.text == b.text:
            continue
        if i in of:
            reference = normalised(counted.lines[of[i]].text)
            effect = (
                char_errors(reference, normalised(b.text)).errors
                - char_errors(reference, normalised(a.text)).errors
            )
        else:
            effect = len(normalised(b.text)) - len(normalised(a.text))
        repaired += max(0, -effect)
        broken += max(0, effect)
    return repaired, broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--id", required=True)
    parser.add_argument("--pairs", type=Path, required=True, help="the dev pairs (engine output)")
    parser.add_argument("--b3", type=Path, required=True, help="the corrected pages' manifest")
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1337)
    arguments = parser.parse_args()
    model = pack.load(arguments.pack)
    risk = model.policy("standard")
    corrected = {p.page: p.engine for p in load_pairs(arguments.b3)}
    pages: list[dict[str, Any]] = []
    for pair in load_pairs(arguments.pairs):
        truth = truth_io.read(pair.truth)
        original = pair.engine.read_text(encoding="utf-8")
        fixed_json = json.loads(corrected[pair.page].read_text(encoding="utf-8"))
        document = drop_dont_care(glypharis.parse(original), truth)
        base = score_page(clean(document, policy=NONE), truth)
        lx = score_page(clean(document, policy=risk, pack=model), truth)
        b1 = score_page(clean(document, policy=PARITY), truth)
        page: dict[str, Any] = {
            "reference": base.chars.reference,
            "uncorrected": base.chars.before,
            "B1": (b1.chars.after, b1.fixed_chars, b1.harm_chars),
            "LX": (lx.chars.after, lx.fixed_chars, lx.harm_chars),
            "B3": {},
        }
        for tau in TAUS:
            text = b3_document(fixed_json, tau)
            result = score_page(
                clean(drop_dont_care(glypharis.parse(text), truth), policy=NONE), truth
            )
            repaired, broken = b3_effects(original, text, truth)
            page["B3"][tau] = (result.chars.after, repaired, broken)
        pages.append(page)

    def summary(get: Any) -> dict[str, Any]:
        def cer(s: Sequence[dict[str, Any]]) -> float:
            return ratio([get(p)[0] for p in s], [p["reference"] for p in s])

        def change(s: Sequence[dict[str, Any]]) -> float:
            return ratio([get(p)[0] - p["uncorrected"] for p in s], [p["reference"] for p in s])

        options = {"resamples": arguments.resamples, "seed": arguments.seed}
        return {
            "cer": _iv(bootstrap(pages, cer, **options)),
            "cer_change": _iv(bootstrap(pages, change, **options)),
            "repaired_rate": ratio([get(p)[1] for p in pages], [p["reference"] for p in pages]),
            "harm_rate": ratio([get(p)[2] for p in pages], [p["reference"] for p in pages]),
            "pages_worse": sum(1 for p in pages if get(p)[0] > p["uncorrected"]) / len(pages),
        }

    systems = {
        "B1-standard": summary(lambda p: p["B1"]),
        "LX-standard": summary(lambda p: p["LX"]),
        **{f"B3 (tau {_tau(t)})": summary(lambda p, t=t: p["B3"][t]) for t in TAUS},
    }
    lx_harm = systems["LX-standard"]["harm_rate"]
    matched = [t for t in TAUS if systems[f"B3 (tau {_tau(t)})"]["harm_rate"] <= lx_harm]
    comparison = None
    if matched:
        tau = min(matched)  # the most permissive ByT5 within LECTRIS's harm

        def gap(s: Sequence[dict[str, Any]], t: float = tau) -> float:
            return ratio([p["LX"][0] - p["B3"][t][0] for p in s], [p["reference"] for p in s])

        comparison = {
            "tau": tau,
            "lx_minus_b3_cer": _iv(
                bootstrap(pages, gap, resamples=arguments.resamples, seed=arguments.seed)
            ),
        }
    all_in = f"B3 (tau {_tau(TAUS[0])})"

    def full_gap(s: Sequence[dict[str, Any]]) -> float:
        return ratio([p["LX"][0] - p["B3"][TAUS[0]][0] for p in s], [p["reference"] for p in s])

    result = {
        "id": arguments.id,
        "pages": len(pages),
        "systems": systems,
        "lx_minus_b3_all_cer": _iv(
            bootstrap(pages, full_gap, resamples=arguments.resamples, seed=arguments.seed)
        ),
        "harm_matched": comparison,
        "b3_all": all_in,
    }
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (arguments.out / "report.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    print(markdown(result))
    return 0


TAUS = (-math.inf, -1.0, -0.5, -0.3, -0.2, -0.1, -0.05, -0.02, -0.01, -0.005, 0.0)


def _tau(t: float) -> str:
    return "any" if t == -math.inf else f"{t:g}"


def _iv(found: Any) -> dict[str, float]:
    return {"estimate": found.estimate, "low": found.low, "high": found.high}


def _points(v: dict[str, float]) -> str:
    return f"{100 * v['estimate']:+.2f} [{100 * v['low']:+.2f}, {100 * v['high']:+.2f}]"


def markdown(result: dict[str, Any]) -> str:
    rows = [
        f"# {result['id']}",
        "",
        "Baseline B3 (ByT5-small fine-tuned on the fit split's line pairs) against LECTRIS on "
        f"{result['pages']} dev pages; B3 keeps a line's correction when its mean byte log "
        "probability reaches tau. Generated by `research/baselines/byt5/score.py`; aggregates "
        "only.",
        "",
        "| System | CER | ΔCER vs uncorrected (points) | Repaired | Harm rate | Pages worse |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in result["systems"].items():
        rows.append(
            f"| {name} | {100 * s['cer']['estimate']:.2f}% | {_points(s['cer_change'])} | "
            f"{100 * s['repaired_rate']:.3f}% | {100 * s['harm_rate']:.3f}% | "
            f"{100 * s['pages_worse']:.1f}% |"
        )
    rows += [
        "",
        "- LX-standard minus B3 (every correction kept), CER: "
        f"{_points(result['lx_minus_b3_all_cer'])} points.",
    ]
    if result["harm_matched"]:
        m = result["harm_matched"]
        rows.append(
            f"- Harm-matched: the most permissive B3 within LX-standard's harm rate keeps "
            f"corrections with log probability >= {_tau(m['tau'])}; LX-standard minus it, CER: "
            f"{_points(m['lx_minus_b3_cer'])} points."
        )
    else:
        rows.append("- No B3 threshold on the grid keeps its harm rate within LX-standard's.")
    rows.append("")
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
