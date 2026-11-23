"""B3, step 2: fine-tune ByT5-small for line-level post-OCR correction (protocol §6).

Starts from ``google/byt5-small`` (Xue et al., 2022), trains on the fit split's line pairs
(``prepare.py``) to map an OCR line to its ground truth, and keeps the checkpoint with the lowest
character error rate on a fixed sample of the cal split's pairs, checked after every epoch.
Bytes beyond ``--max-bytes`` are cut. Seeded; bf16 on a CUDA GPU when there is one.

    uv run python train.py --data ../../../data/baselines/byt5 \
        --out ../../../data/baselines/byt5/model
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from transformers import Adafactor, AutoModelForSeq2SeqLM, AutoTokenizer

from lectris.metrics import char_errors

MODEL = "google/byt5-small"


def read(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return [(r["source"], r["target"]) for r in map(json.loads, handle)]


def batches(
    pairs: list[tuple[str, str]], size: int, generator: random.Random
) -> list[list[tuple[str, str]]]:
    order = pairs[:]
    generator.shuffle(order)
    return [order[i : i + size] for i in range(0, len(order), size)]


@torch.no_grad()
def cer(
    model: torch.nn.Module,
    tokenizer: object,
    pairs: list[tuple[str, str]],
    device: str,
    max_bytes: int,
) -> float:
    model.eval()
    errors = chars = 0
    for i in range(0, len(pairs), 64):
        chunk = pairs[i : i + 64]
        encoded = tokenizer(  # type: ignore[operator]
            [s for s, _ in chunk],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_bytes,
        ).to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            output = model.generate(
                **encoded, max_new_tokens=max_bytes, num_beams=1, do_sample=False
            )
        texts = tokenizer.batch_decode(output, skip_special_tokens=True)  # type: ignore[attr-defined]
        for (_, target), text in zip(chunk, texts, strict=True):
            counts = char_errors(target, text)
            errors += counts.errors
            chars += counts.reference_length
    model.train()
    return errors / max(1, chars)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--accumulate", type=int, default=2)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-bytes", type=int, default=160)
    parser.add_argument("--validation-sample", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1337)
    arguments = parser.parse_args()

    random.seed(arguments.seed)
    torch.manual_seed(arguments.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL).to(device)
    train = read(arguments.data / "train.jsonl")
    validation = read(arguments.data / "validation.jsonl")
    sample = random.Random(arguments.seed).sample(
        validation, min(arguments.validation_sample, len(validation))
    )
    model.gradient_checkpointing_enable()  # the 6 GB laptop GPU: recompute activations
    model.config.use_cache = False
    optimizer = Adafactor(
        model.parameters(),
        lr=arguments.lr,
        scale_parameter=False,
        relative_step=False,
        warmup_init=False,
    )  # T5's optimizer: factored second moments, no first moment, small state
    steps = arguments.epochs * math.ceil(len(train) / (arguments.batch * arguments.accumulate))
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda s: min(1.0, (s + 1) / 200) * max(0.0, 1 - s / steps)
    )
    log: list[dict[str, float]] = []
    best = cer(model, tokenizer, sample, device, arguments.max_bytes)
    identity = sum(char_errors(t, s).errors for s, t in sample) / max(
        1, sum(len(t) for _, t in sample)
    )
    print(f"before training: validation CER {best:.4f} (copying the input: {identity:.4f})")
    log.append({"epoch": 0, "validation_cer": best, "copy_cer": identity})
    arguments.out.mkdir(parents=True, exist_ok=True)
    generator = random.Random(arguments.seed)
    started = time.time()
    model.train()
    for epoch in range(1, arguments.epochs + 1):
        total = 0.0
        for step, batch in enumerate(batches(train, arguments.batch, generator), 1):
            inputs = tokenizer(
                [s for s, _ in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=arguments.max_bytes,
            ).to(device)
            labels = tokenizer(
                [t for _, t in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=arguments.max_bytes,
            ).input_ids.to(device)
            labels[labels == tokenizer.pad_token_id] = -100
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                loss = model(**inputs, labels=labels).loss
            (loss / arguments.accumulate).backward()
            if step % arguments.accumulate == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
            total += float(loss)
            if step % 200 == 0:
                print(
                    f"epoch {epoch} step {step}: loss {total / step:.4f}, "
                    f"{time.time() - started:.0f} s"
                )
        score = cer(model, tokenizer, sample, device, arguments.max_bytes)
        print(f"epoch {epoch}: validation CER {score:.4f}")
        log.append({"epoch": epoch, "validation_cer": score, "train_loss": total / max(1, step)})
        if score < best:
            best = score
            model.save_pretrained(arguments.out)
            tokenizer.save_pretrained(arguments.out)
    if not (arguments.out / "config.json").exists():  # no epoch beat the start: keep the base model
        model.save_pretrained(arguments.out)
        tokenizer.save_pretrained(arguments.out)
    record = {
        "model": MODEL,
        "train_pairs": len(train),
        "validation_sample": len(sample),
        "epochs": arguments.epochs,
        "batch": arguments.batch,
        "accumulate": arguments.accumulate,
        "optimizer": "Adafactor",
        "lr": arguments.lr,
        "max_bytes": arguments.max_bytes,
        "seed": arguments.seed,
        "device": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
        "seconds": time.time() - started,
        "best_validation_cer": best,
        "log": log,
    }
    (arguments.out / "training.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in record.items() if k != "log"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
