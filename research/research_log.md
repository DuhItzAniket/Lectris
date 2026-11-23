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

## 2026-11-23 — Layout-neutral references (R-15) and LX-DATA-002

- Mapping characters back through `OffsetMap` cannot separate layout from text: a de-hyphenation
  edit moves the second half of a word up a line, so its characters come from both lines. The
  robust fix is to build the reference the way the hypothesis is built: the block's ground-truth
  lines, joined by line breaks, go through the system's own layout steps under its policy.
  Line-break decisions are then neutral by construction; layout edits are labelled *layout*.
- LX-DATA-002 (fit split, same pairs and seed): B1-standard CER 27.97% against 28.03%
  uncorrected, ΔCER −0.06 [−0.10, −0.04] points, the first interval in this study that excludes
  zero. 157 fixes, 18 harms (precision 89.71%), harm rate 0.013% [0.001, 0.036]; 1.74% of pages
  made worse. By rule: `noise.drop_lines` 126 / 13 (−247 characters), `confusables.in_numbers`
  13 / 0 (−13), `punctuation.spacing` 18 / 5 (−13). B0 and B1-conservative change nothing but
  layout. The aggressive profile adds one fix and one harm (`confusables.in_words`).
- What this means for the study: the v0.1 rules are precise (≈ 90%) but reach little: about
  0.06 of the 28 CER points, against the 18.9% of errors (≈ 5.3 points) that lie inside a token
  (LX-DATA-001 taxonomy). The method's room is the gap between those two: recall at the same
  precision, which is what Phases 6 and 7 add.

## 2026-11-23 — LX-FIT-001: the evidence models

- The character model (order 5, modified Kneser-Ney, pruned) has a dev perplexity of 12.48 per
  character on HierText ground truth: scene text (signs, labels, numbers) is far less predictable
  than book prose, so the language evidence will be weaker here than on documents.
- The channel model beats a uniform-cost model by 0.26 nats per character [0.21, 0.33] on dev:
  GLYPHARIS's errors are far from uniform. They are mostly **deletions** (spaces, full stops,
  single letters), then inserted spaces and full stops, rather than the substitutions (`rn`/`m`,
  `0`/`O`) that classic OCR correction targets. Proposers for missing characters and spaces
  (Phase 6, part 2) matter more for this engine than confusion tables.

## 2026-11-23 — A channel smoothing bug, and LX-FIT-002

- A test of the evidence features found that the channel model gave an intended string never
  seen in training probability 1 for any reading: the denominator added `alpha` once per form
  seen *for that string*, which is zero for an unseen one. The smoothing now runs over all the
  observed forms the model knows (about 300 for GLYPHARIS), so an unseen string reads as each
  form with probability 1/K.
- LX-FIT-001's channel figure (+0.26 nats per character over uniform) came from the faulty model.
  LX-FIT-002, the same run after the fix: **+0.154 [0.107, 0.219]**. Smaller, still clearly
  above zero: the exit criterion holds. Both reports stay in the repository.
- The lexicon proposers produce many candidates on scene text (about 27 per page on 40 fit
  pages, most of them `lexical.word` on names and labels): the acceptance model of Phase 7 has to
  decline most of them, which is the case for risk control.

## 2026-11-23 — Phase 7: acceptance, risk control, and what it buys on dev

- **Acceptance.** A logistic model on 18,172 fit candidates (2,634 fixes) is well calibrated on
  12,857 cal candidates: ECE 0.044, Brier 0.063 (LX-CAL-003). The strongest evidence is the
  language model's change (weight +0.98, standardised), then the edit's size; the engine's line
  confidence and detection score both have negative weights (−0.25): the less sure the engine
  was, the likelier a correction is right. That is the engine-aware evidence H2 is about.
- **The power limit.** With 430 calibration pages, zero observed loss cannot rule out a risk
  above 1 − δ^(1/n) = 0.00534 (δ = 0.1). ADR-0002's budgets of 0.001 and 0.005 were below it, so
  no threshold could be certified (LX-CAL-001). ADR-0008 sets 0.01 / 0.02 / 0.05.
- **Certified is not useful.** The most permissive certified thresholds (0.33 / 0.2 / 0.06,
  LX-CAL-002) accept mostly wrong candidates while staying under budget. ADR-0009 picks, among
  the certified thresholds, the one with the best estimated CER change: 0.51–0.52, where expected
  gain turns positive. Fixed-sequence testing's family-wise control keeps the guarantee.
- **Dev (LX-RISK-001, full runs).** Every profile's harm rate is far below its budget (0.017%
  for α = 1%, 0.095% for α = 2%). Precision rises from 54% (v0.1 rules) to 68–76%, and the new
  `lexical.word` proposer contributes 100 fixes against 32 harms. But ΔCER is −0.03 [−0.06,
  +0.01] points: real, small, and not separated from zero. On HierText the corrector works on a
  ceiling of about 5 CER points (the in-token errors), and most of the 26 points are lost or
  invented lines.
- **For the paper:** the method does what it claims (bounded harm, higher precision), but
  HierText is the wrong showcase for its CER gains. The document-domain test (GDC, Phase 13)
  and a corpus where in-token errors dominate are where the gains should show; the error
  taxonomy should be reported next to every CER number.

## 2026-11-23 — H3 across 1,000 re-splits, and baseline B2

- **H3 (LX-RISK-002).** Pooling cal and dev (863 pages) and re-splitting them 1,000 times, the
  threshold certified and chosen on each calibration half never let the test half's harm exceed
  its budget: 0 violations per profile. The budgets are loose against the realised loss (the
  largest test loss was 0.002, against α = 0.01–0.05), which ADR-0008 already said: validity holds
  with a wide margin, and the price of the guarantee on this data is its looseness, not its
  failure. The recall gap to the "most permissive within budget" oracle is 73–80%, far above the
  25% the hypothesis named: that oracle maximises recall at any precision, and ADR-0009 chose not
  to. Reported as written.
- **B2 (LX-BASE-001).** A classic lexicon corrector, accepting each unknown word's most frequent
  neighbour, makes 610 fixes and 2,686 harms on dev (precision 18.51%), raises CER by 0.98
  points [+0.86, +1.10] and worsens 78% of pages. LECTRIS-standard draws on the same
  `lexical.word` candidates and accepts 100 fixes against 32 harms. **This is the paper's clearest
  result so far:** the same candidates, accepted by a calibrated probability under a harm
  budget, turn a corrector that damages text into one that does not.

## 2026-11-23 — H2: the engine's confidence helps the corrector (LX-ABL-001)

- The same pack calibrated without the engine features (`line_confidence`, `detection`,
  `engine_missing`) gets a stricter threshold (0.64 against 0.52) and repairs less: paired over
  the 433 dev pages, the engine-aware system repairs +0.03 points more of the reference's
  characters [+0.02, +0.04] and its CER is 0.02 points lower [−0.03, −0.01]; it breaks slightly
  more (+0.01 [+0.00, +0.01]), within the same budget. 174 fixes against 115.
- This is the link between the two projects in numbers: GLYPHARIS's calibrated line confidence,
  passed through its JSON, tells LECTRIS where corrections are likely to be right. H2 is
  supported on dev for the line-level arm; per-character confidences (`chars`, ADR-0003) are the
  next step, and need GLYPHARIS to export them.
