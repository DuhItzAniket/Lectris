# Phase status

Live record of every phase. Values are measured or quoted from generated reports, never invented.
The phases are defined in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

| Phase | Name | Status | Tag |
|---|---|---|---|
| 0 | v0.1 rule engine | **COMPLETE** | `v0.1.0` |
| 1 | Research planning | **COMPLETE** (merged in #15; no phase tag) | — |
| 2 | Engine-aware input and the GLYPHARIS contract | **COMPLETE** (#18, #19, #20; no phase tag) | — |
| 3 | Candidate core with v0.1 parity | **COMPLETE** (#21; no phase tag) | — |
| 4 | Evaluation harness | **COMPLETE** (#22; no phase tag) | — |
| 5 | Paired data | **COMPLETE** (#24, R-15 fix #25; no phase tag) | — |
| 6 | Evidence models and model packs | **COMPLETE** (#26, #27; no phase tag) | — |
| 7 | Acceptance model and risk control | **COMPLETE** (#28; no phase tag) | — |
| 8 | Explanations, flags and the v0.3 interface | **COMPLETE** (#29; no phase tag) | — |
| 9 | Baselines | **IN PROGRESS** (B0–B3 done; B4 not run) | — |
| 10 | Main study (dev) | **IN PROGRESS** (H3 tested: LX-RISK-002) | — |
| 11 | Ablations | not started | — |
| 12 | Engine transfer | **IN PROGRESS** (H4 decided on dev: LX-XFER-001) | — |
| 13 | Test evaluation | not started | — |
| 14 | Error analysis | not started | — |
| 15 | Efficiency | **IN PROGRESS** (H6 measured: LX-EFF-001) | — |
| 16 | Research package | not started | — |
| 17 | Release v1.0 | not started | — |

## Open items for the owner

| Item | Needed by | Status |
|---|---|---|
| Review the v2 architecture and the research framing (ADR-0001, 0002) | Phase 2 | open |
| Approve or decline the research environment for neural baselines (ADR-0004, point 3) | Phase 9 | **approved** (2026-11-23); B3 run |
| Decide whether GLYPHARIS exports per-character `chars` (ADR-0003); GLYPHARIS 1.0 does not | Phase 6 (RQ2 character arm) | open; the owner asked that LECTRIS work not touch the GLYPHARIS repository |
| GLYPHARIS v1.1 installable on Python 3.12+ (1.0 pins `<3.12`, LECTRIS needs `>=3.12`); the CLI handoff through JSON works across two environments meanwhile | joint Python use | open (GLYPHARIS side) |
| GLYPHARIS output (JSON) on HierText validation and GlyphSynth validation pages, with the model version | Phase 5 | HierText done (glypharis_v1, Phase 5); GlyphSynth not (line images) |
| Tesseract installed, its version, for the transfer engine | Phase 5 | **done** (5.4.0, 2026-11-23; H4 run) |
| Target venue (journal or conference) and its page limit | Phase 16 | open |
| PyPI: a pending publisher for `lectris` and the protected `pypi` environment (docs/RELEASING.md); the release workflow is merged (#23) | first PyPI release | **done** (2026-11-23): v0.3.0 published on PyPI by the release workflow (Trusted Publishing) |
| The GDC test (Phase 13): freeze the configuration and run it once, logging the access in both projects | Phase 13 | **done** in LECTRIS (LX-TEST-001, re-run as LX-TEST-002 after a scoring fix; `research/test_access_log.md`); logged in GLYPHARIS too (DuhItzAniket/Glypharis#32, by the owner) |
| Reproduce the calibrated pack from code: it was calibrated at the Phase 7 code, before the `lexical_rank` feature; today's `lectris calibrate` on the same inputs gives other thresholds (0.43 / 0.54 / 0.43) | Phase 16 (reproducibility) | open: record the commit to calibrate at, or recalibrate and re-run dev (the test may not be re-run for it) |

---

## Phase 0 — v0.1 rule engine

**Status:** COMPLETE (released 2026-10-31 as v0.1.0; one rule change since, in `Unreleased`).

**Results (measured):** 1,270 tests pass (2026-11-14, `uv run pytest`).

---

## Phase 1 — Research planning

**Status:** COMPLETE (opened 2026-11-14 on `docs/research-plan`, merged 2026-11-14 as #15).

**Implemented**
- Target architecture v2 (`docs/ARCHITECTURE.md`), ADR-0001 to ADR-0007.
- Implementation plan, roadmap, experiment protocol, risk register, dataset cards.
- Hypotheses H1–H6, experiment registry, research log, test access log, related-work notes, paper
  outline.

**Known issues**
- Related-work notes are written from memory and are unverified; the novelty claim (risk control
  over harm in post-OCR correction) must be checked by a literature search before Phase 16
  (RISK_REGISTER R-03).
- Dataset licences are quoted from GLYPHARIS's DATASETS.md and must be re-checked for LECTRIS's
  uses (derived word counts, pack publication).

---

## Phase 2 — Engine-aware input and the GLYPHARIS contract

**Status:** COMPLETE (opened 2026-11-22, closed 2026-11-23). Landed in three pull requests:
1. the GLYPHARIS reader and the model's detection fields (this branch, `phase/02-glypharis-reader`);
2. `OffsetMap`, from edits and composed across stages, with property tests;
3. ALTO `CC` and `ALTERNATIVE`, and `Glyph`, once a real input that carries them is in hand.

**Part 1, implemented**
- `Engine`, `Line.polygon`, `Line.detection`, `Document.engine`, validated; kept by layout and
  `clean()`; written and read by LECTRIS's JSON form only when set.
- `lectris.io.glypharis`: reads every key GLYPHARIS 1.0's `OCRResult.to_dict` writes, or ignores
  it on purpose (`READ`, `IGNORED`, `LINE_READ`, `LINE_IGNORED`); detection by the first key;
  `--format glypharis`.
- A hand-written fixture in the exact shape of GLYPHARIS 1.0's JSON, and a contract test: the
  fixture holds every key, and every key is either read or ignored.

**Deviations from the plan**
- `Page.source` (ADR-0003) is not added: no format names its image, and the caller knows the file.
- `Glyph` and the `chars` field wait for GLYPHARIS to write them (it does not in 1.0).

**Part 1** merged as #18 (2026-11-23).

**Part 2** merged as #19 (2026-11-23).

**Part 3** merged as #20 (2026-11-23).

**Part 3, implemented:** `Glyph` and `Word.glyphs`/`Word.alternatives`; ALTO `CC` (levels 0 to 9
as confidences `1 - level/9`) and `ALTERNATIVE`; the GLYPHARIS reader reads ADR-0003's proposed
`chars` when present (`LINE_PROPOSED`); LECTRIS's JSON form writes and reads glyphs and
alternatives when set. hOCR character confidences are not read: no real Tesseract output with
them is at hand to check the format against. `uv run pytest`: 1,388 passed (2026-11-23).

**Part 2, implemented:** `lectris.edits.OffsetMap` (`from_edits`, `then`, `source`), with property
tests against a character-by-character reference and for composition. `uv run pytest`: 1,347
passed (2026-11-23).

**Part 1 results (measured):** `uv run pytest`: 1,335 passed (2026-11-22). Cleaning the fixture gives
the same text through the new reader as through the flat JSON reading, for all three profiles
(a test).

---

## Phase 3 — Candidate core with v0.1 parity

**Status:** COMPLETE (opened 2026-11-23 on `phase/03-candidate-core`, merged as #21).

**Implemented**
- `Candidate` and `Decision` in `lectris.edits`; `Revision.decisions`.
- `lectris.propose`: `PROPOSERS` (the six v0.1 repairs) and `candidates(revision)`, which marks
  each of a rule's edits `v01 = 1`.
- `lectris.decide`: `decide(text, candidates, policy)`, the `PARITY` and `Threshold` policies,
  and weighted interval scheduling for overlaps (architecture §11.3).
- The pipeline: a proposer step's edits go through `decide`; `clean(..., policy=PARITY)`;
  `Result.decisions()` and `Judgement`.
- `tests/legacy/`: a frozen copy of the v0.1 text rules, pipeline and profiles (ADR-0006), and
  `tests/test_parity.py`.

**Exit criteria**

| Criterion | Result | Evidence |
|---|---|---|
| Parity byte for byte, text and every located edit, every profile | pass | `tests/test_parity.py`: all 9 samples × 3 profiles × with and without a lexicon; the README example; 300 generated OCR-like texts (and the random profile) |
| Idempotence | pass | `tests/test_pipeline.py` (unchanged) |
| The v0.1 public API unchanged | pass | every v0.1 test unchanged and passing |

**Deviation from the plan.** The proposers propose only what their v0.1 rule applies: they wrap
the rules instead of re-implementing them, so parity holds by construction and the rules keep their
tests. Proposing what the v0.1 conditions decline (`v01 = 0`) moves to Phase 6, where the
evidence that could accept such candidates arrives.

**Results (measured):** `uv run pytest`: 1,476 passed (2026-11-23).

---

## Phase 4 — Evaluation harness

**Status:** COMPLETE (opened 2026-11-23 on `phase/04-eval-harness`, merged as #22).

**Implemented:** `lectris.eval` with `truth`, `matching`, `scoring`, `stats` and `experiment`
(architecture §13); `lectris experiment run CONFIG [-o reports]`.

**Exit criteria**

| Criterion | Result | Evidence |
|---|---|---|
| Scoring tested on hand-made pairs with known labels, including reading-order swaps and insertions | pass | `tests/test_eval.py`: a swap, a fix, a harm, neutral transforms and unwrapping, unmatched lines both ways, pages without boxes, the `none` policy, words |
| The bootstrap reproduces for a seed | pass | `TestBootstrap`, `test_the_report_is_the_same_on_every_run` |
| A dry-run experiment writes a report | pass | `TestExperiment.test_a_dry_run_writes_its_report` (three hand-made GLYPHARIS pages) |

**Changes to the protocol** (its §10): the edit label is the exact marginal effect on the block's
distance, not a token window; the raw track folds whitespace. No experiment had run.

**Not done here:** the layout metrics of protocol §3.4 (Kendall's τ, paragraph F1) and the
recall of correctable errors; both need paired data and come with Phase 10.

**Results (measured):** `uv run pytest`: 1,507 passed (2026-11-23).

---

## Phase 5 — Paired data

**Status:** COMPLETE (opened and closed 2026-11-23 on `phase/05-paired-data`; the owner approved
running GLYPHARIS on this machine overnight).

**Implemented**
- GLYPHARIS glypharis_v1 (the clean 1.0 install, PyTorch backend, CPU) run on all 1,724
  HierText validation images, its JSON in the git-ignored `data/engine/` (about 55 minutes).
- `scripts/build_hiertext_pairs.py`: ground truth per page (`lectris.eval.truth`, with GLYPHARIS's
  don't-care rule), page-level splits and manifests in `data/manifests/pairs/` (ids, paths,
  SHA-256 and the document-slice flag only).
- `scripts/error_taxonomy.py`: character errors split into in-token, spacing, missed-line and
  extra-line.
- `lectris.eval`: don't-care lines (`drop_dont_care`); the experiment report's edits by rule.
- LX-DATA-001, registered before it ran, on the fit split.

**Exit criteria**

| Criterion | Result | Evidence |
|---|---|---|
| Splits deterministic and disjoint by page | pass | `tests/test_scripts_pairs.py`; `data/manifests/pairs/hiertext_val_glypharis_v1.json`: fit 861, cal 430, dev 433 pages (document slice 52, 26, 27) |
| Audit written | pass | `reports/LX-DATA-001/report.md` |
| Share of errors inside one token measured | pass | `reports/LX-DATA-001/taxonomy.md`: 18.9% (all fit pages), 14.1% (document slice) |

**Results (measured, fit split; reports/LX-DATA-001):** uncorrected CER 28.03% [24.67, 32.66],
WER 44.40% [40.59, 49.49]. B1-standard ΔCER −0.00 [−0.04, +0.03] points, harm rate 0.041%; by
rule, see the report. 50.4% of errors are missed lines and 28.1% extra lines.

**Known issues**
- R-15: de-hyphenation and unwrapping scored as harm against HierText's line-level ground
  truth (`hyphenation.join` 3 fixes / 123 harms). Mitigated the same day by layout-neutral
  references (protocol §3.3); LX-DATA-002 re-runs the audit: B1-standard ΔCER −0.06
  [−0.10, −0.04] points, precision 89.71%, harm rate 0.013%.
- The GLYPHARIS install reports `glypharis_version` "0.1.0.dev0" for the glypharis_v1 model.
- The GLYPHARIS run on GlyphSynth validation (ADR-0005's auxiliary set) is not done: its
  validation data is line images, not pages, and needs the recognizer alone.
- Tesseract outputs (the transfer engine) are not built: Tesseract is not installed here.

**Results (tests):** `uv run pytest`: 1,522 passed (2026-11-23).

---

## Phase 6 — Evidence models and model packs

**Status:** COMPLETE (opened and closed 2026-11-23). Two pull requests: (1, #26) the models, the pack and
`lectris fit` (`phase/06-evidence-models`); (2) the evidence features and the new proposers.

**Part 1, implemented**
- `lectris.models.charlm`: a character n-gram model, interpolated modified Kneser-Ney, with
  pruning of the highest order's singletons; a property test checks that it is a distribution.
- `lectris.models.channel`: the engine's confusions over substrings of up to two characters,
  from aligned line pairs; the uniform-cost baseline.
- `lectris.models.pack`: fit, save (deterministic gzip JSON), load, `matches`; `PackError`.
- `lectris.eval.lines.matched_lines`; `Lexicon.counts`; `lectris fit`;
  `scripts/evaluate_pack.py`.

**Exit criteria (part 1; LX-FIT-001, registered before it ran)**

| Criterion | Result | Evidence |
|---|---|---|
| Language model perplexity on dev text reported | 12.478 per character [11.559, 13.464] | `reports/LX-FIT-001/report.md` |
| Channel log-likelihood on dev pairs better than uniform-cost Levenshtein | +0.2596 nats per intended character [0.2110, 0.3281] | same |
| Fit deterministic for its inputs | a second fit is the same file | same |
| The pack round-trips | pass | `tests/test_models.py` |

**Results (measured):** the pack fits in 10 s from the fit split's 26,317 line pairs and the first
3,000,000 characters of PG-19 train books (7 books in name order): 346,294 n-grams (order 5),
18,499 words, 973,373 bytes. GLYPHARIS's most frequent confusions are deletions: a space (1,123),
a full stop (373), single letters (`i` 310, `e` 289); then inserted spaces (619) and full stops
(342).

**Part 2, implemented**
- `lectris.evidence`: channel, language, lexicon, engine (through the composed `OffsetMap` to the
  lines a span came from), shape and rule features for every candidate.
- `lectris.propose`: `Lexical` (`lexical.word`) and `Segmentation` (`segmentation.split`,
  `segmentation.merge`), on a pack's word list.
- The pipeline: `clean(..., pack=...)` scores every candidate and runs the lexicon proposers as two
  final stages; their candidates are `v01 = 0`, so `PARITY` declines them and the text is v0.1's.
  On 40 fit pages, 1,076 candidates in 0.7 s, the text unchanged (a check, not a reported result).
- **Bug fixed:** the channel model's smoothing let an intended string never seen in training
  read as anything with probability 1. Fixed (smoothing over the model's observed forms), with
  tests. LX-FIT-001's channel numbers came from the faulty model; LX-FIT-002 re-runs it.

**LX-FIT-002 (the same criteria after the fix):** perplexity 12.478 [11.559, 13.464] (the
language model was not affected); channel minus uniform **+0.1539** nats per intended character
[0.1067, 0.2191] (LX-FIT-001, faulty: +0.2596); the second fit is the same file. The exit
criteria still hold.

**Deviation:** the v0.1 rules do not yet propose what their own conditions decline; the lexicon
proposers supply the `v01 = 0` candidates instead. `engine.alternatives` waits for glyphs.

---

## Phase 7 — Acceptance model and risk control

**Status:** COMPLETE (opened and closed 2026-11-23 on `phase/07-acceptance`).

**Implemented**
- `lectris.eval.scoring.label_candidates`: every candidate, accepted or not, with its exact
  marginal effect where it was proposed.
- `lectris.models.acceptance`: logistic regression with L2 by Newton's method (plain Python,
  deterministic); `calibration` (ECE over equal-mass bins, reliability, Brier).
- `lectris.models.risk`: Hoeffding-Bentkus p-values, fixed-sequence Learn-then-Test
  (`certified`, `learn_then_test`), the threshold grid.
- `lectris.eval.calibrate`: `calibrate` (acceptance on fit, thresholds on cal), `risk_policy`;
  packs carry `acceptance`, `risk` (`Budget`) and `calibration`; `lectris calibrate`.
- Experiments: systems can name a pack and the `risk` policy.
- ADR-0008 (budgets the calibration pages can certify) and ADR-0009 (the most useful certified
  threshold).

**Exit criteria**

| Criterion | Result | Evidence |
|---|---|---|
| On simulated data the realised risk exceeds α in at most δ of the repetitions | pass | `tests/test_acceptance_risk.py::TestLearnThenTest::test_the_guarantee_holds_in_simulation` (300 repetitions) |
| Calibration report on held-out candidates | ECE 0.0441, Brier 0.0630 on 12,857 cal candidates | `reports/LX-CAL-003/report.md` |
| Profiles defined | conservative 0.01, standard 0.02, aggressive 0.05 (δ 0.1); thresholds 0.51, 0.52, 0.52 | same; ADR-0008, ADR-0009 |

**The power check (LX-CAL-001, LX-CAL-002).** With ADR-0002's budgets, standard (0.005) and
conservative (0.001) got no threshold: 430 cal pages cannot certify a risk below 0.00534 even
with zero loss. ADR-0008 sets budgets above that limit. The most permissive certified thresholds
were then 0.33 / 0.2 / 0.06, where most accepted candidates are wrong; ADR-0009 uses the most
useful certified one instead.

**Validation on dev (LX-RISK-001, full runs, 433 pages; re-run with the scoring fix of Phase 13)**

| System | CER | ΔCER (points) | Harm rate (budget) | Fix / harm | Precision |
|---|---|---|---|---|---|
| uncorrected | 26.17% | — | — | — | — |
| B1-standard (v0.1) | 26.16% | −0.00 [−0.03, +0.04] | 0.078% | 60 / 51 | 54.05% |
| LX-conservative | 26.13% | −0.03 [−0.05, −0.02] | 0.017% (1%) | 112 / 36 | 75.68% |
| LX-standard | 26.13% | −0.03 [−0.07, +0.00] | 0.095% (2%) | 174 / 85 | 67.18% |

Every profile's dev harm rate is far below its budget, and precision rises from 54% (v0.1) to
67–76%. The CER gain is small and its interval reaches zero: on this data the corrector's ceiling
is the 18.9% of errors that lie inside a token.

**Known issues**
- The guarantee is loose (budgets of 1–5% against realised harm below 0.1%): more calibration
  pages would allow tighter budgets (ADR-0008).
- `noise.drop_lines` is much less precise on dev (46 fixes / 37 harms) than on fit
  (126 / 13); it needs features of its own (the noise score) for the acceptance model to judge it.

**Results (tests):** `uv run pytest`: 1,584 passed (2026-11-23).

---

## Phase 8 — Explanations, flags and the v0.3 interface

**Status:** COMPLETE (opened and closed 2026-11-23 on `phase/08-interface`).

**Implemented**
- `lectris.decide.Guarantee`; `Threshold.guarantee`; `ModelPack.policy(profile)` (the risk
  policy, with its guarantee; `lectris.eval.calibrate.risk_policy` delegates to it).
- `Result.guarantee`, `Result.guarantee_applies`, `Result.flags(threshold=0.3)` and `Flag`.
- Reports: the JSON holds the guarantee, every decision (rule, span, accepted, reason,
  probability, threshold, features) and the flags; the Markdown states the guarantee and lists
  the flags for review.
- `lectris clean --pack P [--policy parity|risk|none]`, with a warning when the guarantee does
  not apply to the input's engine.
- README ("With a model pack"), `docs/rules.md` (the new proposers and the evidence).

**Exit criteria**

| Criterion | Result | Evidence |
|---|---|---|
| Every accepted edit in a report shows its probability and features | pass | `tests/test_interface_v03.py::TestReports` |
| A mismatched engine is warned about | pass | `TestCleanCommand::test_another_engine_gets_a_warning`; `TestGuarantee` |

**Checked by hand:** `lectris clean` with the LX-CAL-003 pack on a dev page states the guarantee
("harm rate at most 0.02 with confidence 0.9, threshold 0.52 … applies") and lists for review
near-misses such as `Corference` → `Conference` (0.51).

**Results (tests):** `uv run pytest`: 1,598 passed (2026-11-23).

**v0.3 (the method, complete) is reached with this phase.** Not tagged or released: that is the
owner's call (docs/RELEASING.md).

---

## Phase 9 — Baselines (in progress)

- B0 (no correction, transforms only) and B1 (v0.1 rules, `parity`) run in every experiment.
- **B2, a lexicon corrector** (`lectris.eval.experiment.LEXICON`): each token not in the pack's
  lexicon becomes its most frequent word one edit away (`lexical.word`'s first candidate, marked
  by the new feature `lexical_rank`). Distance 1, not the protocol's 2 (deviation).
  LX-BASE-001 (dev): ΔCER +0.98 [+0.86, +1.10] points, 610 fixes / 2,686 harms, precision 18.51%,
  harm rate 1.410%, 78% of pages worse.
- **B3, ByT5-small** (LX-BASE-002; the research environment approved 2026-11-23,
  `research/baselines/byt5/`): it never beat copying on cal; on dev, every correction kept, ΔCER
  +1.08 [+0.44, +1.88] points at a 1.231% harm rate; harm-matched to LECTRIS-standard, LECTRIS
  lower by −0.04 [−0.08, −0.0005] points after the scoring fix of Phase 13 (−0.03 [−0.07, +0.01]
  before). H5 not supported as stated: B3 does not lower CER at all.
- B4 (an LLM) is not run: it would send data to a provider, which the protocol allows only for
  data whose licence permits it; HierText's terms were not checked for that.

## Phase 10 — Main study (in progress)

- **H3** (LX-RISK-002): 0 violations in 1,000 cal/dev re-splits for every profile; recall gap to
  the oracle 72.8% (standard). Partly supported (hypotheses.md).
- H1 has its first dev evidence (LX-RISK-001).
- **H2** (LX-ABL-001, Phase 11's first ablation): supported on dev for the line-level arm; the
  engine features add +0.03 [+0.02, +0.04] points of repaired characters at the same budget.
  `lectris calibrate --exclude` and paired `compare` in experiment configs make ablations.

## Phase 15 — Efficiency (in progress)

- **H6** (LX-EFF-001, 433 dev pages, this machine): LECTRIS-standard with the calibrated pack,
  median 0.0078 s per page (95th percentile 0.0223); GLYPHARIS, from its own log, 1.590 s; median
  per-page ratio 0.0050. Supported. Memory and the neural baselines' times are still to measure.

## Phase 12 — Engine transfer (in progress)

- Tesseract 5.4.0 (UB Mannheim build, `eng`) installed with the owner's approval; its hOCR for the
  1,724 HierText validation pages in `data/engine/hiertext_val/tesseract_5.4/`; pairs built with
  the same splits (`scripts/build_hiertext_pairs.py --suffix .hocr`); a Tesseract pack fitted and
  calibrated (thresholds 0.98 / 0.66 / 0.66).
- **H4** (LX-XFER-001): calibration transfers (ECE 0.0770 against 0.0400); the guarantee held even
  without recalibration (0 violations); recalibration keeps it (0 violations, ECE 0.0328 in-engine).
- Not done: the reverse transfer (a Tesseract pack on GLYPHARIS output).

## Phase 13 — Test evaluation

**Status:** COMPLETE (2026-11-23, on `phase/13-gdc-test`; the owner asked for the run). The test
was read twice: once as registered (LX-TEST-001), and once more as the registered re-run after a
scoring bug its report revealed (LX-TEST-002), as the phase's exit allows.

**Frozen:** LECTRIS code `8a1699c` (LX-TEST-001) and `e722231` (the fix, LX-TEST-002); the
calibrated pack (LX-CAL-003, SHA-256 `84674369…ab147b`) and the no-engine pack
(`794e008b…434794a`); GLYPHARIS glypharis_v1 (the clean 1.0 install, PyTorch on the CPU, 106
pages in about 12 minutes); GDC 1.1, the frozen file whose SHA-256 GLYPHARIS's GDC manifest
records. Pairs: `scripts/build_gdc_pairs.py`, GLYPHARIS's page-metric rule for lines that count
(8,372 lines count; 234 lines and 455 ignore regions are don't care); manifest
`data/manifests/pairs/gdc_v1_1_glypharis_v1_test.json`.

**The bug.** LX-TEST-001 showed LX-standard's labelled edits netting −0.03 points against B0
while its CER rose by 0.01. The layout-neutral reference (R-15) decided its own hyphen joins
under the system's policy; under `risk`, the acceptance model scored the ground truth's
candidates without the evidence it scores the OCR's with, and joined none, so each of LECTRIS's
102 joins on GDC (21 on dev) counted as an error. The reference now rejoins exactly where the
system rejoined (`lectris.eval.scoring`; a regression test). Calibration labels change for 1 of
12,857 cal candidates; the frozen pack was kept. The dev reports were re-run (LX-DATA-002,
LX-RISK-001, LX-ABL-001, LX-BASE-001, LX-BASE-002); LX-RISK-002 and LX-XFER-001 were not, since
they rest on the calibration labels.

**Results (LX-TEST-002, 106 GDC pages, 1,000 bootstrap resamples over pages)**

| System | CER | ΔCER vs uncorrected (points) | Harm rate (budget) | Fix / harm | Precision |
|---|---|---|---|---|---|
| uncorrected | 21.35% | — | — | — | — |
| B1-standard (v0.1) | 21.35% | −0.00 [−0.01, +0.00] | 0.004% | 12 / 10 | 54.55% |
| B2-lexicon | 22.06% | +0.71 [+0.57, +0.87] | 0.730% | 324 / 2,459 | 11.64% |
| LX-conservative | 21.32% | −0.02 [−0.04, −0.01] | 0.008% (1%) | 106 / 22 | 82.81% |
| LX-standard | 21.33% | −0.02 [−0.04, −0.01] | 0.012% (2%) | 115 / 28 | 80.42% |
| LX-standard-no-engine | 21.34% | −0.01 [−0.03, −0.00] | 0.012% (2%) | 89 / 23 | 79.46% |

Paired: LX-standard − B1-standard −0.02 [−0.03, −0.01] points; LX-standard − no-engine −0.01
[−0.02, −0.00], repaired +0.01 [+0.003, +0.013]. LX-aggressive equals LX-standard (ADR-0009's
thresholds). Error taxonomy (`reports/LX-TEST-001/taxonomy.md`): 23.0% of GDC's character errors
lie inside a token, 5.0% are spacing, 45.6% missed lines, 26.4% extra lines.

**Hypotheses:** H1 holds on GDC (partly supported overall: not CI-separated on dev); H2 confirmed
on GDC; H3's check on GDC passes for every profile (the recall gap not measured there). The
effects are small, bounded by the share of errors inside a token.

**Known issues:** the first run is kept and logged; numbers come from LX-TEST-002 only. Both
reads are logged in GLYPHARIS as well (DuhItzAniket/Glypharis#32).
