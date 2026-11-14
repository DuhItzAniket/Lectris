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
