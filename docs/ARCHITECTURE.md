# Architecture

LECTRIS turns OCR output into clean, ordered text. It reads what an OCR engine produced (words and
lines with boxes and confidences), puts the lines in reading order, groups them into paragraphs,
and repairs the text: Unicode and whitespace, ligatures, words hyphenated across lines, characters
that OCR confuses, and noise lines. Every change to the text is recorded with the rule that made
it, so a result can always be explained and audited.

It does not run OCR, process images or use language models.

## Principles

1. **No silent edits.** Every text change is an `Edit`: the rule, the span in the input, what was
   there and what replaced it. `clean()` returns the text and the report of every edit.
2. **Conservative by default.** A rule changes text only where local evidence is strong. Where it
   is not, the text is left as it was. The `standard` profile is safe for archival text;
   `aggressive` trades precision for recall and says so.
3. **Pure and deterministic.** Functions take values and return new values. No global state, no
   I/O outside `lectris.io` and the CLI, no randomness. The same input gives the same output.
4. **No runtime dependencies.** The standard library only.
5. **Typed and tested.** `mypy --strict` passes. Every rule has unit tests for what it changes and
   what it must leave alone, and property tests for its invariants.

Scope of v0.1: Latin-script text (English, and the Western European languages' diacritics),
horizontal lines, left-to-right reading order.

## Two stages

```
input file ──► lectris.io ──► Document ──► layout ──► Document (blocks in reading order)
                                                          │
                                       each block's text  ▼
                              text rules (Revision + Edits) ──► Result: text + report
```

1. **Structure.** A reader builds a `Document` of pages, blocks, lines and words, with boxes and
   confidences where the format has them. Layout steps then group words into lines, find columns,
   order lines for reading and group them into paragraphs (blocks).
2. **Text.** Each block's text (its lines joined by `\n`) goes through the text rules in order.
   A rule returns a `Revision`: the new text and the edits that produced it. De-hyphenation and
   unwrapping work across the `\n` between lines, which is why the unit of repair is the block.

The text stage does not rewrite words and boxes: after de-hyphenation a word no longer has one
box. A `Result` holds the cleaned blocks with their source text, and the layout `Document`
stays available for anything geometric.

## The data model (`lectris.model`)

Frozen dataclasses with slots; sequences are tuples. Coordinates are image coordinates: the origin
is the top-left corner and `y` grows downwards.

| Type | Fields | Text |
|---|---|---|
| `Box` | `x0, y0, x1, y1` (floats, `x0 <= x1`, `y0 <= y1`, else `ValueError`) | — |
| `Word` | `text`, `box=None`, `confidence=None` | the word |
| `Line` | `words`, `box=None`, `confidence=None` | words joined by one space |
| `Block` | `lines`, `box=None` | lines joined by `\n` |
| `Page` | `blocks`, `width=None`, `height=None`, `number=1` | blocks joined by a blank line |
| `Document` | `pages` | pages joined by a blank line |

A confidence is a float in `[0, 1]` or `None` (unknown); anything else is a `ValueError`. Readers
convert their format's scale (hOCR's `x_wconf` and TSV's `conf` are 0–100).

## Edits (`lectris.edits`)

```python
Edit(rule: str, start: int, end: int, before: str, after: str)
Revision(text: str, edits: tuple[Edit, ...])
```

- `start` and `end` are offsets in the rule's **input**; `before == input[start:end]`.
- A revision's edits are sorted by `start` and do not overlap. An edit never has
  `before == after`.
- `apply_edits(input, edits) == revision.text` for every revision a rule returns. The property
  tests check this for every rule.
- Rules are identified as `"<module>.<rule>"`, for example `"hyphenation.join"` or
  `"unicode.ligatures"`. The ids are stable: they appear in reports.

`substitute(text, pattern, replace, rule)` builds a revision from a regular expression, recording
one edit per match whose replacement differs.

## Text rules (`lectris.text`)

A rule is a function `rule(text: str, /, **options) -> Revision`. It must:
- record every change as an edit (never return changed text with no edit);
- leave text it has no evidence about unchanged;
- be idempotent unless documented otherwise: `rule(rule(t).text).edits == ()`.

| Module | Rules |
|---|---|
| `unicode` | NFC normalisation; ligatures (`ﬁ` → `fi`); invisible characters (soft hyphen, zero-width, BOM); compatibility forms |
| `whitespace` | collapse runs of spaces and tabs; trim line ends; normalise line breaks |
| `punctuation` | spaces before `.,;:!?` and inside brackets; straight or curly quotes; dashes; ellipsis |
| `hyphenation` | join words hyphenated at line ends; suspended hyphens, compounds with a second hyphen and French clitics are kept, and a lexicon tells other compounds (`well-known`) from split words |
| `confusables` | letters read as digits and digits as letters, from their context (`O`/`0`, `l`/`1`, `S`/`5`) |
| `numbers` | decimal and thousands separators broken by OCR spaces |
| `unwrap` | join a paragraph's lines into one line |
| `noise` | drop lines that are OCR noise (scanner specks, ruled lines, pictures read as characters), keeping section breaks |

## Layout (`lectris.layout`)

| Module | What it does |
|---|---|
| `lines` | words to lines, by vertical overlap |
| `columns` | column ranges, from the gaps in the lines' horizontal projection |
| `order` | reading order by recursive XY-cut over the lines' boxes |
| `paragraphs` | lines to blocks: vertical gaps, indents and alignment |

Layout steps need boxes. Lines without boxes keep the order the input gave them.

## Supporting modules

| Module | What it holds |
|---|---|
| `distance` | Levenshtein and Damerau–Levenshtein distances, and an OCR-weighted distance where common confusions (`rn`/`m`, `cl`/`d`, `0`/`O`) cost less |
| `lexicon` | an optional word list with frequencies: membership and suggestions. No dictionary is bundled |
| `confidence` | aggregate word confidences to lines, blocks and pages; find low-confidence spans |
| `quality` | heuristics for text that is not language: symbol ratios, repeated characters, vowel ratio |
| `align` | character and word alignment of two texts (substitutions, insertions, deletions) |
| `metrics` | character and word error rates (CER, WER) from those alignments |

## Readers (`lectris.io`)

| Format | Module | Notes |
|---|---|---|
| hOCR | `hocr` | `ocr_page`, `ocr_carea`/`ocr_par`, `ocr_line`, `ocrx_word`; `bbox` and `x_wconf` from `title` |
| ALTO XML | `alto` | versions 2–4; `TextBlock`, `TextLine`, `String`, `SP`, `HYP`; `WC` is already 0–1 |
| Tesseract TSV | `tsv` | `level` 1–5 rows; `conf` −1 marks non-word rows |
| JSON | `jsonio` | LECTRIS's own form, and a flat list of lines with `text`, `bbox`, `confidence` |
| Plain text | `plain` | blocks separated by blank lines, pages by form feeds |

`lectris.io.read(source, format=None)` detects the format from the content when none is given.
Inputs are untrusted: readers never fetch external resources, and XML is parsed by the standard
library's expat, which resolves no external entities.

## The pipeline (`lectris.pipeline`)

```python
result = lectris.clean(document_or_text, profile="standard", lexicon=None)
result.text  # the cleaned text
result.blocks  # CleanBlock: page, index, box, confidence, source text, text, revisions
result.changes()  # every edit, located by page, block and step
result.counts()  # edits per rule
```

A `Profile` says whether to arrange the layout and lists its text rules in order, each a `Step`
with its options. `lectris.profiles` defines `conservative`, `standard` and `aggressive`, and
explains their order; `lectris.report` renders a result as a summary, JSON or Markdown.

Plain text given to `clean()` as a string reaches the rules as written, so changes to its spacing
and line breaks are recorded. A document's blocks reach them as their lines' text, built from the
words.

## Code conventions

- Python 3.12+, `src/` layout, absolute imports only.
- Public functions and classes have a docstring: one summary line, then what a caller needs (the
  rule's evidence, what it leaves alone).
- No `print`: the CLI writes to `sys.stdout`.
- Errors derive from `lectris.errors.LectrisError`. `FormatError` is an input a reader cannot read.
- Tests live in `tests/`, one file per module (`test_text_hyphenation.py`), with `pytest`
  parametrisation for cases and `hypothesis` for invariants. Test data is written for this
  project; no third-party documents are copied into it.
