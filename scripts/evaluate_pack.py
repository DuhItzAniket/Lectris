"""Evaluate a model pack against Phase 6's exit criteria (docs/IMPLEMENTATION_PLAN.md).

On the pages of a held-out pairs manifest (dev):

- **language**: the per-character perplexity of the ground-truth lines that count, under the
  pack's character language model, with a bootstrap interval over pages;
- **channel**: the mean log-likelihood, per intended character, of each matched OCR line given
  its ground-truth line, under the pack's channel model and under a uniform-cost model (every
  character read right with probability 1 - e, every error with e / |alphabet|, e and the
  alphabet taken from the fit pages), and their paired difference over pages;
- **determinism**: whether a second fit of the same inputs (``--twin``) is the same file;
- the pack's size, n-grams, words and most frequent confusions.

The report is aggregates only (ground rule 5).

    uv run python scripts/evaluate_pack.py --pack P --twin P2 --fit FIT --dev DEV \\
        --out reports/LX-FIT-001 --fit-seconds S
"""

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lectris.align import align_chars
from lectris.eval.experiment import load_pairs
from lectris.eval.lines import PageLines, matched_lines
from lectris.eval.stats import bootstrap
from lectris.models import pack
from lectris.models.channel import uniform_log_likelihood


def uniform_parameters(pages: Sequence[PageLines]) -> tuple[float, int]:
    """The uniform model's error rate and alphabet size, from the fit pages' line pairs."""
    errors = total = 0
    alphabet: set[str] = set()
    for page in pages:
        for intended, observed in page.pairs:
            alphabet.update(intended + observed)
            for op in align_chars(intended, observed):
                total += 1
                errors += op.kind != "equal"
    return errors / total, len(alphabet) + 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--twin", type=Path, help="a second fit of the same inputs")
    parser.add_argument("--fit", type=Path, required=True, help="the fit pairs manifest")
    parser.add_argument("--dev", type=Path, required=True, help="the held-out pairs manifest")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fit-seconds", type=float, help="how long the fit took")
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1337)
    arguments = parser.parse_args(argv)

    model = pack.load(arguments.pack)
    error_rate, alphabet = uniform_parameters(list(matched_lines(load_pairs(arguments.fit))))
    units: list[dict[str, float]] = []
    for page in matched_lines(load_pairs(arguments.dev)):
        logprob = sum(model.language.score(text) for text in page.truth)
        chars = sum(len(text) for text in page.truth)
        intended = sum(len(a) for a, _ in page.pairs)
        channel = sum(model.channel.log_likelihood(a, b) for a, b in page.pairs)
        uniform = sum(uniform_log_likelihood(a, b, error_rate, alphabet) for a, b in page.pairs)
        units.append(
            {"logprob": logprob, "chars": chars, "intended": intended, "channel": channel,
             "uniform": uniform}
        )  # fmt: skip

    def perplexity(sample: Sequence[dict[str, float]]) -> float:
        chars = sum(u["chars"] for u in sample)
        return math.exp(-sum(u["logprob"] for u in sample) / chars)

    def per_char(key: str) -> Any:
        return lambda s: sum(u[key] for u in s) / max(1, sum(u["intended"] for u in s))

    def difference(sample: Sequence[dict[str, float]]) -> float:
        return float(per_char("channel")(sample) - per_char("uniform")(sample))

    options = {"resamples": arguments.resamples, "seed": arguments.seed}
    found = {
        "perplexity": bootstrap(units, perplexity, **options),
        "channel": bootstrap(units, per_char("channel"), **options),
        "uniform": bootstrap(units, per_char("uniform"), **options),
        "difference": bootstrap(units, difference, **options),
    }
    data = arguments.pack.read_bytes()
    result: dict[str, Any] = {
        "pack": {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "engine": model.engine,
            "model": model.model,
            "ngrams": model.language.size,
            "order": model.language.order,
            "words": len(model.lexicon),
            "sources": len(model.sources),
        },
        "fit_seconds": arguments.fit_seconds,
        "deterministic": None
        if arguments.twin is None
        else hashlib.sha256(arguments.twin.read_bytes()).hexdigest()
        == hashlib.sha256(data).hexdigest(),
        "dev_pages": len(units),
        "dev_chars": sum(u["chars"] for u in units),
        "dev_line_pairs_chars": sum(u["intended"] for u in units),
        "uniform_model": {"error_rate": error_rate, "alphabet": alphabet},
        "language_perplexity": vars_of(found["perplexity"]),
        "channel_log_likelihood_per_char": vars_of(found["channel"]),
        "uniform_log_likelihood_per_char": vars_of(found["uniform"]),
        "channel_minus_uniform": vars_of(found["difference"]),
        "top_confusions": [
            {"intended": a, "observed": b, "count": n} for a, b, n in model.channel.top(15)
        ],
    }
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    (arguments.out / "report.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    sys.stdout.write(markdown(result))
    return 0


def vars_of(interval: Any) -> dict[str, float]:
    return {"estimate": interval.estimate, "low": interval.low, "high": interval.high}


def _interval(value: dict[str, float], digits: int = 3) -> str:
    return f"{value['estimate']:.{digits}f} [{value['low']:.{digits}f}, {value['high']:.{digits}f}]"


def markdown(result: dict[str, Any]) -> str:
    packed = result["pack"]
    rows = [
        "# LX-FIT-001",
        "",
        "Phase 6: the evidence models fitted on the fit split, measured on the dev split. "
        "Generated by `scripts/evaluate_pack.py`; aggregates only.",
        "",
        f"- Pack: `{packed['sha256'][:16]}…`, {packed['bytes']:,} bytes; engine "
        f"{packed['engine']} / {packed['model']}; order-{packed['order']} language model with "
        f"{packed['ngrams']:,} n-grams; {packed['words']:,} words; {packed['sources']} sources",
        f"- Fit: {result['fit_seconds']} s; a second fit gives the same file: "
        f"{result['deterministic']}",
        f"- Dev: {result['dev_pages']} pages, {result['dev_chars']:,} ground-truth characters, "
        f"{result['dev_line_pairs_chars']:,} in matched line pairs",
        "",
        "| Measure | Value [95% bootstrap interval over pages] |",
        "|---|---|",
        f"| Language model perplexity per character | {_interval(result['language_perplexity'])} |",
        "| Channel log-likelihood per intended character | "
        f"{_interval(result['channel_log_likelihood_per_char'], 4)} |",
        "| Uniform-cost log-likelihood per intended character "
        f"(e = {result['uniform_model']['error_rate']:.4f}, "
        f"alphabet {result['uniform_model']['alphabet']}) | "
        f"{_interval(result['uniform_log_likelihood_per_char'], 4)} |",
        f"| Channel minus uniform | {_interval(result['channel_minus_uniform'], 4)} |",
        "",
        "## Most frequent confusions (fit split)",
        "",
        "| Intended | Observed | Count |",
        "|---|---|---|",
    ]
    rows.extend(
        f"| `{item['intended']!r}` | `{item['observed']!r}` | {item['count']} |"
        for item in result["top_confusions"]
    )
    rows.append("")
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
