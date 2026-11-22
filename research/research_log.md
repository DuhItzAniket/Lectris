# Research log

Dated notes: what was tried, what was learned, what changed. Newest last.

## 2026-11-14 — Phase 1 opened

- v0.1 is a working rule engine (1,270 tests pass) but not a research method: each rule decides
  alone, nothing is calibrated, and there is no claim to test beyond "the rules help".
- Reframed as **propose → evidence → decide**, with the decision threshold chosen by
  Learn-then-Test so that the expected harm rate is bounded (ADR-0001, 0002). "Precision before
  recall" becomes a measurable guarantee.
- The link with GLYPHARIS becomes part of the method: engine uncertainty as evidence (ADR-0003).
  Today GLYPHARIS exports line confidence and detector score; per-character alternatives would
  need a small export change there.
- Decision to keep the run time on the standard library: learned parts are n-gram, channel and
  logistic models stored as packs (ADR-0004).
- Open: verify novelty (R-03); confirm the research environment for the neural baseline.

## 2026-11-23 — LX-DATA-001: what GLYPHARIS's errors on HierText are made of

GLYPHARIS glypharis_v1 on the 861 fit pages (reports/LX-DATA-001). Descriptive; no hypothesis
tested.

- **Uncorrected:** CER 28.03% [24.67, 32.66], WER 44.40% (normalised track). 26,317 of 37,322
  ground-truth lines that count are matched (IoU ≥ 0.5) by 30,901 OCR lines.
- **Most errors are not locally correctable.** Of all character errors, 50.4% are missed lines
  and 28.1% extra lines (detection), 2.6% spacing, and only **18.9% lie inside a token**: the
  upper bound for a local corrector. On the document slice (52 pages) the share in a token is
  14.1% and CER 49.16%. R-01 has materialised: on HierText, any corrector's ceiling is small.
- **The v0.1 rules' real repairs work; the measurement penalises layout.** By rule (B1-standard):
  `noise.drop_lines` 126 fixes / 13 harms (net −247 characters), `confusables.in_numbers` 13 / 0
  (−13), `punctuation.spacing` 18 / 5 (−13). But `hyphenation.join` scores 3 / 123 (+240) and
  `unwrap.join_lines` 8 / 26 (+18; 11 / 149 under B0): HierText transcribes each printed line,
  line-end hyphens included, so rejoining a hyphenated word counts as a harm against a reference
  that keeps "spr- ing". Net, ΔCER of B1-standard is −0.00 [−0.04, +0.03] points.
- **Consequence for the protocol (before any hypothesis is tested):** text corrections and layout
  operations must be scored apart. A layout-neutral track is needed in which line boundaries are
  treated alike on the hypothesis and the reference (hyphen-and-break zones mapped through
  `OffsetMap`), so that de-hyphenation and unwrapping are neutral there and are evaluated, if at
  all, on data with reading-text ground truth. Recorded as R-15; to design and register before
  Phase 10, with the owner.
- GLYPHARIS's installed package reports `glypharis_version` "0.1.0.dev0" while its model is
  glypharis_v1; the pairs are keyed by the model, as ADR-0003 requires.
