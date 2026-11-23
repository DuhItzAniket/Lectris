"""B3, step 3: correct every dev line with the fine-tuned ByT5 (protocol §6).

For each page of a pairs manifest (dev), reads the engine's GLYPHARIS JSON, corrects each line's
text (in LECTRIS's normalised track, the form ByT5 was trained on) by greedy decoding, and
writes the same JSON with the corrected text, plus ``b3_logprob`` (the mean log probability of the
output's bytes) and ``b3_source`` (the line as the engine read it). An empty output keeps the
engine's line. A manifest of the corrected pages, pointing at the same ground truth, is written
next to them.

    uv run python correct.py --model M --pairs DEV --out ../../../data/engine/hiertext_val/byt5 \\
        --manifest ../../../data/manifests/pairs/hiertext_val_byt5_dev.json
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from lectris.eval.experiment import load_pairs
from lectris.eval.scoring import normalised


@torch.no_grad()
def correct(
    model: torch.nn.Module, tokenizer: object, lines: list[str], device: str, max_bytes: int
) -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    for i in range(0, len(lines), 64):
        chunk = lines[i : i + 64]
        encoded = tokenizer(
            chunk, return_tensors="pt", padding=True, truncation=True, max_length=max_bytes
        ).to(device)  # type: ignore[operator]
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            output = model.generate(  # type: ignore[attr-defined]
                **encoded, max_new_tokens=max_bytes, num_beams=1, do_sample=False,
                output_scores=True, return_dict_in_generate=True,
            )  # fmt: skip
        scores = model.compute_transition_scores(
            output.sequences, output.scores, normalize_logits=True
        )  # type: ignore[attr-defined]
        texts = tokenizer.batch_decode(output.sequences, skip_special_tokens=True)  # type: ignore[attr-defined]
        for row, text in enumerate(texts):
            kept = scores[row][output.sequences[row][1:] != tokenizer.pad_token_id]  # type: ignore[attr-defined]
            found.append((text, float(kept.float().mean()) if len(kept) else 0.0))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=160)
    arguments = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(arguments.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(arguments.model).to(device).eval()
    arguments.out.mkdir(parents=True, exist_ok=True)
    arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for pair in load_pairs(arguments.pairs):
        data = json.loads(pair.engine.read_text(encoding="utf-8"))
        sources = [normalised(line["text"]) for line in data["lines"]]
        outputs = correct(
            model, tokenizer, [s or " " for s in sources], device, arguments.max_bytes
        )
        for line, source, (text, logprob) in zip(data["lines"], sources, outputs, strict=True):
            line["b3_source"] = line["text"]
            line["b3_logprob"] = logprob
            line["text"] = text if text.strip() and source else line["text"]
        target = arguments.out / f"{pair.page}.json"
        target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
        entries.append(
            {
                "page": pair.page,
                "engine": Path(os.path.relpath(target, arguments.manifest.parent)).as_posix(),
                "truth": Path(os.path.relpath(pair.truth, arguments.manifest.parent)).as_posix(),
                "engine_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    arguments.manifest.write_text(
        json.dumps(
            {
                "name": "hiertext_val_byt5_dev",
                "source": str(arguments.pairs.name),
                "pages": entries,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(entries)} pages corrected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
