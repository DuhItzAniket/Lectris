"""Build LECTRIS's test pairs from GDC (GLYPHARIS Document Challenge) and an engine's output.

Phase 13 (docs/IMPLEMENTATION_PLAN.md; ADR-0005: GDC is the test set, read once). GDC's pages
come from GLYPHARIS's frozen page file (``pages_test.jsonl.gz``, checked against the SHA-256
its manifest records). For every page it writes LECTRIS's ground truth, mirroring GLYPHARIS's
own page metrics (``glypharis.eval.page_metrics``):

- a line **counts** when it is legible, printed, horizontal and not empty **and** its box is
  trusted (no alignment score, or one of at least 0.3, ``MIN_ALIGN_SCORE``): LECTRIS matches lines
  by their boxes, so a line whose box the alignment does not support cannot be matched;
- every other line is **don't care**, and so is each of the page's ignore regions (the sheet's
  markers and printed label, GDC 1.1): an OCR line on one is left out of the scoring;
- a box is the box around the line's (or region's) polygon.

The page's id is GDC's ``doc_id``; the engine's output for it is ``--engine-dir/<image>.json``,
``<image>`` the capture's file name without its suffix. One manifest, split ``test``, lists the
pages with the SHA-256 of each file. Aggregates and ids only; GDC's data stays outside the
repository.

    uv run python scripts/build_gdc_pairs.py --pages <GDC>/pages_test.jsonl.gz \\
        --manifest-of-record <GDC manifest> --engine-dir data/engine/gdc_v1_1/glypharis_v1 \\
        --truth-dir data/truth/gdc_v1_1 --out data/manifests/pairs/gdc_v1_1_glypharis_v1_test.json
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

MIN_ALIGN_SCORE = 0.3


def box_of(polygon: Sequence[Sequence[float]]) -> Box | None:
    if not polygon:
        return None
    xs = [float(x) for x, _ in polygon]
    ys = [float(y) for _, y in polygon]
    return Box(min(xs), min(ys), max(xs), max(ys))


def counts(line: dict[str, Any]) -> bool:
    """GLYPHARIS's box lines: a text line with a trusted box."""
    score = line.get("align_score")
    return (
        bool(line.get("legible", True))
        and not bool(line.get("handwritten", False))
        and not bool(line.get("vertical", False))
        and bool(str(line.get("text", "")).strip())
        and (score is None or float(score) >= MIN_ALIGN_SCORE)
    )


def page_of(record: dict[str, Any]) -> TruthPage:
    lines = [
        TruthLine(str(line.get("text", "")), box_of(line.get("polygon", [])), counts(line))
        for line in record.get("lines", [])
    ]
    lines += [TruthLine("", box_of(region), care=False) for region in record.get("ignore", [])]
    return TruthPage(
        str(record["doc_id"]), tuple(lines), float(record["width"]), float(record["height"])
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--manifest-of-record", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--truth-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--engine", default="glypharis")
    parser.add_argument("--model", default="glypharis_v1")
    parser.add_argument("--suffix", default=".json")
    arguments = parser.parse_args(argv)

    data = arguments.pages.read_bytes()
    record = json.loads(arguments.manifest_of_record.read_text(encoding="utf-8"))
    digest = hashlib.sha256(data).hexdigest()
    if digest != record["pages_sha256"] or not record.get("frozen"):
        sys.stderr.write("the pages file is not the frozen GDC the manifest records\n")
        return 1
    rows = [json.loads(line) for line in gzip.decompress(data).decode("utf-8").splitlines()]
    arguments.truth_dir.mkdir(parents=True, exist_ok=True)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for row in rows:
        page = page_of(row)
        engine_file = arguments.engine_dir / f"{Path(row['image']).stem}{arguments.suffix}"
        if not engine_file.is_file():
            sys.stderr.write(f"no engine output for {page.page}: {engine_file.name}\n")
            return 1
        truth_file = arguments.truth_dir / f"{page.page}.json"
        truth_file.write_text(truth.dumps(page) + "\n", encoding="utf-8", newline="\n")
        entries.append(
            {
                "page": page.page,
                "engine": Path(os.path.relpath(engine_file, arguments.out.parent)).as_posix(),
                "truth": Path(os.path.relpath(truth_file, arguments.out.parent)).as_posix(),
                "engine_sha256": hashlib.sha256(engine_file.read_bytes()).hexdigest(),
                "truth_sha256": hashlib.sha256(truth_file.read_bytes()).hexdigest(),
            }
        )
    summary = {
        "name": arguments.out.stem,
        "source": {
            "dataset": "GDC",
            "version": record["gdc_version"],
            "frozen_utc": record["frozen_utc"],
            "pages_sha256": digest,
        },
        "engine": {"name": arguments.engine, "model": arguments.model},
        "rule": "a line counts when legible, printed, horizontal, not empty and its alignment "
        f"score is absent or >= {MIN_ALIGN_SCORE}; other lines and ignore regions are don't care",
        "split": "test",
        "lines_that_count": sum(1 for r in rows for line in r["lines"] if counts(line)),
        "dont_care_lines": sum(1 for r in rows for line in r["lines"] if not counts(line)),
        "ignore_regions": sum(len(r.get("ignore", [])) for r in rows),
        "pages": entries,
    }
    arguments.out.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    sys.stdout.write(
        f"{len(entries)} pages; {summary['lines_that_count']} lines count, "
        f"{summary['dont_care_lines']} don't care, {summary['ignore_regions']} ignore regions\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
