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

Each system is a profile and a policy: ``parity`` (LECTRIS v0.1's decisions), ``none`` (no
guess accepted: the transforms only, baseline B0), ``lexicon`` (baseline B2, a lexicon
corrector, ``LEXICON``) or ``risk`` (the pack's acceptance model and
the profile's risk-controlled threshold, ``lectris.eval.calibrate.risk_policy``). A system can
name a model ``pack`` (relative to the configuration's folder): it adds evidence and the lexicon
proposers, and ``risk`` needs one. Every page is read, its OCR lines on
don't-care ground truth are dropped (``scoring.drop_dont_care``), and it is cleaned by each
system and scored (``lectris.eval.scoring``). The report holds, for the uncorrected text and
for each system: CER (normalised and raw tracks), WER, the harm rate, edit counts by label, the
precision of edits and the share of pages made worse, with bootstrap intervals over pages; and
each system's paired CER difference from the uncorrected text. It holds aggregates only, never
text (ground rule 5).
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
from lectris.eval.scoring import PageScore, drop_dont_care, score_page
from lectris.eval.stats import Interval, bootstrap, ratio
from lectris.io._common import decode
from lectris.io._json import array, load, number, obj, required, string
from lectris.models import pack as pack_io
from lectris.pipeline import clean
from lectris.profiles import PROFILES

NONE: Final = Threshold(lambda _: 0.0, 1.0)
"""A policy that accepts no guess: every candidate's probability is 0, below the bar of 1."""

LEXICON: Final = Threshold(
    lambda c: 1.0 if c.rule == "lexical.word" and c.feature("lexical_rank", 9.0) == 0 else 0.0, 1.0
)
"""Baseline B2, a lexicon corrector: every token not in the lexicon becomes the lexicon's most
frequent word one edit away (``lexical.word``'s first candidate); no other guess is accepted.
It needs a pack, for the word list."""

POLICIES: Final[dict[str, Policy]] = {"parity": PARITY, "none": NONE, "lexicon": LEXICON}
"""The policies a configuration can name, besides ``risk`` (which needs a pack)."""

_POLICY_NAMES: Final = (*POLICIES, "risk")


@dataclass(frozen=True, slots=True)
class System:
    """One system an experiment runs: a name, a profile and a policy."""

    name: str
    profile: str
    policy: str
    pack: Path | None = None


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
    compare: tuple[tuple[str, str], ...] = ()


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
        _system(item, f"systems[{index}]", path.parent)
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
        compare=_comparisons(data.get("compare", []), names),
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
    from lectris.eval.calibrate import risk_policy  # noqa: PLC0415 - calibrate imports this module

    packs = {s.pack: pack_io.load(s.pack) for s in config.systems if s.pack is not None}
    policies: dict[str, Policy] = {}
    for system in config.systems:
        if system.policy == "risk":
            if system.pack is None:
                raise FormatError(f"{system.name}: the risk policy needs a pack")
            policies[system.name] = risk_policy(packs[system.pack], system.profile)
        else:
            policies[system.name] = POLICIES[system.policy]
    for pair in pairs:
        truth = truth_io.read(pair.truth)
        document = drop_dont_care(io.read(pair.engine), truth, iou_threshold=config.iou)
        for system in config.systems:
            result = clean(
                document,
                profile=system.profile,
                policy=policies[system.name],
                pack=None if system.pack is None else packs[system.pack],
            )
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
            {"name": s.name, "profile": s.profile, "policy": s.policy}
            | ({} if s.pack is None else {"pack_sha256": _sha256(s.pack)})
            for s in config.systems
        ],
        "lines": {
            "ocr": sum(score.ocr_lines for score in first),
            "truth": sum(score.truth_lines for score in first),
            "matched": sum(score.matched_lines for score in first),
        },
        "uncorrected": _uncorrected(first, config),
        "results": {name: _summary(pages, config) for name, pages in scores.items()},
        "comparisons": {
            f"{a} vs {b}": _comparison(scores[a], scores[b], config) for a, b in config.compare
        },
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
        "neutral / layout | Precision | Pages worse |",
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
            f"{result['fixes']} / {result['harms']} / {result['neutral']} / "
            f"{result['layout']} | "
            f"{_pct(result['precision'])} | {_pct(result['pages_worse'])} |"
        )
    lines += [
        "",
        "Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the "
        "system's normalised CER minus the uncorrected text's, in points. The harm rate is the "
        "characters broken by harmful edits per reference character (ADR-0002). Layout edits "
        "(de-hyphenation, unwrapping) are counted apart: the reference is laid out the same way "
        "(lectris.eval.scoring, R-15).",
        "",
    ]
    if report.get("comparisons"):
        lines += [
            "## Paired comparisons",
            "",
            "| A vs B | CER difference (points) | Repaired, per reference character | Broken |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| {name} | {_points(c['cer'])} | {_points(c['fixed'])} | {_points(c['harmed'])} |"
            for name, c in report["comparisons"].items()
        )
        lines += [
            "",
            "Each is A minus B, paired over pages, with its 95% bootstrap interval, in points of "
            "the reference's characters.",
            "",
        ]
    lines += [
        "## Edits by rule",
        "",
        "| System | Rule | Fix | Harm | Neutral | Layout | Net effect (characters) |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, result in report["results"].items():
        for rule, counts in result["by_rule"].items():
            lines.append(
                f"| {name} | `{rule}` | {counts['fix']} | {counts['harm']} | "
                f"{counts['neutral']} | {counts['layout']} | {counts['effect']:+d} |"
            )
    lines += [
        "",
        "The net effect is the sum of the edits' effects on the distance to the reference: "
        "below zero the rule repaired more than it broke. For a layout rule it is measured against "
        "a reference laid out by the same rule, so it shows agreement, not accuracy.",
        "",
    ]
    return "\n".join(lines)


def _comparisons(value: Any, names: Sequence[str]) -> tuple[tuple[str, str], ...]:
    found = []
    for index, item in array(value, "compare"):
        pair = array(item, f"compare[{index}]")
        if len(pair) != 2:  # noqa: PLR2004 - a pair
            raise FormatError(f"compare[{index}]: a comparison names two systems")
        a, b = (string(name, f"compare[{index}][{i}]") for i, name in pair)
        for name in (a, b):
            if name not in names:
                raise FormatError(f"compare[{index}]: no system called {name!r}")
        found.append((a, b))
    return tuple(found)


def _comparison(
    first: Sequence[PageScore], second: Sequence[PageScore], config: Config
) -> dict[str, Any]:
    """Paired differences between two systems on the same pages: CER (normalised, points of
    the reference), characters repaired and characters broken, per reference character."""
    pairs = list(zip(first, second, strict=True))

    def difference(key: Callable[[PageScore], int]) -> Callable[[Sequence[Any]], float]:
        return lambda s: ratio([key(a) - key(b) for a, b in s], [a.chars.reference for a, _ in s])

    def interval(statistic: Callable[[Sequence[Any]], float]) -> dict[str, float]:
        found = bootstrap(pairs, statistic, resamples=config.resamples, seed=config.seed)
        return {"estimate": found.estimate, "low": found.low, "high": found.high}

    return {
        "cer": interval(difference(lambda p: p.chars.after)),
        "fixed": interval(difference(lambda p: p.fixed_chars)),
        "harmed": interval(difference(lambda p: p.harm_chars)),
    }


def _system(value: Any, path: str, folder: Path) -> System:
    data = obj(value, path)
    pack = data.get("pack")
    system = System(
        string(required(data, "name", path), f"{path}.name"),
        string(data.get("profile", "standard"), f"{path}.profile"),
        string(data.get("policy", "parity"), f"{path}.policy"),
        None if pack is None else folder / string(pack, f"{path}.pack"),
    )
    if system.profile not in PROFILES:
        raise FormatError(f"{path}.profile: no profile called {system.profile!r}")
    if system.policy not in _POLICY_NAMES:
        raise FormatError(
            f"{path}.policy: one of {', '.join(_POLICY_NAMES)}, not {system.policy!r}"
        )
    if system.policy == "risk" and system.pack is None:
        raise FormatError(f"{path}: the risk policy needs a pack")
    return system


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        "layout": sum(page.count("layout") for page in pages),
        "fixed_chars": sum(page.fixed_chars for page in pages),
        "harm_chars": sum(page.harm_chars for page in pages),
        "precision": fixes / (fixes + harms) if fixes + harms else None,
        "pages_worse": sum(1 for page in pages if page.chars.after > page.chars.before)
        / len(pages),
        "by_rule": _by_rule(pages),
    }


def _by_rule(pages: Sequence[PageScore]) -> dict[str, dict[str, int]]:
    """Each rule's edits by label, and the sum of their effects, rules in name order."""
    found: dict[str, dict[str, int]] = {}
    for page in pages:
        for item in page.labels:
            counts = found.setdefault(
                item.edit.rule, {"fix": 0, "harm": 0, "neutral": 0, "layout": 0, "effect": 0}
            )
            counts[item.label] += 1
            counts["effect"] += item.effect
    return dict(sorted(found.items()))


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
