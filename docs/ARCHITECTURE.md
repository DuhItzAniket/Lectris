# Architecture

LECTRIS reads what an OCR engine produced and turns it into clean, ordered text. Every change is
recorded with its rule, its evidence and the decision that accepted it. It works with any engine,
and it is **engine-aware**: when the engine reports how unsure it was (word, line or character
confidences, alternative characters), that uncertainty becomes evidence. The engine it is designed
alongside is [GLYPHARIS](https://github.com/DuhItzAniket/Glypharis).

It does not run OCR, process images or use language models at run time.

> **Status.** Version 0.1 (released) is a pipeline of deterministic rules. This document describes
> the **target architecture v2**, the design behind the research plan
> ([IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)). Every section is marked **[v0.1]**
> (implemented), **[v0.1 → v2]** (implemented, changed by a later phase) or **[v2, Phase N]**
> (planned). Values marked _(tunable)_ are starting points for the experiments to confirm or
> replace. The decisions behind the design are in [decisions/](decisions/).

## 1. The problem

Post-OCR correction faces a trade-off that most systems leave implicit. Every correction that
fixes an error can also break correct text (`modem` → `modern`, `well-known` → `wellknown`,
`1O5` left alone because it is a part number). A corrector that maximises CER reduction on
average can still damage the documents an archive or a search index trusts most. Neural
correctors can also produce fluent text the page never said.

LECTRIS makes that trade-off **explicit and controlled**:

1. Rules and models only **propose** candidate edits. They never apply them.
2. Each candidate is scored from **evidence**: the engine's uncertainty at that span, a channel
   model of what this engine confuses, a character language model, a lexicon and the local
   context.
3. A **calibrated acceptance model** turns the evidence into the probability that the edit is
   right.
4. A **risk-controlled decision** accepts candidates only above a threshold chosen on held-out
   pages. The threshold carries a finite-sample, distribution-free guarantee: with probability at
   least 1 − δ, the expected **harm rate** (correct characters broken, per character) on new pages
   from the same distribution is at most α. A profile is a choice of α.
5. Every accepted edit keeps its **provenance**: rule, span, evidence, probability, threshold.
   Every candidate that was declined but was close is kept as a **review flag**.

The existing ground rules ("no silent edits", "precision before recall") become measurable
properties with a stated guarantee.

## 2. Principles

1. **No silent edits.** [v0.1] Every text change is an `Edit` from a named rule.
   `clean()` returns the text and the report of every edit. [v2] Every edit also carries its
   `Decision` (evidence and probability), and declined candidates are reported as flags.
2. **Propose, then decide.** [v2, Phase 3] A rule that guesses (a repair) proposes candidates. A
   rule that only normalises (Unicode, whitespace) transforms. Only the decision layer accepts a
   guess.
3. **Risk is a parameter, not a habit.** [v2, Phase 7] How much harm a profile may do is a number
   (α), held on held-out data with a stated confidence (1 − δ).
4. **Engine-aware, not engine-dependent.** [v2, Phase 2] Uncertainty from the engine improves
   decisions when it is there. Without it, every component still works on plain text.
5. **Pure and deterministic.** [v0.1] The same input and model pack give the same output. No
   global state, no I/O outside `lectris.io`, `lectris.models` and the CLI, no randomness at run
   time. Fitting is seeded.
6. **Standard library at run time.** [v0.1] Learned components are small statistical models
   (n-gram counts, confusion tables, logistic regression) stored as data, not code
   ([ADR-0004](decisions/ADR-0004-stdlib-runtime-model-packs.md)).
7. **Typed and tested.** [v0.1] `mypy --strict` passes. Every rule and proposer has tests for
   what it changes and for what it must leave alone, plus property tests for its invariants.

Scope: Latin-script text (English and the diacritics of the Western European languages),
horizontal or slightly skewed lines, left-to-right reading order.

## 3. Overview

```
 OCR output (hOCR, ALTO, TSV, JSON, GLYPHARIS JSON, plain text)
      │
      ▼
 L0 Ingest      lectris.io        ─► Document: pages, blocks, lines, words, glyphs
      │                                with boxes, confidences, alternatives
      ▼
 L1 Layout      lectris.layout    ─► blocks in reading order (columns, paragraphs)
      │
      ▼  each block's text, with an offset map back to its glyphs
 ┌──────────────────────── staged passes (profile order) ───────────────────────┐
 │ L2 Normalise  lectris.text      transforms: applied, always recorded         │
 │ L3 Propose    lectris.propose   candidates: span, replacement, rule          │
 │ L4 Evidence   lectris.evidence  features: engine, channel, LM, lexicon, ctx  │
 │ L5 Decide     lectris.decide    p(correct) ─► risk threshold ─► conflicts    │
 │                                 ─► accepted edits + review flags             │
 └──────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
 L6 Result      lectris.pipeline / lectris.report ─► text, edits, decisions, flags

 Offline:  lectris.models (fit, model packs)       lectris.eval (scoring, statistics)
```

**Staged passes.** v0.1 runs its rules in an order that matters (see `lectris/profiles.py`):
unwrapping must happen before the number rules read tokens. v2 keeps that order. A profile is a
sequence of stages, each a set of transforms or proposers. Every stage proposes on the output of
the stage before it, decides and applies. So the "accept every v0.1 candidate" policy reproduces
v0.1 exactly ([ADR-0006](decisions/ADR-0006-v01-as-baseline-and-parity.md)).

## 4. The data model (`lectris.model`)

[v0.1] Frozen dataclasses with slots; sequences are tuples. Coordinates are image coordinates: the
origin is the top-left corner and `y` grows downwards.

| Type | Fields | Text |
|---|---|---|
| `Box` | `x0, y0, x1, y1` (floats, `x0 <= x1`, `y0 <= y1`, else `ValueError`) | — |
| `Word` | `text`, `box=None`, `confidence=None`, [v2] `glyphs=None` | the word |
| `Line` | `words`, `box=None`, `confidence=None`, [v2] `polygon=None`, `detection=None` | words joined by one space |
| `Block` | `lines`, `box=None` | lines joined by `\n` |
| `Page` | `blocks`, `width=None`, `height=None`, `number=1`, [v2] `source=None` | blocks joined by a blank line |
| `Document` | `pages`, [v2] `engine=None` | pages joined by a blank line |

A confidence is a float in `[0, 1]` or `None` (unknown); anything else raises `ValueError`.
Readers convert their format's scale (hOCR's `x_wconf` and TSV's `conf` are 0–100).

**[v2, Phase 2] Uncertainty.**

```python
Glyph(char: str, confidence: float | None, alternatives: tuple[tuple[str, float], ...] = ())
Engine(name: str, version: str, model: str)          # e.g. ("glypharis", "0.1.0", "glypharis-0.1.0")
```

- A word's `glyphs`, when present, spell its `text` exactly (`"".join(g.char for g in glyphs) ==
  text`, else `ValueError`). Alternatives are other characters the engine considered at that
  position, with their probabilities, sorted, never including `char`. The empty string means
  "nothing here" (CTC blank), which makes a deletion a candidate.
- `Line.detection` is the detector's score (GLYPHARIS `det_score`), kept apart from the
  recognition `confidence`. `Line.polygon` keeps a rotated or curved line's outline.
- `Document.engine` identifies the engine and model that produced the input. Engine-specific
  evidence (the channel model, calibration) is valid only for the engine it was fitted on
  ([ADR-0003](decisions/ADR-0003-engine-aware-input.md)).

## 5. Edits, offset maps and provenance (`lectris.edits`, `lectris.decide`)

[v0.1]

```python
Edit(rule: str, start: int, end: int, before: str, after: str)
Revision(text: str, edits: tuple[Edit, ...])
```

- `start` and `end` are offsets in the rule's **input**; `before == input[start:end]`.
- A revision's edits are sorted by `start` and do not overlap. An edit never has
  `before == after`.
- `apply_edits(input, edits) == revision.text` for every revision. The property tests check this
  for every rule.
- Rule ids are `"<module>.<rule>"`, for example `"hyphenation.join"`. They are stable and appear
  in reports and model packs.

**[v2, Phase 2] Offset maps.** `OffsetMap.from_edits(edits)` maps offsets in a stage's output back
to its input. Maps compose across stages, so evidence for a span at any stage can find the
glyphs (and their confidences) it came from. An inserted character maps to the gap it was
inserted into. A property test checks that composing maps equals mapping through each stage in
turn.

**[v2, Phase 3] Decisions.**

```python
Candidate(rule: str, start: int, end: int, before: str, after: str, features: Mapping[str, float])
Decision(candidate: Candidate, probability: float, threshold: float, accepted: bool, reason: str)
```

An accepted decision becomes an `Edit` with the same rule and span. `Revision` gains `decisions`
(the accepted and the declined), and the `Edit` contract is unchanged.

## 6. L0 Ingest: readers (`lectris.io`)

[v0.1]

| Format | Module | Notes |
|---|---|---|
| hOCR | `hocr` | `ocr_page`, `ocr_carea`/`ocr_par`, `ocr_line`, `ocrx_word`; `bbox` and `x_wconf` from `title` |
| ALTO XML | `alto` | versions 2–4; `TextBlock`, `TextLine`, `String`, `SP`, `HYP`; `WC` is already 0–1 |
| Tesseract TSV | `tsv` | `level` 1–5 rows; `conf` −1 marks non-word rows |
| JSON | `jsonio` | LECTRIS's own form, and a flat list of lines with `text`, `bbox`, `confidence` |
| Plain text | `plain` | blocks separated by blank lines, pages by form feeds |

**[v2, Phase 2] Engine-aware readers.**

| Format | Module | Uncertainty read |
|---|---|---|
| GLYPHARIS JSON (`OCRResult.to_dict`) | `glypharis` | page `width`/`height`, line `confidence`, `det_score`, `polygon`, `quad`, `glypharis_version`, `model_version`; per-character `chars` when the engine writes them ([ADR-0003](decisions/ADR-0003-engine-aware-input.md), the contract) |
| ALTO | `alto` | `CC` (character confidences) and `ALTERNATIVE` elements, if present |
| hOCR | `hocr` | per-character confidences and choices from Tesseract's extended hOCR, if present (to be checked against real Tesseract output, Phase 2) |

`lectris.io.read(source, format=None)` detects the format from the content; GLYPHARIS JSON is
recognised by its `glypharis_version` key. Inputs are untrusted: readers never fetch external
resources, and XML is parsed by the standard library's expat, which resolves no external entities.

## 7. L1 Layout (`lectris.layout`)

[v0.1]

| Module | What it does |
|---|---|
| `lines` | words to lines, by vertical overlap |
| `columns` | column ranges, from the gaps in the lines' horizontal projection |
| `order` | reading order by recursive XY-cut over the lines' boxes, with skew correction |
| `paragraphs` | lines to blocks: vertical gaps, indents and alignment |

Layout steps need boxes; lines without boxes keep the order the input gave them. [v2, Phase 2]
With GLYPHARIS input, line polygons give the skew directly, and the engine's own order is kept as
a fallback and as a baseline for the layout evaluation (protocol §3.4).

## 8. L2 Normalise: transforms (`lectris.text`)

[v0.1 → v2] A **transform** is a rule with no guess in it: the change is right whenever its
pattern matches. It is applied without a decision, and its edits are still recorded.

| Module | Transforms |
|---|---|
| `unicode` | NFC; ligatures (`ﬁ` → `fi`); invisible characters; compatibility forms |
| `whitespace` | line breaks; collapse runs of spaces and tabs; trim line ends |
| `punctuation` | dashes; quotes and ellipsis (style choices, aggressive profile) |
| `unwrap` | join a paragraph's lines onto one line |

**The rule contract** (unchanged from v0.1, and it holds for transforms and proposers alike). A
rule is a function `rule(text: str, /, **options) -> Revision` (a transform) or
`-> tuple[Candidate, ...]` (a proposer). It must:
- record every change as an edit, or propose it as a candidate (never return changed text without
  an edit);
- leave text it has no evidence about unchanged, or propose nothing for it;
- give offsets in its input, sorted, non-overlapping for a transform's edits (a proposer's
  candidates may overlap; the decision layer resolves conflicts);
- be idempotent unless documented otherwise: `rule(rule(t).text).edits == ()`, and for a
  profile, cleaning its own output accepts nothing.

## 9. L3 Propose: proposers (`lectris.propose`)

[v2, Phase 3] A **proposer** finds spans that may be OCR errors and proposes replacements. It
attaches rule-specific features (for example, "both halves are in the lexicon"), but it does not
decide.

| Proposer | From | What it proposes |
|---|---|---|
| `confusables.in_numbers`, `confusables.in_words` | v0.1 rules | letters read in numbers, digits read in words |
| `numbers.separators` | v0.1 rule | spaces inside numbers removed |
| `punctuation.spacing` | v0.1 rule | spaces before punctuation removed |
| `hyphenation.join` | v0.1 rule | a word hyphenated across a line break rejoined (or the hyphen kept, for a compound) |
| `noise.drop_lines` | v0.1 rule | a noise line deleted |
| `channel.lexical` [Phase 6] | new | for a token outside the lexicon, in-lexicon words within a weighted channel distance (a SymSpell-style deletion index, standard library) |
| `engine.alternatives` [Phase 6] | new | a low-confidence character replaced by the engine's own alternative (needs glyphs) |
| `segmentation.spaces` [Phase 6] | new | a missing space inserted (`thecat`) or a spurious one removed (`th e`) |

The v0.1 rules keep their names, their tests and their "left alone" lists. In v2, their regexes
and conditions become the proposers' **candidate generators** (recall) and features (evidence).
How strict each one was in v0.1 is reproduced by the parity policy (§11.4).

## 10. L4 Evidence (`lectris.evidence`)

[v2, Phase 6] Each candidate gets a feature vector. Every feature is defined on plain text, and
engine features are missing (with a "missing" indicator) when the input has no uncertainty.

| Group | Features _(tunable)_ | Source |
|---|---|---|
| Engine | min and mean glyph confidence over the span; line confidence; detection score; whether `after` is among the engine's alternatives at the span, and its probability | `Glyph`, `Line` |
| Channel | log P(observed \| intended) under the engine's confusion model (substitutions, insertions, deletions, and substring pairs up to length 2 such as `rn`/`m`, after Brill and Moore) | model pack |
| Language | Δ log P of a character n-gram model (order 6, interpolated modified Kneser–Ney) over a window around the span, per character | model pack |
| Lexicon | `before`/`after` token in the lexicon; log frequencies; frequency ratio | `Lexicon` |
| Context | token class (alphabetic, numeric, mixed); case pattern; position in the line; span length | text |
| Rule | the rule id (one-hot); the proposer's own features | proposer |

## 11. L5 Decide (`lectris.decide`)

### 11.1 Acceptance model
[v2, Phase 7] The probability that a candidate is right, p = σ(w · φ(candidate)): a logistic
regression with L2 regularisation over the features, fitted by iteratively reweighted least
squares (a few dozen features; standard library). One model is fitted per engine pack, with the
rule as a feature, so rules with few candidates borrow strength from the others. Calibration is
measured (ECE, reliability curves) on held-out pages. If needed, Platt scaling on the calibration
split corrects it.

### 11.2 Risk-controlled threshold
[v2, Phase 7] A candidate is accepted if p ≥ λ. λ is chosen with **Learn-then-Test** (Angelopoulos
et al.) on the calibration split, which is made of whole pages:

- Loss of a page at threshold λ: L(λ) = (characters broken by accepted harmful edits) /
  max(1, characters of the ground truth), clipped to [0, 1]. An edit is *harmful* if applying it
  raises the edit distance to the ground truth in its aligned window (protocol §3.2).
- Risk: R(λ) = E_page[L(λ)], the expected **harm rate**.
- For each λ on a grid from strict to permissive, test H₀: R(λ) > α with a Hoeffding–Bentkus
  p-value over the calibration pages. Fixed-sequence testing at level δ stops at the first
  H₀ that is not rejected, and λ̂ is the most permissive λ rejected before it.
- Guarantee: P(R(λ̂) ≤ α) ≥ 1 − δ over the draw of calibration pages, for test pages exchangeable
  with them (same engine and model, same kind of document). Pages, not edits, are the unit,
  because edits on a page are not independent.
- If no λ passes, the profile accepts no guesses (transforms still apply). It says so in the
  report.

Profiles become risk budgets _(tunable)_: `conservative` α = 0.001, `standard` α = 0.005,
`aggressive` α = 0.02, all with δ = 0.1. Precision of accepted edits, recall of correctable
errors and the fraction of pages made worse are reported for each, but only the harm rate is
guaranteed. Under a different engine or domain the guarantee does not carry over, and protocol
§5 measures how far it holds in practice.

### 11.3 Conflicts
[v2, Phase 7] Overlapping candidates (`rn` → `m` and `modem` → `modern` on the same token) are
resolved by weighted interval scheduling: the accepted non-overlapping set maximises
Σ (p·gain − (1 − p)·cost), where gain and cost are the candidate's character counts. Ties break by
rule order, then offset, so the result is deterministic.

### 11.4 Policies
| Policy | What decides | Use |
|---|---|---|
| `parity` | every candidate the v0.1 rule would have applied is accepted (the proposer's v0.1 condition is a feature, and its value is the decision) | reproduces v0.1 byte for byte (Phase 3 exit), the rule baseline in the paper |
| `risk` | §11.1–11.3 with the profile's α | the default once a model pack exists |
| `threshold` | p ≥ a fixed λ, no guarantee | ablations, threshold sweeps |

Without a model pack, `clean()` uses `parity`. That is LECTRIS v0.1's behaviour, so no user is
broken.

### 11.5 Review flags
[v2, Phase 8] A declined candidate with p ≥ λ_flag _(tunable)_, and any span whose engine
confidence is below a threshold, is reported as a `Flag`: its span, the best candidate, its
probability and why it was declined. It is selective prediction, in the archive's terms: what a
person should look at.

## 12. Model packs and fitting (`lectris.models`)

[v2, Phase 6] A model pack is a versioned JSON (gzip) file:

```
manifest      pack version, LECTRIS version, engine (name, version, model), fit data hashes, seed
channel       confusion counts and substring pairs, with smoothing
language      character n-gram counts (pruned) and discounts
lexicon       optional word counts (or a reference to a separate word list)
acceptance    feature names, weights, scaling, calibration
risk          per profile: α, δ, λ̂, the calibration pages' count and hash
```

`lectris fit --pairs fit/ --calibrate cal/ --engine glypharis-0.1.0 -o pack.json.gz` builds a
pack from paired OCR and ground-truth pages (protocol §1). Fitting is deterministic for a
seed. A pack refuses to run on input from another engine unless `--allow-engine-mismatch` is
given, and then it reports that the guarantee does not apply.

No pack is bundled with the library until the licences of its sources are cleared
([DATASETS.md](../DATASETS.md)).

## 13. Evaluation (`lectris.eval`, `lectris.metrics`, `lectris.align`)

[v0.1] Levenshtein, Damerau–Levenshtein and OCR-weighted distances; character and word
alignment; CER and WER; confusion counts.

[v2, Phase 4]
- **Edit scoring.** Each edit (or candidate) is labelled *fix*, *harm* or *neutral* by aligning
  the OCR text with the ground truth and comparing the distance in the edit's aligned window
  before and after it.
- **Line matching.** With boxes, OCR lines are matched to ground-truth lines by box overlap before
  text is compared, so a reading-order difference is not counted as recognition errors. Layout
  is scored separately (protocol §3.4).
- **Statistics.** Paired bootstrap over pages (1,000 resamples, 95% CI) for every difference,
  under the decision rule in the protocol.
- **Experiments.** `lectris experiment run configs/LX-....json` runs a registered experiment and
  writes `reports/LX-.../report.{md,json}`, with the code version, pack hash and data hashes.

## 14. The pipeline and public interface (`lectris.pipeline`)

[v0.1]

```python
result = lectris.clean(document_or_text, profile="standard", lexicon=None)
result.text  # the cleaned text
result.blocks  # CleanBlock: page, index, box, confidence, source text, text, revisions
result.changes()  # every edit, located by page, block and step
result.counts()  # edits per rule
```

[v2, Phase 3 and 8] Additions; every v0.1 call keeps its meaning.

```python
result = lectris.clean(document, profile="standard", pack=lectris.models.load("pack.json.gz"))
result.decisions()  # every candidate: accepted or declined, with evidence and probability
result.flags()  # spans for review
result.guarantee  # α, δ, λ̂ and whether the pack matches the input's engine
```

`lectris.report` renders a result as a summary, JSON or Markdown, and [v2] includes the evidence
behind each edit. The CLI adds `lectris fit`, `lectris experiment` and `lectris clean --pack`.

GLYPHARIS and LECTRIS are joined only through the JSON contract; neither imports the other:

```
glypharis-ocr --image page.png --output out/          # out/page.json
lectris clean out/page.json --pack glypharis-0.1.0.lectris.json.gz -r report.json
```

## 15. Mapping v0.1 to v2

| v0.1 | v2 | Phase |
|---|---|---|
| `lectris.text.*` repairs (confusables, numbers, punctuation.spacing, hyphenation, noise) | proposers in `lectris.propose`, with the v0.1 condition kept as a feature | 3 |
| `lectris.text.*` normalisation | transforms, unchanged | — |
| `Profile` of `Step`s | `Profile` of stages, with a policy and a risk budget | 3, 7 |
| `confidence` aggregation | engine evidence features | 6 |
| `distance`, `lexicon` | channel evidence, `channel.lexical` proposer | 6 |
| `metrics`, `align` | `lectris.eval` edit scoring and statistics | 4 |

## 16. Code conventions

- Python 3.12+, `src/` layout, absolute imports only.
- Public functions and classes have a docstring: one summary line, then what a caller needs (the
  rule's evidence, what it leaves alone).
- No `print`: the CLI writes to `sys.stdout`.
- Errors derive from `lectris.errors.LectrisError`. `FormatError` is an input a reader cannot
  read; [v2] `PackError` is a model pack that cannot be used.
- Tests live in `tests/`, one file per module (`test_text_hyphenation.py`), with `pytest`
  parametrisation for cases and `hypothesis` for invariants. Test data is written for this
  project; no third-party documents are copied into it.
- [v2] Experiment code lives in `lectris.eval` (standard library) or, for neural baselines only,
  in `research/baselines/` with its own environment
  ([ADR-0004](decisions/ADR-0004-stdlib-runtime-model-packs.md)).
