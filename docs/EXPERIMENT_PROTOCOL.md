# Experiment protocol

How LECTRIS is fitted, evaluated and compared. A change to this protocol after an experiment it
governs has started is recorded in §10 with its date and reason.

## 1. Data roles and splits

Roles are fixed by [ADR-0005](decisions/ADR-0005-data-roles.md).

- **Pairs.** One pair per page: the engine's output file (GLYPHARIS JSON, Tesseract hOCR) and the
  page's ground truth as lines with polygons, from the dataset.
- **Splits.** HierText validation pages: fit 50%, cal 25%, dev 25%, by page, stratified by the
  document-slice flag, deterministic (SHA-256 of `page_id` + salt `lectris-v1`). Re-split seeds
  for validity and variance (§5): the salt plus the seed.
- **Leakage.** No page in two splits; the language model and word counts are fitted on PG-19 and
  the fit split only; dev and test never feed a pack.
- **Manifests.** Every split has a manifest: page ids, counts, hashes of the pair files, engine
  and model version. Committed; the data is not.

## 2. Text normalisation tracks

So that normalisation is not credited as correction, every CER/WER is reported in two tracks:
- **Raw:** ground truth and output compared as they are, in NFC, with each whitespace run
  one space (line breaks are layout, not text).
- **Normalised:** both sides through LECTRIS's transforms (Unicode, whitespace, dashes, quotes)
  before comparison. **This is the primary track**: it measures what the proposers and the
  decision layer did, not the transforms.

## 3. Metrics

### 3.1 Recognition quality
- Page CER and WER after line matching (§3.3), micro-averaged over characters and macro over pages.
- Change against the uncorrected output: ΔCER (points), relative CER reduction.

### 3.2 Edit quality
- Each accepted edit is scored by its exact marginal effect: Δ = distance(block reference, the
  block's text at the edit's step with the edit applied) − distance(block reference, that text
  without it), in the normalised track, where a block's reference is the ground truth of its
  matched lines (§3.3), laid out as the system lays out its text. **Fix**: Δ < 0. **Harm**:
  Δ > 0. **Neutral**: Δ = 0. **Layout**: any edit of a layout rule, whatever its Δ.
- **Harm rate** (the guaranteed risk): per page, Σ Δ over harmful edits / max(1, |ground truth|).
- **Precision**: fixes / (fixes + harms). **Recall**: characters fixed / characters in
  locally correctable errors (errors inside one token or one inter-token gap of a matched line).
- **Pages worsened**: share of pages whose CER rises.
- **Label check**: 200 edits sampled from dev, labelled by hand, agreement with the automatic label
  reported.

### 3.3 Line matching
OCR lines are matched to ground-truth lines one to one by the IoU of their boxes (greedy by IoU,
threshold 0.5 _(tunable)_). Unmatched OCR lines are insertions, unmatched ground-truth lines are
deletions; both count in CER but are outside any edit's window (they are not locally correctable).

**Layout-neutral references.** Line-level ground truth keeps each printed line's end, line-end
hyphens included. A block's reference is its matched ground-truth lines joined by line breaks;
the cleaned text is compared with that reference *after* the system's own layout steps
(`hyphenation.join`, `unwrap.join_lines`, in the profile's order, under the system's policy), and
the uncorrected text with the reference as it is. Line-break decisions are then the same on both
sides; layout edits are labelled *layout* and scored apart (they need reading-text ground truth).
Where the OCR text near a line end differs from the ground truth, the two sides can decide
differently, and that counts (R-15).

**Don't care.** As in GLYPHARIS's page metrics, a ground-truth line counts only if it is legible,
printed (not handwritten), horizontal (not vertical) and not empty; every other line is *don't
care*. Before cleaning, an OCR line that matches no line that counts, but matches a don't-care
line or lies half or more inside one, is dropped (`lectris.eval.scoring.drop_dont_care`; lines
that count are matched first). A don't-care line is never a deletion.

### 3.4 Layout (secondary)
Reading order: Kendall's τ between the order of matched lines and the ground truth's order, for
the engine's order and for LECTRIS's layout. Paragraph grouping: pairwise F1 over lines of the same
block, where the ground truth has paragraphs.

### 3.5 Calibration
ECE (15 equal-mass bins) and reliability curves for p(correct) on dev candidates; Brier score.

### 3.6 Efficiency
CPU time per page (median and p95 over dev, 3 warm runs, one process, the laptop's CPU), peak
memory, pack size. Neural baselines on CPU and GPU, reported apart.

## 4. Statistics

- Paired bootstrap over pages, 1,000 resamples, 95% percentile CI, seed 1337.
- **Better**: the CI of the difference excludes zero. Otherwise: no clear difference.
- Multiple comparisons: the headline comparisons are the ones in the hypotheses; everything else
  is exploratory and labelled so.

## 5. Risk-control validity

- **Re-splits.** 1,000 random re-splits of the cal ∪ dev pages into cal and dev of the same sizes:
  fit λ̂ on cal, measure the harm rate on dev. Validity holds if the share of re-splits with
  dev harm rate > α is at most δ (plus its binomial 95% upper bound reported).
- **Oracle.** The most permissive λ whose dev harm rate is ≤ α, chosen on dev itself: the recall
  the guarantee costs is the recall gap to it.
- **Transfer.** The same measures with cal from one engine or set and dev from another (Phase 12,
  13). Here validity is not promised; it is measured.

## 6. Baselines

| ID | System | Settings |
|---|---|---|
| B0 | no correction (transforms only) | — |
| B1 | LECTRIS v0.1 rules (`parity`) | each profile |
| B2 | lexicon corrector | out-of-lexicon tokens replaced by the most frequent word within OCR-weighted distance ≤ 2 |
| B3 | ByT5-small, fine-tuned (research environment) | fit split pairs, line level; budget recorded; harm-matched by thresholding its sequence probability where possible |
| B4 | LLM zero-shot (optional) | prompt fixed in advance; only data whose licence allows sending it to a provider; the provider and model version recorded |

All baselines are scored by the same code (`lectris.eval`) on the same pairs.

## 7. Reports

Every experiment writes `reports/<ID>/report.md` and `report.json`: config, code commit, pack hash,
manifest hashes, all metrics with CIs, run time. Reports hold aggregates only. Examples of text in
the repository come from original or synthetic data (ground rule 5).

## 8. Test-access rules

- GDC and the external sets are read only in Phase 13, once per frozen configuration, logged in
  [research/test_access_log.md](../research/test_access_log.md) and in GLYPHARIS's log for GDC.
- A bug found after a test run is fixed, the whole test is re-run, and both runs are reported.

## 9. Reproducibility

Commands, seeds, code commit and manifests are enough to regenerate every report. Packs are
deterministic for their inputs. Run time is the only number that may differ between machines.

## 10. Protocol change log

| Date | Change | Reason | Affects |
|---|---|---|---|
| 2026-11-14 | first version | Phase 1 | — |
| 2026-11-23 | §3.2: an edit's Δ is its exact marginal effect on its block's distance to the block's reference, not a distance in a token window | a window needs a choice of its edges and an alignment that can be ambiguous; the block is small enough to measure exactly (Phase 4) | every edit label; no experiment had run |
| 2026-11-23 | §3.2, §3.3: layout-neutral references; layout edits labelled *layout* and left out of fixes, harms and the harm rate | LX-DATA-001 showed correct de-hyphenations scored as harm against line-level ground truth (R-15) | every score with layout steps; only the descriptive LX-DATA-001 had run, and it is re-run as LX-DATA-002 |
| 2026-11-23 | §3.3: don't-care ground-truth lines (illegible, handwritten, vertical, empty), and OCR lines on them dropped before cleaning | the same rule as GLYPHARIS's page metrics, so the two projects score one page alike (Phase 5) | every page score; no experiment had run |
| 2026-11-23 | §2: the raw track folds whitespace runs to one space | line breaks and unwrapping are layout, which §3.4 scores apart (Phase 4) | raw CER; no experiment had run |
| 2026-11-23 | §3.3: a layout-neutral reference rejoins hyphenated words exactly where the system rejoined them; the policy is no longer asked again on the ground truth | a bug: under `risk`, the acceptance model decided the reference's joins without the evidence it scores the OCR with, so LECTRIS's joins were charged as errors (found in LX-TEST-001; on dev, 21 joins against 0) | every score of a system whose `hyphenation.join` decisions are policy-dependent; LX-TEST-001 re-run as LX-TEST-002; the dev reports re-run (research/experiments.md); calibration labels change for 1 of 12,857 cal candidates |
