"""B3, step 1: line pairs for ByT5 from LECTRIS's paired data (protocol §6).

For the fit split (training) and the cal split (choosing the checkpoint), every OCR line matched
with a ground-truth line that counts becomes a pair ``{"source": OCR line, "target": ground
truth}``, both in LECTRIS's normalised track (``lectris.eval.lines.matched_lines``). The dev split
is not read here: it is only corrected, by ``correct.py``. Output: JSON lines, git-ignored.

    uv run python prepare.py --fit FIT --cal CAL --out ../../../data/baselines/byt5
"""

import argparse
import json
from pathlib import Path

from lectris.eval.experiment import load_pairs
from lectris.eval.lines import matched_lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--cal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)
    for name, manifest in (("train", arguments.fit), ("validation", arguments.cal)):
        count = 0
        with (arguments.out / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as out:
            for page in matched_lines(load_pairs(manifest)):
                for target, source in page.pairs:
                    if source and target:
                        out.write(json.dumps({"source": source, "target": target}) + "\n")
                        count += 1
        print(f"{name}: {count} line pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
