# ADR-0007: An integration release (v0.2) before the research phases

- **Status:** Accepted (2026-11-14, Phase 1)

## Context
GLYPHARIS v0.1 is released and its research phases are close to the end. The owner wants to test
the two together as soon as both are ready, and the research phases need data that only exists
once GLYPHARIS runs on the evaluation pages.

## Decision
1. **v0.2, integration-ready** (Phases 2–4): the GLYPHARIS reader and contract test, the
   uncertainty model, the propose/decide core with the `parity` policy, and the evaluation
   harness (edit scoring, line matching, bootstrap). No learned models yet.
2. The joint test runs GLYPHARIS v0.1 → LECTRIS v0.2 on a few pages, end to end, on the CLI and
   in Python.
3. The research phases (5 onwards) start once paired data can be produced. They use the
   GLYPHARIS v0.1 bundle for development and are re-run on the final GLYPHARIS model before
   anything is reported (ADR-0003, point 5).

## Consequences
- The integration does not wait for the learned components.
- Development numbers on GLYPHARIS v0.1 output are provisional and are not reported in the paper.

## Revisit if
GLYPHARIS's final model changes the output format; then the reader and fixture change first.
