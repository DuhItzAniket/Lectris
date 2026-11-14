# ADR-0006: v0.1 is the rule baseline and must be reproduced byte for byte

- **Status:** Accepted (2026-11-14, Phase 1)

## Context
v0.1 is released, tested (1,270 tests) and correct by its own standard. The v2 refactor touches
every repair rule. A refactor that silently changes behaviour would break users and would make
the "rule baseline" in the paper a moving target.

## Decision
1. The `parity` policy (architecture §11.4) accepts exactly the candidates the v0.1 rules applied.
2. **Phase 3 exit:** with `parity`, `clean()` returns the same text and the same edits as v0.1
   for every profile, on the whole test suite and on a fixed corpus of generated inputs (a
   Hypothesis strategy over OCR-like text, plus every test fixture). A test runs v0.1's
   functions, kept frozen in `tests/legacy/`, against v2.
3. Without a model pack, `parity` is the default, so v0.1 users see no change.
4. In the paper, `parity` is the system "LECTRIS rules (v0.1)".

## Consequences
- The refactor can land in small pull requests, each one checked by the parity test and by Repro.
- `tests/legacy/` is a frozen copy of the v0.1 rule code; it is deleted at v1.0 together with
  the policy's test, or kept if the baseline is still reported.

## Revisit if
A v0.1 behaviour turns out to be a bug: then it is fixed in both, with a CHANGELOG line, and the
parity corpus is updated in the same pull request.
