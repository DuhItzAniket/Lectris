# Implementation plan

The phases that take LECTRIS from the v0.1 rule engine to the v2 architecture
([ARCHITECTURE.md](ARCHITECTURE.md)) and to a research paper. Each phase has its tasks,
deliverables and exit criteria. Live status is in [PHASE_STATUS.md](PHASE_STATUS.md); milestones
and the dependency graph are in [ROADMAP.md](ROADMAP.md).

## 1. Goal

A post-OCR correction method that is **auditable** (every edit explained), **risk-controlled**
(a stated bound on the harm it does, on held-out pages) and **engine-aware** (it uses the OCR
engine's own uncertainty), implemented as a dependency-free library, evaluated with GLYPHARIS and
Tesseract under one protocol ([EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)).

Working title of the paper: *LECTRIS: auditable, risk-controlled post-OCR correction with engine
uncertainty.*

## 2. Ground rules

The rules in [CLAUDE.md](../CLAUDE.md) apply to every phase. In addition:
- **Pre-registration light.** Hypotheses ([research/hypotheses.md](../research/hypotheses.md)) and
  each experiment's plan are written before it runs. Numbers come from generated reports only.
- **Test discipline.** Test sets are read only in Phase 13, and every read is logged
  ([research/test_access_log.md](../research/test_access_log.md)).
- **Parity first.** No phase may change v0.1 output under the `parity` policy (ADR-0006).
- **Phase gate** (every phase): tests, ruff, mypy green; docs and CHANGELOG updated; PHASE_STATUS
  entry written with measured numbers; pull request with CI and Repro green; squash merge; tag
  `phase-NN`.

## 3. Research questions → where they are answered

| RQ | Question | Phases |
|---|---|---|
| RQ1 | How much do risk-controlled corrections lower CER and WER on modern document OCR, and how much harm do they do, against no correction, the v0.1 rules, a lexicon corrector and a neural corrector? | 9, 10, 13 |
| RQ2 | Does engine uncertainty (line confidence, detector score, character confidences and alternatives) raise recall at the same harm budget? | 10, 11 |
| RQ3 | Does the Learn-then-Test threshold hold the harm rate at α on unseen pages, and what recall does the guarantee cost against an oracle threshold? | 10, 13 |
| RQ4 | Do calibration and the guarantee transfer to another engine (Tesseract) or another document set (GDC)? | 12, 13 |
| RQ5 | Which OCR errors remain beyond local correction (segmentation, reading order, hallucinated lines), and how are they distributed between detector and recognizer? | 14 |
| RQ6 | What does correction cost on a CPU, against the engine's own time per page and a neural corrector? | 15 |

## 4. Data strategy (summary; [ADR-0005](decisions/ADR-0005-data-roles.md), [DATASETS.md](../DATASETS.md))

Pairs of engine output and ground truth, by page: HierText validation (fit / cal / dev),
GlyphSynth validation (auxiliary), GDC (test). PG-19 text for the language model and word counts.
Nothing from these enters the repository; manifests do.

## 5. Phases

### Phase 0 — v0.1 rule engine ✅
Readers for five formats, layout, seventeen rules in three profiles, every edit recorded, metrics.
Released as v0.1.0 (2026-10-31).

### Phase 1 — Research planning
- **Tasks:** target architecture v2; ADR-0001 to 0007; this plan, the roadmap, the protocol, the
  risk register, the dataset cards; hypotheses H1–H6; research log, experiment registry, test
  access log, paper outline.
- **Exit:** documents reviewed by the owner; links resolve; tests, lint and types still green.

### Phase 2 — Engine-aware input and the GLYPHARIS contract
- **Tasks:** `Glyph`, `Engine`, `Line.polygon`, `Line.detection`, `Page.source`,
  `Document.engine`, with validation; `lectris.io.glypharis` and detection; ALTO `CC` and
  `ALTERNATIVE`; `OffsetMap` (from edits, composition) with property tests; a hand-written
  GLYPHARIS JSON fixture (with and without `chars`); `lectris clean page.json` end to end.
- **Deliverables:** the reader, the fixture, a contract test; a GLYPHARIS issue or pull request
  proposing `chars` (owner's call).
- **Exit:** every field of `OCRResult.to_dict` is read or deliberately ignored, and a test says
  which; the offset-map properties hold; v0.1 tests unchanged and green.

### Phase 3 — Candidate core with v0.1 parity
- **Tasks:** `Candidate`, `Decision`, `Revision.decisions`; `lectris.propose` (the six v0.1 repair
  rules as proposers, their v0.1 condition as a feature); stages in `Profile`; `lectris.decide`
  with the `parity` and `threshold` policies and the interval-scheduling conflict resolver;
  `tests/legacy/` and the parity test.
- **Exit:** parity holds byte for byte on the suite and on the generated corpus, for every profile;
  idempotence holds; the old public API is unchanged.

### Phase 4 — Evaluation harness
- **Tasks:** `lectris.eval`: edit scoring (fix, harm, neutral) by windowed alignment; line matching
  by box overlap; page CER/WER under the normalisation tracks; harm rate; paired bootstrap over
  pages; the experiment config and report format; `lectris experiment run`.
- **Exit:** scoring is tested on hand-made pairs with known labels (including reading-order swaps
  and insertions); bootstrap reproduces for a seed; a dry-run experiment writes a report.

**→ v0.2: integration release.** Joint test with GLYPHARIS v0.1 (ADR-0007).

### Phase 5 — Paired data
- **Tasks:** scripts that run GLYPHARIS (`glypharis-ocr`, JSON) and Tesseract (hOCR) on HierText
  validation and GlyphSynth validation pages; pair them with ground truth; page splits; manifests
  with counts and hashes; a data audit (error rates by slice, what the errors are made of).
- **Deliverables:** `data/manifests/*.json`, `reports/data/audit.md` (aggregates only).
- **Exit:** splits deterministic and disjoint by page; audit written; the share of character
  errors that lie inside a single token (locally correctable, an upper bound for the method)
  measured.

### Phase 6 — Evidence models and model packs
- **Tasks:** character n-gram LM (interpolated modified Kneser–Ney, pruning), channel model
  (substitutions, insertions, deletions, substring pairs), word counts from PG-19; engine
  features; the new proposers (`channel.lexical`, `engine.alternatives`, `segmentation.spaces`);
  pack format, `lectris fit`, `lectris.models.load`; fit-time and size measurements.
- **Exit:** perplexity of the LM on dev text reported; channel model log-likelihood on dev pairs
  better than uniform-cost Levenshtein; fit deterministic for a seed; pack round-trips.

### Phase 7 — Acceptance model and risk control
- **Tasks:** feature scaling; logistic regression by IRLS; calibration (ECE, reliability, Platt if
  needed); Learn-then-Test with Hoeffding–Bentkus p-values; the `risk` policy; profiles as (α, δ);
  a power check (λ̂ against calibration size); a simulation test of validity on synthetic data
  with a known risk.
- **Exit:** on simulated data the realised risk exceeds α in at most δ of 1,000 repetitions;
  calibration report on dev; profiles defined.

### Phase 8 — Explanations, flags and the v0.3 interface
- **Tasks:** `result.decisions()`, `result.flags()`, `result.guarantee`; report JSON/Markdown with
  evidence; `lectris clean --pack`; docs/rules.md updated with each proposer's features; README.
- **Exit:** every accepted edit in a report shows its probability and top features; a mismatched
  engine pack is refused or warned about.

**→ v0.3: the method, complete.**

### Phase 9 — Baselines
- **Tasks:** B0 no correction; B1 v0.1 rules (`parity`); B2 a lexicon corrector (SymSpell-style,
  standard library, best-candidate replacement for out-of-lexicon tokens); B3 ByT5-small
  fine-tuned on the fit split (research environment, ADR-0004, if approved); B4 optional LLM
  zero-shot (if approved, with the data rules in the protocol).
- **Exit:** every baseline produces JSON scored by `lectris.eval` on dev; budgets and settings
  recorded.

### Phase 10 — Main study (dev)
- **Tasks:** RQ1–RQ3 on dev with GLYPHARIS output: CER/WER, harm rate, precision, recall, pages
  worsened, for each profile and baseline; harm-matched comparison (each baseline thresholded to
  the same harm where it has a score); validity over 1,000 random cal/dev re-splits; oracle
  threshold.
- **Exit:** H1, H3 decided on dev; reports generated.

### Phase 11 — Ablations
- **Tasks:** remove each evidence group; LM order 3/4/6; character alternatives on/off (if
  available); calibration size 100–full; α sweep; proposer by proposer.
- **Exit:** H2 decided on dev; ablation table generated.

### Phase 12 — Engine transfer
- **Tasks:** packs fitted on GLYPHARIS used on Tesseract output and the reverse; packs fitted per
  engine; calibration and validity under transfer.
- **Exit:** H4 decided on dev.

### Phase 13 — Test evaluation (once)
- **Tasks:** freeze packs, code version and GLYPHARIS model; run GDC (and optional external sets)
  once; log the access.
- **Exit:** test report generated; no change to anything after it except documented bug fixes,
  which are re-run in full and reported as such.

### Phase 14 — Error analysis
- **Tasks:** taxonomy of residual errors (in-token, segmentation, line-level, reading order,
  hallucinated or missed lines); harmful edits that passed; flags against the errors they cover.
- **Exit:** RQ5 tables and examples (examples from original or synthetic data only in the
  repository).

### Phase 15 — Efficiency
- **Tasks:** CPU time and memory per page for each profile and baseline; against GLYPHARIS's time
  per page on the same machine.
- **Exit:** H6 decided.

### Phase 16 — Research package
- **Tasks:** paper draft from `research/paper/`; every number traced to a report; bibliography
  checked; limitations; reproducibility appendix (commands, hashes).
- **Exit:** draft complete; every table regenerates from a script.

### Phase 17 — Release v1.0
- **Tasks:** API review; deprecations; packs published if licences allow; CHANGELOG; tag `v1.0.0`.
- **Exit:** release built and tested on the CI matrix.

## 6. Experiment design defaults

- Unit: the page. Splits, bootstrap and the risk guarantee are all by page.
- Bootstrap: paired, 1,000 resamples, 95% percentile CI, seed 1337.
- **Better** means the CI of the difference excludes zero; otherwise "no clear difference".
- Seeds: fitting is deterministic; the variance that matters is the split, so headline numbers
  are reported over five split seeds (1337, 2024, 7, 42, 99) where a re-split is possible.
- Experiment IDs: `LX-<AREA>-NNN`, areas `DATA`, `FIT`, `CAL`, `RISK`, `BASE`, `MAIN`, `ABL`,
  `XFER`, `TEST`, `ERR`, `EFF`. Registered in [research/experiments.md](../research/experiments.md)
  before they run.
