# ADR-0008: Risk budgets follow what the calibration pages can certify

- **Status:** Accepted (2026-11-23, Phase 7). Supersedes the default budgets in ADR-0002, point 3;
  the rest of ADR-0002 stands.

## Context
ADR-0002 set the profiles' harm-rate budgets to α = 0.001, 0.005 and 0.02 (δ = 0.1), marked
tunable, and asked for a power check in Phase 7. LX-CAL-001 ran it on the 430 cal pages:

- the standard and conservative profiles got no threshold at all. At the strictest threshold
  (nothing accepted, every page's loss exactly 0) the Hoeffding-Bentkus p-value for α = 0.005 is
  0.65, above δ;
- this is not a weakness of the bound. A page's loss can be as large as 1, so zero loss on n
  pages cannot rule out a risk above 1 − δ^(1/n): **0.00534** for n = 430 and δ = 0.1. Every
  valid procedure has this limit; a budget below it can never be met;
- the estimated loss itself is small: 0.00069 at threshold 0.5 on cal (LX-CAL-001).

## Decision
1. The profiles' budgets are **conservative α = 0.01, standard α = 0.02, aggressive α = 0.05**,
   δ = 0.1, about 2, 4 and 9 times the smallest budget 430 calibration pages can certify.
2. A calibration report states the smallest certifiable α for its page count next to each budget
   (`scripts/report_calibration.py`).
3. The paper reports the guarantee (α) and the realised harm side by side: the guarantee is an
   upper bound and is expected to sit well above the harm measured.

## Consequences
- Every profile gets a threshold on this calibration set, so the risk policy is usable.
- The guarantee is loose: a budget of 1–5% of characters is far above the harm the v0.1 rules do
  (0.013%, LX-DATA-002). Tighter budgets need more calibration pages: about 2,300 for α = 0.001.
- The profiles' names keep their order (conservative accepts least), not their v0.1 meaning.

## Alternatives considered
- **A variance-adaptive bound (Waudby-Smith–Ramdas betting).** Tighter when losses are small and
  observed, but it cannot beat the zero-loss limit above; it may be added later for the budgets
  that are above the limit.
- **A larger δ.** δ = 0.2 lowers the limit only to 0.0037, and weakens the guarantee.
- **Calibrating on the fit pages too.** The acceptance model is fitted on them; its losses there
  are optimistic, so the guarantee would not hold.
- **Bounding a page's loss below 1.** No such bound holds for every policy (a noise-line deletion
  can remove most of a page).

## Revisit if
More calibration pages become available (a second engine's pairs, more HierText-like pages),
or the loss is redefined on a unit with a natural bound below 1.
