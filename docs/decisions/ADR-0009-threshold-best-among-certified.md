# ADR-0009: The threshold is the most useful of those the test certifies

- **Status:** Accepted (2026-11-23, Phase 7). Refines architecture §11.2 (which took the most
  permissive certified threshold); ADR-0002's guarantee is unchanged.

## Context
Learn-then-Test walks thresholds from strict to permissive and certifies, with fixed-sequence
testing, every threshold before the first null it cannot reject. Architecture §11.2 took the most
permissive of them, which maximises recall under the harm budget. LX-CAL-002 shows the problem:
with budgets of 1–5% (ADR-0008) the most permissive certified thresholds are 0.33, 0.2 and 0.06,
where most accepted candidates are wrong (the reliability bins near 0.2 have about 15% fixes).
Staying under a harm budget is not the same as improving the text: such a threshold can make CER
worse while keeping its promise.

## Decision
1. Learn-then-Test returns the whole certified set (every threshold rejected before the first
   failure), not only its most permissive member.
2. The threshold used is the one in that set with the **largest estimated CER reduction** on the
   calibration pages: the sum of the accepted candidates' effects, the most negative; on a tie,
   the strictest (highest).
3. The pack records both: `threshold` (used) and `permissive` (the most permissive certified).

## Why the guarantee holds
Fixed-sequence testing controls the family-wise error rate at δ: with probability at least
1 − δ, every certified threshold has risk at most α. A choice made among the certified thresholds,
by any rule, including one that looks at the calibration data, is then a threshold whose risk is
at most α with that same probability.

## Consequences
- The policy accepts a candidate only where, on the calibration pages, accepting at that level
  helped more than it hurt, and never beyond the harm budget.
- The utility estimate uses each candidate's effect where `PARITY` proposed it, the same
  approximation as the loss (architecture §11.2); the realised effect is measured on dev.

## Revisit if
A profile should trade CER for recall (a search index that prefers a fix it can verify later):
then a different utility can choose within the same certified set.
