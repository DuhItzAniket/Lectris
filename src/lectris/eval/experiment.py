"""A registered experiment, run from its configuration into a report (experiment protocol §7).

A configuration is JSON:

.. code-block:: json

    {"id": "LX-MAIN-001", "question": "Does the standard profile lower CER on dev?",
     "pairs": "data/manifests/pairs/hiertext_val_dev.json",
     "systems": [{"name": "B1", "profile": "standard", "policy": "parity"}],
     "resamples": 1000, "seed": 1337, "iou": 0.5}

``pairs`` names a manifest (relative to the configuration's folder), whose pages each give an
engine output file and a ground-truth file (``lectris.eval.truth``), relative to the manifest's
folder:

.. code-block:: json

    {"pages": [{"page": "a1b2c3", "engine": "../../engine/a1b2c3.json",
                "truth": "../../truth/a1b2c3.json"}]}

Each system is a profile and a policy: ``parity`` (LECTRIS v0.1's decisions) or ``none`` (no
guess accepted: the transforms only, baseline B0). Every page is read, cleaned by each system and
scored (``lectris.eval.scoring``). The report holds, for the uncorrected text and for each
system: CER (normalised and raw tracks), WER, the harm rate, edit counts by label, the precision
of edits and the share of pages made worse, with bootstrap intervals over pages; and each
system's paired CER difference from the uncorrected text. It holds aggregates only, never text
(ground rule 5).
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from lectris import __version__, io
from lectris.decide import PARITY, Policy, Threshold
from lectris.errors import FormatError
from lectris.eval import truth as truth_io
from lectris.eval.scoring import PageScore, score_page
from lectris.eval.stats import Interval, bootstrap, ratio
from lectris.io._common import decode
from lectris.io._json import array, load, number, obj, required, string
from lectris.pipeline import clean
from lectris.profiles import PROFILES

NONE: Final = Threshold(lambda _: 0.0, 1.0)
"""A policy that accepts no guess: every candidate's probability is 0, below the bar of 1."""

POLICIES: Final[dict[str, Policy]] = {"parity": PARITY, "none": NONE}
"""The policies a configuration can name."""


@dataclass(frozen=True, slots=True)
class System:
    """One system an experiment runs: a name, a profile and a policy."""

    name: str
    profile: str
    policy: str


@dataclass(frozen=True, slots=True)
class Config:
    """An experiment's configuration (see the module's documentation)."""

    id: str
    question: str
    pairs: Path
    systems: tuple[System, ...]
    resamples: int = 1000
    seed: int = 1337
    iou: float = 0.5


@dataclass(frozen=True, slots=True)
class Pair:
    """One page: its id, its engine output and its ground truth."""

    page: str
    engine: Path
    truth: Path


def load_config(path: Path) -> Config:
    """The configuration in the file at ``path``; ``FormatError`` names what is wrong."""
    data = obj(load(decode(path.read_bytes())), "")
    systems = tuple(
        _system(item, f"systems[{index}]")
        for index, item in array(required(data, "systems", ""), "systems")
    )
    if not systems:
        raise FormatError("systems: an experiment runs at least one system")
    names = [system.name for system in systems]
    if len(set(names)) != len(names):
        raise FormatError(f"systems: each system's name is given once, not {names}")
    return Config(
        id=string(required(data, "id", ""), "id"),
        question=string(data.get("question", ""), "question"),
        pairs=(path.parent / string(required(data, "pairs", ""), "pairs")),
        systems=systems,
        resamples=_integer(data, "resamples", 1000),
        seed=_integer(data, "seed", 1337),
        iou=number(data.get("iou", 0.5), "iou"),
    )


def load_pairs(path: Path) -> tuple[Pair, ...]:
    """The pages of the pairs manifest at ``path``."""
    data = obj(load(decode(path.read_bytes())), "")
    pairs = []
    for index, item in array(required(data, "pages", ""), "pages"):
        where = f"pages[{index}]"
        page = obj(item, where)
        pairs.append(
            Pair(
                string(required(page, "page", where), f"{where}.page"),
                path.parent / string(required(page, "engine", where), f"{where}.engine"),
                path.parent / string(required(page, "truth", where), f"{where}.truth"),
            )
        )
    return tuple(pairs)


def run(config: Config) -> dict[str, Any]:
    """Run ``config`` and return its report as a JSON-ready dictionary."""
    pairs = load_pairs(config.pairs)
    if not pairs:
        raise FormatError(f"{config.pairs}: the manifest has no pages")
    scores: dict[str, list[PageScore]] = {system.name: [] for system in config.systems}
    for pair in pairs:
        document = io.read(pair.engine)
        truth = truth_io.read(pair.truth)
        for system in config.systems:
            result = clean(document, profile=system.profile, policy=POLICIES[system.policy])
            scores[system.name].append(score_page(result, truth, iou_threshold=config.iou))
    first = scores[config.systems[0].name]
    report: dict[str, Any] = {
        "id": config.id,
        "question": config.question,
        "lectris_version": __version__,
        "pages": len(pairs),
        "manifest_sha256": hashlib.sha256(config.pairs.read_bytes()).hexdigest(),
        "resamples": config.resamples,
        "seed": config.seed,
        "iou": config.iou,
        "systems": [
            {"name": s.name, "profile": s.profile, "policy": s.policy} for s in config.systems
        ],
        "lines": {
            "ocr": sum(score.ocr_lines for score in first),
            "truth": sum(score.truth_lines for score in first),
            "matched": sum(score.matched_lines for score in first),
        },
        "uncorrected": _uncorrected(first, config),
        "results": {name: _summary(pages, config) for name, pages in scores.items()},
    }
    return report


def write(report: dict[str, Any], folder: Path) -> tuple[Path, Path]:
    """Write ``report`` as ``report.json`` and ``report.md`` in ``folder``; their paths."""
    folder.mkdir(parents=True, exist_ok=True)
    as_json = folder / "report.json"
    as_markdown = folder / "report.md"
    as_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    as_markdown.write_text(markdown(report), encoding="utf-8", newline="\n")
    return as_json, as_markdown


def markdown(report: dict[str, Any]) -> str:
    """The report as a Markdown page."""
    lines = [
        f"# {report['id']}",
        "",
        report["question"] or "(no question given)",
        "",
        f"- Pages: {report['pages']}; lines: {report['lines']['ocr']} OCR, "
        f"{report['lines']['truth']} ground truth, {report['lines']['matched']} matched "
        f"(IoU >= {report['iou']})",
        f"- LECTRIS {report['lectris_version']}; manifest sha256 `{report['manifest_sha256']}`",
        f"- Bootstrap: {report['resamples']} resamples over pages, seed {report['seed']}, 95%",
        "",
        "| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / "
        "neutral | Precision | Pages worse |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    base = report["uncorrected"]
    lines.append(
        f"| uncorrected | {_pct(base['cer'])} | {_pct(base['cer_raw'])} | {_pct(base['wer'])} "
        "| — | — | — | — | — |"
    )
    for name, result in report["results"].items():
        lines.append(
            f"| {name} | {_pct(result['cer'])} | {_pct(result['cer_raw'])} | "
            f"{_pct(result['wer'])} | {_points(result['cer_change'])} | "
            f"{_pct(result['harm_rate'], digits=3)} | "
            f"{result['fixes']} / {result['harms']} / {result['neutral']} | "
            f"{_pct(result['precision'])} | {_pct(result['pages_worse'])} |"
        )
    lines += [
        "",
        "Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the "
        "system's normalised CER minus the uncorrected text's, in points. The harm rate is the "
        "characters broken by harmful edits per reference character (ADR-0002).",
        "",
    ]
    return "\n".join(lines)


def _system(value: Any, path: str) -> System:
    data = obj(value, path)
    system = System(
        string(required(data, "name", path), f"{path}.name"),
        string(data.get("profile", "standard"), f"{path}.profile"),
        string(data.get("policy", "parity"), f"{path}.policy"),
    )
    if system.profile not in PROFILES:
        raise FormatError(f"{path}.profile: no profile called {system.profile!r}")
    if system.policy not in POLICIES:
        raise FormatError(f"{path}.policy: one of {', '.join(POLICIES)}, not {system.policy!r}")
    return system


def _integer(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if type(value) is not int or value < 0:
        raise FormatError(f"{key}: a whole number, not {value!r}")
    return value


def _interval(
    pages: Sequence[PageScore], statistic: Callable[[Sequence[PageScore]], float], config: Config
) -> dict[str, float]:
    found: Interval = bootstrap(pages, statistic, resamples=config.resamples, seed=config.seed)
    return {"estimate": found.estimate, "low": found.low, "high": found.high}


def _uncorrected(pages: Sequence[PageScore], config: Config) -> dict[str, Any]:
    return {
        "cer": _interval(
            pages,
            lambda s: ratio([p.chars.before for p in s], [p.chars.reference for p in s]),
            config,
        ),
        "cer_raw": _interval(
            pages,
            lambda s: ratio([p.raw_chars.before for p in s], [p.raw_chars.reference for p in s]),
            config,
        ),
        "wer": _interval(
            pages,
            lambda s: ratio([p.words.before for p in s], [p.words.reference for p in s]),
            config,
        ),
    }


def _summary(pages: Sequence[PageScore], config: Config) -> dict[str, Any]:
    fixes = sum(page.count("fix") for page in pages)
    harms = sum(page.count("harm") for page in pages)
    return {
        "cer": _interval(
            pages,
            lambda s: ratio([p.chars.after for p in s], [p.chars.reference for p in s]),
            config,
        ),
        "cer_raw": _interval(
            pages,
            lambda s: ratio([p.raw_chars.after for p in s], [p.raw_chars.reference for p in s]),
            config,
        ),
        "wer": _interval(
            pages,
            lambda s: ratio([p.words.after for p in s], [p.words.reference for p in s]),
            config,
        ),
        "cer_change": _interval(
            pages,
            lambda s: ratio(
                [p.chars.after - p.chars.before for p in s], [p.chars.reference for p in s]
            ),
            config,
        ),
        "harm_rate": _interval(pages, lambda s: sum(p.harm_rate for p in s) / len(s), config),
        "fixes": fixes,
        "harms": harms,
        "neutral": sum(page.count("neutral") for page in pages),
        "fixed_chars": sum(page.fixed_chars for page in pages),
        "harm_chars": sum(page.harm_chars for page in pages),
        "precision": fixes / (fixes + harms) if fixes + harms else None,
        "pages_worse": sum(1 for page in pages if page.chars.after > page.chars.before)
        / len(pages),
    }


def _pct(value: Any, *, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        return (
            f"{100 * value['estimate']:.{digits}f}% "
            f"[{100 * value['low']:.{digits}f}, {100 * value['high']:.{digits}f}]"
        )
    return f"{100 * value:.{digits}f}%"


def _points(value: dict[str, float]) -> str:
    return f"{100 * value['estimate']:+.2f} [{100 * value['low']:+.2f}, {100 * value['high']:+.2f}]"
