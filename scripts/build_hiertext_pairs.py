"""Build LECTRIS's paired data from HierText validation and an engine's output on its pages.

Phase 5 (docs/IMPLEMENTATION_PLAN.md; ADR-0005; experiment protocol §1). For every page of the
HierText validation ground truth it

1. writes the page's ground truth in LECTRIS's form (``lectris.eval.truth``) to
   ``--truth-dir/<image_id>.json``. A line counts (``care``) when it is legible, not handwritten,
   not vertical and not empty, as GLYPHARIS's page metrics define it; every other line is don't
   care. A line's box is the box around its quadrilateral;
2. checks that the engine's output for the page, ``--engine-dir/<image_id>.json``, exists;
3. assigns the page to a split, **fit** 50%, **cal** 25%, **dev** 25%, by page, stratified by
   the document slice (pages with at least 100 lines that count, GLYPHARIS Phase 12's proxy for
   document pages): within each stratum, pages are ordered by SHA-256 of ``salt + image_id`` and
   the first half is fit, the next quarter cal, the rest dev;
4. writes one manifest per split to ``--manifests/<name>_<split>.json``, listing each page's id,
   its engine and truth files (relative to the manifest) and their SHA-256, and a summary with
   the counts to ``--manifests/<name>.json``.

The ground truth and the engine's output are third-party data and stay out of the repository
(ground rule 5): ``data/`` is git-ignored except ``data/manifests/``, which holds ids, counts and
hashes only.

    uv run python scripts/build_hiertext_pairs.py \\
        --gt <HierText>/gt/validation.jsonl.gz \\
        --engine-dir data/engine/hiertext_val/glypharis_v1 \\
        --truth-dir data/truth/hiertext_val \\
        --manifests data/manifests/pairs --name hiertext_val_glypharis_v1 \\
        --engine glypharis --model glypharis_v1
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lectris.eval import truth
from lectris.eval.truth import TruthLine, TruthPage
from lectris.model import Box

SPLITS = (("fit", 0.5), ("cal", 0.25), ("dev", 0.25))
DOCUMENT_LINES = 100
SALT = "lectris-v1"


def counts(line: dict[str, Any]) -> bool:
    """Whether a HierText line counts: legible, printed, horizontal and with text."""
    return (
        bool(line.get("legible", True))
        and not bool(line.get("handwritten", False))
        and not bool(line.get("vertical", False))
        and bool(str(line.get("text", "")).strip())
    )


def page_of(record: dict[str, Any]) -> TruthPage:
    """A HierText annotation as a LECTRIS ground-truth page, lines in annotation order."""
    lines = []
    for paragraph in record.get("paragraphs", []):
        for line in paragraph.get("lines", []):
            xs = [float(x) for x, _ in line.get("vertices", [])]
            ys = [float(y) for _, y in line.get("vertices", [])]
            bounds = Box(min(xs), min(ys), max(xs), max(ys)) if xs else None
            lines.append(TruthLine(str(line.get("text", "")), bounds, counts(line)))
    return TruthPage(
        str(record["image_id"]),
        tuple(lines),
        float(record["image_width"]),
        float(record["image_height"]),
    )


def assign(pages: Sequence[TruthPage], salt: str) -> dict[str, str]:
    """Each page's split: stratified by the document slice, ordered by the salted hash."""
    split: dict[str, str] = {}
    for in_slice in (True, False):
        stratum = sorted(
            (page.page for page in pages if is_document(page) == in_slice),
            key=lambda page: hashlib.sha256((salt + page).encode()).hexdigest(),
        )
        start = 0
        for index, (name, share) in enumerate(SPLITS):
            end = len(stratum) if index == len(SPLITS) - 1 else start + int(share * len(stratum))
            for page in stratum[start:end]:
                split[page] = name
            start = end
    return split


def is_document(page: TruthPage) -> bool:
    return sum(1 for line in page.lines if line.care) >= DOCUMENT_LINES


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gt", type=Path, required=True, help="HierText validation.jsonl.gz")
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--truth-dir", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--name", required=True, help="the manifests' name")
    parser.add_argument("--engine", required=True, help="the engine's name")
    parser.add_argument("--model", required=True, help="the engine's model version")
    parser.add_argument("--salt", default=SALT)
    arguments = parser.parse_args(argv)

    with gzip.open(arguments.gt, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    pages = [page_of(record) for record in data["annotations"]]
    missing = [p.page for p in pages if not (arguments.engine_dir / f"{p.page}.json").is_file()]
    if missing:
        sys.stderr.write(f"{len(missing)} pages have no engine output, e.g. {missing[:3]}\n")
        return 1
    arguments.truth_dir.mkdir(parents=True, exist_ok=True)
    arguments.manifests.mkdir(parents=True, exist_ok=True)
    for page in pages:
        (arguments.truth_dir / f"{page.page}.json").write_text(
            truth.dumps(page) + "\n", encoding="utf-8", newline="\n"
        )
    split = assign(pages, arguments.salt)
    summary: dict[str, Any] = {
        "name": arguments.name,
        "source": {"dataset": "HierText", "split": "validation", "info": data.get("info", {})},
        "engine": {"name": arguments.engine, "model": arguments.model},
        "salt": arguments.salt,
        "rule": "fit 50%, cal 25%, dev 25%, by page, stratified by the document slice "
        f"(>= {DOCUMENT_LINES} lines that count), ordered by sha256(salt + image_id)",
        "splits": {},
    }
    for name, _ in SPLITS:
        chosen = sorted((p for p in pages if split[p.page] == name), key=lambda p: p.page)
        entries = []
        for page in chosen:
            engine_file = arguments.engine_dir / f"{page.page}.json"
            truth_file = arguments.truth_dir / f"{page.page}.json"
            entries.append(
                {
                    "page": page.page,
                    "engine": _relative(engine_file, arguments.manifests),
                    "truth": _relative(truth_file, arguments.manifests),
                    "engine_sha256": sha256(engine_file),
                    "truth_sha256": sha256(truth_file),
                    "document_slice": is_document(page),
                }
            )
        manifest = {key: summary[key] for key in ("name", "source", "engine", "salt", "rule")}
        manifest |= {"split": name, "pages": entries}
        (arguments.manifests / f"{arguments.name}_{name}.json").write_text(
            json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        summary["splits"][name] = {
            "pages": len(chosen),
            "document_slice_pages": sum(1 for p in chosen if is_document(p)),
            "lines_that_count": sum(1 for p in chosen for line in p.lines if line.care),
            "dont_care_lines": sum(1 for p in chosen for line in p.lines if not line.care),
        }
    (arguments.manifests / f"{arguments.name}.json").write_text(
        json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    sys.stdout.write(json.dumps(summary["splits"], indent=1) + "\n")
    return 0


def _relative(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path, start)).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
