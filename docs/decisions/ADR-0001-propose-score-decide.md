# ADR-0001: Rules propose, evidence scores, one decision layer accepts

- **Status:** Accepted (2026-11-14, Phase 1)

## Context
In v0.1 each repair rule decides alone, with its own hand-set conditions (`confusables.in_numbers`
needs a digit on both sides; `hyphenation.join` asks the lexicon). That works and is safe, but:
- decisions cannot use evidence the rule does not know about (the engine's confidence, what this
  engine confuses);
- there is no common scale, so the precision of one rule cannot be traded against the recall of
  another;
- there is nothing to calibrate or guarantee, and nothing to study: a paper can report the rules'
  effect, not a method.

## Decision
1. Split rules into **transforms** (no guess: Unicode, whitespace, unwrapping, punctuation style),
   which apply as in v0.1, and **proposers** (a guess: confusions, separators, punctuation spacing,
   hyphenation, noise lines and the new proposers), which return `Candidate`s.
2. One evidence layer (`lectris.evidence`) computes features for every candidate, whatever rule
   proposed it.
3. One decision layer (`lectris.decide`) accepts or declines, resolves overlaps and records a
   `Decision` for each candidate.
4. Profiles keep v0.1's stage order, so later stages see earlier stages' output.

## Consequences
- The edit contract and the v0.1 rule tests stay valid: an accepted candidate is an `Edit`.
- New evidence (a better language model, character alternatives) improves every rule at once.
- Declined candidates become review flags at no extra cost.
- Cost: a refactor of six rule modules, guarded by the parity policy (ADR-0006).

## Alternatives considered
- **Keep per-rule decisions and add a confidence gate.** Simple, but each rule would still need
  its own threshold and there would be no joint guarantee.
- **One sequence-to-sequence model** (ByT5 or an LLM). Strong recall, but no span-level
  provenance, possible hallucination, and dependencies at run time. It is kept as a baseline
  (protocol §6).

## Revisit if
The decision layer cannot match the parity output, or a single model is shown to beat the
decision layer at equal harm (H5).
