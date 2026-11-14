# Hypotheses

Written **before** the experiments that test them. A hypothesis is never edited after its
experiment starts; if it needs to change, add a new one and mark the old one superseded. Outcomes
are filled in from generated reports, with experiment IDs.

Status values: `open` → `testing` → `supported` | `not supported` | `inconclusive` | `superseded`.
"Better" follows the protocol (§4): the 95% paired-bootstrap CI over pages excludes zero. Numbers
are on the normalised track (protocol §2), GLYPHARIS output, dev split, document slice, unless
stated.

---

### H1 — Risk-controlled correction helps without breaking text (RQ1)

- **Statement:** The `standard` profile (risk policy, α = 0.005) lowers CER against no correction
  (B0), keeps the dev harm rate at or below α, and lowers CER at least as much as the v0.1 rules
  (B1) at equal or lower harm.
- **Test:** Phase 10 (LX-MAIN-*); confirmed once on GDC in Phase 13.
- **Success criterion:** ΔCER vs B0 CI-separated below zero; dev harm rate ≤ α; ΔCER vs B1 ≤ 0
  (CI-separated, or no clear difference with lower harm).
- **Status:** open.

### H2 — Engine uncertainty raises recall at the same budget (RQ2)

- **Statement:** At the same α, evidence with engine features (line confidence, detector score,
  and character alternatives where available) fixes more correctable errors than the same model
  without engine features.
- **Test:** Phase 11 (LX-ABL-*).
- **Success criterion:** recall difference CI-separated above zero at α = 0.005; reported apart for
  the line-level and the character-level arms.
- **Status:** open.

### H3 — The guarantee holds in distribution (RQ3)

- **Statement:** Over 1,000 random cal/dev re-splits, the dev harm rate exceeds α in at most δ of
  them, for each profile; the recall cost against the oracle threshold is under _(tunable)_ 25%
  relative at α = 0.005.
- **Test:** Phase 10 (LX-RISK-*).
- **Success criterion:** violation share ≤ δ (its binomial upper bound reported); recall gap
  measured.
- **Status:** open.

### H4 — Calibration transfers across engines, the guarantee does not (RQ4)

- **Statement:** A pack fitted on GLYPHARIS output, applied to Tesseract output, has an ECE within
  2× its in-engine ECE, but its harm-rate guarantee is violated more often than δ; refitting the
  calibration on the new engine restores validity.
- **Test:** Phase 12 (LX-XFER-*).
- **Success criterion:** each of the three parts decided separately.
- **Status:** open.

### H5 — Against neural correction at matched harm (RQ1)

- **Statement:** A fine-tuned ByT5-small (B3) lowers CER more than LECTRIS `aggressive`, but at a
  higher harm rate; at matched harm, LECTRIS lowers CER at least as much.
- **Test:** Phase 10 (LX-BASE-*, LX-MAIN-*), if B3 is approved (ADR-0004).
- **Success criterion:** each part CI-separated; "inconclusive" if B3 cannot be harm-matched.
- **Status:** open.

### H6 — Correction is cheap next to recognition (RQ6)

- **Statement:** LECTRIS `standard` with a pack needs at most 10% of GLYPHARIS's CPU time per page
  on the same machine (median over dev).
- **Test:** Phase 15 (LX-EFF-*).
- **Status:** open.
