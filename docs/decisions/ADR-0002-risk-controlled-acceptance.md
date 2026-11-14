# ADR-0002: Acceptance threshold by Learn-then-Test, guaranteeing a harm rate

- **Status:** Accepted (2026-11-14, Phase 1)

## Context
"Precision before recall" is a habit in v0.1. To be a property, a profile needs a number that is
held on unseen data with a stated confidence. Post-OCR correction is usually reported as an
average CER reduction, which hides the pages it damages.

## Decision
1. The controlled quantity is the **harm rate**: per page, the characters broken by accepted
   harmful edits divided by the ground truth's length (bounded in [0, 1]); its expectation over
   pages is the risk R(λ).
2. The acceptance threshold λ̂ is chosen on a calibration split of whole pages by Learn-then-Test
   (fixed-sequence testing over a grid from strict to permissive, Hoeffding–Bentkus p-values), so
   that P(R(λ̂) ≤ α) ≥ 1 − δ for exchangeable test pages.
3. A profile is a risk budget (α, δ). Defaults _(tunable)_: conservative 0.001, standard 0.005,
   aggressive 0.02; δ = 0.1.
4. Precision, recall and the fraction of pages made worse are reported, not guaranteed.
5. Pages are the statistical unit everywhere (fitting splits, calibration, bootstrap), because
   edits on one page share a font, a scan and an engine state.

## Consequences
- The guarantee is distribution-free but needs exchangeability: the same engine and model, and
  the same kind of document. Engine transfer (RQ4) and the GDC test (Phase 13) measure how far it
  holds outside that.
- With few calibration pages the bound is loose and λ̂ is strict; the plan needs at least
  _(tunable)_ 500 calibration pages for the standard budget, to be confirmed by a power check in
  Phase 7.
- The harm label depends on alignment with the ground truth (protocol §3.2). Alignment errors are
  measured on a hand-checked sample.

## Alternatives considered
- **Control precision of accepted edits.** Precision is a ratio of two random counts, so it does
  not fit the bounded-mean risk this method needs, and edits are dependent within a page.
- **Split conformal prediction per edit.** Gives marginal coverage per candidate, which is not
  what an archive needs.
- **A fixed threshold tuned for best CER.** No guarantee; kept as the `threshold` policy for
  sweeps.

## Revisit if
Calibration data is too small for useful thresholds, or the harm label proves unreliable.
