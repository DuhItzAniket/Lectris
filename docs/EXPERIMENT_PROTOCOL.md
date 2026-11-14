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
- **Raw:** ground truth and output compared as they are (NFC only).
- **Normalised:** both sides through LECTRIS's transforms (Unicode, whitespace, dashes, quotes)
  before comparison. **This is the primary track**: it measures what the proposers and the
  decision layer did, not the transforms.

## 3. Metrics

### 3.1 Recognition quality
- Page CER and WER after line matching (§3.3), micro-averaged over characters and macro over pages.
- Change against the uncorrected output: ΔCER (points), relative CER reduction.

### 3.2 Edit quality
- Each accepted edit is aligned to the ground truth: the OCR line and its matched ground-truth line
  are aligned (Levenshtein with backtrace), and the edit's window is its span extended to token
  boundaries. Δ = distance(window after) − distance(window before).
  **Fix**: Δ < 0. **Harm**: Δ > 0. **Neutral**: Δ = 0.
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
