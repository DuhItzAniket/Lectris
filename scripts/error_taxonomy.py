"""What an engine's errors are made of, on a split of paired data (Phase 5 audit).

For every page of a pairs manifest: OCR lines on don't-care ground truth are dropped
(``lectris.eval.scoring.drop_dont_care``), OCR lines are matched with the ground-truth lines that
count, and each matched pair is aligned character by character in the normalised track. Each
character error is then one of:

- **in a token**: a substitution, insertion or deletion of a character that is not a space. Such
  an error lies inside one word of the OCR line and is the kind a local correction can fix: the
  share of these bounds what LECTRIS can repair;
- **spacing**: an inserted or deleted space, or a space substituted for a character or the
  reverse, which splits or merges words (segmentation);
- **missed line**: the characters of a ground-truth line no OCR line was matched with;
- **extra line**: the characters of an OCR line matched with no ground-truth line.

The output is aggregates only (ground rule 5): counts, shares, and the same for the document
slice.

    uv run python scripts/error_taxonomy.py MANIFEST --out reports/LX-DATA-001

where MANIFEST is, for example, ``data/manifests/pairs/hiertext_val_glypharis_v1_fit.json``.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lectris import io
from lectris.align import align_chars
from lectris.eval import truth as truth_io
from lectris.eval.experiment import load_pairs
from lectris.eval.matching import match_lines
from lectris.eval.scoring import drop_dont_care, normalised

KINDS = ("in_token", "spacing", "missed_line", "extra_line")
DOCUMENT_LINES = 100  # the document slice, as scripts/build_hiertext_pairs.py defines it


def classify(reference: str, hypothesis: str) -> Counter[str]:
    """The character errors of one matched line pair, by kind."""
    found: Counter[str] = Counter()
    for op in align_chars(reference, hypothesis):
        if op.kind == "equal":
            continue
        if op.reference == " " or op.hypothesis == " ":
            found["spacing"] += 1
        else:
            found["in_token"] += 1
    return found


def page_counts(engine: Path, truth_path: Path) -> tuple[Counter[str], int, bool]:
    """A page's errors by kind, its reference length, and whether it is in the document slice."""
    page = truth_io.read(truth_path)
    document = drop_dont_care(io.read(engine), page)
    counted = page.counted
    lines = [line for p in document.pages for line in p.lines]
    matching = match_lines([line.box for line in lines], [line.box for line in counted.lines])
    found: Counter[str] = Counter()
    for i, j in matching.pairs:
        found += classify(normalised(counted.lines[j].text), normalised(lines[i].text))
    for j in matching.truth_unmatched:
        found["missed_line"] += len(normalised(counted.lines[j].text))
    for i in matching.ocr_unmatched:
        found["extra_line"] += len(normalised(lines[i].text))
    reference = sum(len(normalised(line.text)) for line in counted.lines)
    return found, reference, len(counted.lines) >= DOCUMENT_LINES


def summary(counts: Counter[str], reference: int, pages: int) -> dict[str, Any]:
    errors = sum(counts[kind] for kind in KINDS)
    return {
        "pages": pages,
        "reference_chars": reference,
        "errors": errors,
        "cer": errors / reference if reference else None,
        "counts": {kind: counts[kind] for kind in KINDS},
        "shares": {kind: counts[kind] / errors if errors else None for kind in KINDS},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    total: Counter[str] = Counter()
    document: Counter[str] = Counter()
    reference = document_reference = pages = document_pages = 0
    for pair in load_pairs(arguments.manifest):
        found, chars, in_slice = page_counts(pair.engine, pair.truth)
        total += found
        reference += chars
        pages += 1
        if in_slice:
            document += found
            document_reference += chars
            document_pages += 1
    result = {
        "manifest": arguments.manifest.as_posix(),
        "track": "normalised",
        "all": summary(total, reference, pages),
        "document_slice": summary(document, document_reference, document_pages),
    }
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "taxonomy.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (arguments.out / "taxonomy.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


def markdown(result: dict[str, Any]) -> str:
    rows = [
        "# Error taxonomy",
        "",
        f"Manifest `{result['manifest']}`, {result['track']} track. Generated by "
        "`scripts/error_taxonomy.py`; aggregates only.",
        "",
        "| Slice | Pages | Reference chars | CER | In a token | Spacing | Missed lines | "
        "Extra lines |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in ("all", "document_slice"):
        part = result[name]
        cer = "—" if part["cer"] is None else f"{100 * part['cer']:.2f}%"
        shares = [
            "—" if part["shares"][k] is None else f"{100 * part['shares'][k]:.1f}%" for k in KINDS
        ]
        rows.append(
            f"| {name.replace('_', ' ')} | {part['pages']} | {part['reference_chars']} | {cer} | "
            + " | ".join(shares)
            + " |"
        )
    rows += [
        "",
        "Shares are of all character errors. *In a token* errors are the ones a local "
        "correction can reach: an upper bound for what LECTRIS can repair.",
        "",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
