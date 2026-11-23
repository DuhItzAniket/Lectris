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
| 5 | Paired data | **COMPLETE** (in review) | — |
| 6 | Evidence models and model packs | not started | — |
| 7 | Acceptance model and risk control | not started | — |
| 8 | Explanations, flags and the v0.3 interface | not started | — |
| 9 | Baselines | not started | — |
| 10 | Main study (dev) | not started | — |
| 11 | Ablations | not started | — |
| 12 | Engine transfer | not started | — |
| 13 | Test evaluation | not started | — |
| 14 | Error analysis | not started | — |
| 15 | Efficiency | not started | — |
| 16 | Research package | not started | — |
| 17 | Release v1.0 | not started | — |

## Open items for the owner

| Item | Needed by | Status |
|---|---|---|
| Review the v2 architecture and the research framing (ADR-0001, 0002) | Phase 2 | open |
| Approve or decline the research environment for neural baselines (ADR-0004, point 3) | Phase 9 | open |
| Decide whether GLYPHARIS exports per-character `chars` (ADR-0003); GLYPHARIS 1.0 does not | Phase 6 (RQ2 character arm) | open |
| GLYPHARIS v1.1 installable on Python 3.12+ (1.0 pins `<3.12`, LECTRIS needs `>=3.12`); the CLI handoff through JSON works across two environments meanwhile | joint Python use | open (GLYPHARIS side) |
| GLYPHARIS output (JSON) on HierText validation and GlyphSynth validation pages, with the model version | Phase 5 | open |
| Tesseract installed, its version, for the transfer engine | Phase 5 | open |
| Target venue (journal or conference) and its page limit | Phase 16 | open |
| PyPI: a pending publisher for `lectris` and the protected `pypi` environment (docs/RELEASING.md); the release workflow is merged (#23) | first PyPI release | open |

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
- R-15 (new): de-hyphenation and unwrapping score as harm against HierText's line-level ground
  truth (`hyphenation.join` 3 fixes / 123 harms). The scoring needs a layout-neutral track before
  any hypothesis is tested (research log, 2026-11-23).
- The GLYPHARIS install reports `glypharis_version` "0.1.0.dev0" for the glypharis_v1 model.
- The GLYPHARIS run on GlyphSynth validation (ADR-0005's auxiliary set) is not done: its
  validation data is line images, not pages, and needs the recognizer alone.
- Tesseract outputs (the transfer engine) are not built: Tesseract is not installed here.

**Results (tests):** `uv run pytest`: 1,522 passed (2026-11-23).
