# LECTRIS

**OCR output, read back into clean, ordered text: every change it makes is recorded and explained.**

[![CI](https://github.com/DuhItzAniket/Lectris/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DuhItzAniket/Lectris/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Checked by Repro](https://img.shields.io/badge/pull%20requests-checked%20by%20Repro-informational)](https://github.com/DuhItzAniket/Repro)

OCR engines return words, lines and boxes, and the text they recover still needs work: columns
read in the wrong order, words split across lines, `ﬁ` ligatures, `O` read for `0`, spaces in the
middle of numbers, specks read as lines of punctuation. LECTRIS reads the engine's output
(hOCR, ALTO, Tesseract TSV, JSON or plain text), puts the lines in reading order, groups them into
paragraphs, and repairs the text with small, conservative rules. Each rule records each edit it
makes, so you can audit a result, count what changed, or switch a rule off.

It does not run OCR, process images or use language models, and it has no dependencies outside
the standard library.

## Example

```python
from lectris import clean

ocr = (
    "The ﬁrst survey of the river  recorded 1O5 species , most of them\n"
    "in the upper reaches. Later surveys con-\n"
    "firmed the count.\n"
    "~~~ ,,, ' ' |||\n"
    "Water quality fell by 3 .5 percent in ten years."
)
result = clean(ocr)
print(result.text)
```

```text
The first survey of the river recorded 105 species, most of them in the upper reaches. Later surveys confirmed the count. Water quality fell by 3.5 percent in ten years.
```

Every change is in the result: ten edits here, each with its rule, its place and what it replaced.

```python
for change in result.changes():
    print(change.edit.rule, repr(change.edit.before), "->", repr(change.edit.after))
```

```text
unicode.ligatures 'ﬁ' -> 'fi'
whitespace.collapse '  ' -> ' '
noise.drop_lines "~~~ ,,, ' ' |||\n" -> ''
hyphenation.join '-\nfirmed ' -> 'firmed\n'
unwrap.join_lines '\n' -> ' '
unwrap.join_lines '\n' -> ' '
unwrap.join_lines '\n' -> ' '
confusables.in_numbers '1O5' -> '105'
numbers.separators ' .' -> '.'
punctuation.spacing ' ' -> ''
```

## Install

```bash
pip install git+https://github.com/DuhItzAniket/Lectris
```

LECTRIS needs Python 3.12 or newer.

## The command line

```bash
lectris clean page.hocr                     # the cleaned text, on standard output
lectris clean page.xml -o page.txt -r report.json --summary
lectris clean scan.tsv --profile conservative
lectris eval reference.txt page.txt         # character and word error rates
lectris rules                               # every profile and its rules
```

The input's format is detected from its content; `--format` names it. `--lexicon words.txt` (one
word per line, an optional count after it) makes de-hyphenation and the confusion rules more
precise. No dictionary is bundled.

## Profiles

| Profile | What it changes |
|---|---|
| `conservative` | The safest repairs: line breaks, invisible characters, compatibility forms, ligatures, Unicode composition, extra spaces, and words hyphenated across lines. Line breaks are kept. |
| `standard` (default) | The conservative rules, plus noise lines dropped, paragraphs unwrapped onto one line, letters read inside numbers, spaces inside numbers and before punctuation, and dash variants. |
| `aggressive` | The standard rules, plus digits read inside words, straight quotes and three-dot ellipses. Recall over precision: read its report before trusting it. |

Every profile is idempotent: cleaning its own output changes nothing. The rules, their evidence
and what each one deliberately leaves alone are listed in [docs/rules.md](docs/rules.md).

## Reading OCR output

```python
from pathlib import Path

from lectris import clean, io, report

document = io.read("page.hocr")  # or .xml (ALTO), .tsv, .json, .txt
result = clean(document, profile="standard")
print(report.summary(result))  # edits per rule
Path("report.json").write_text(report.to_json(result), encoding="utf-8")
```

| Format | What is read |
|---|---|
| hOCR | pages, areas and paragraphs, lines, words, with `bbox` and `x_wconf` |
| ALTO XML 2–4 | text blocks, lines and strings with their positions, `WC` confidences and `HYP` hyphens |
| Tesseract TSV | pages, paragraphs, lines and words with boxes and confidences |
| JSON | LECTRIS's own form, or a flat list of lines with `text`, `bbox` and `confidence` |
| Plain text | pages separated by form feeds, paragraphs by blank lines |

When the lines have boxes, the layout steps put them in reading order (columns read whole, a
title before the columns under it) and group them into paragraphs from their spacing, indents
and sentence ends. Every threshold is relative to the size of the text, so a scan at any
resolution gives the same result.

## Measuring OCR

```python
from lectris import metrics

metrics.cer("kitten sat", "sitting sat")  # 0.3: 3 errors in 10 characters
metrics.word_errors("kitten sat", "sitting sat")  # substitutions, deletions, insertions
metrics.confusions(reference, ocr_text)  # which characters the engine mixes up
```

## Design

- **No silent edits.** A rule returns its new text and the edits that produced it; the pipeline
  keeps them all.
- **Precision before recall.** A rule changes text only where local evidence is strong, and each
  rule's tests list the correct text it must leave alone.
- **Pure and deterministic.** The same input always gives the same output.

The architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Scope**: Latin-script text, horizontal lines (scans skewed by a few degrees are corrected),
left-to-right reading order. Tables, and tables of contents whose page numbers stand far to the
right, are read column by column.

## Development

```bash
uv sync
uv run pytest
uv run ruff check && uv run mypy
```

Every pull request is checked by [Repro](https://github.com/DuhItzAniket/Repro), which runs the
tests on both sides of the change, compares what the changed functions actually return, and
posts a Reproduction Card on the pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
