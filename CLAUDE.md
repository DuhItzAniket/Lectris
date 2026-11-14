# LECTRIS

OCR output, read back into clean, ordered text: every change it makes is recorded and explained.
A Python library and CLI, and a research project with a paper as its goal. The design is
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); read it before changing code. Its sections are
marked [v0.1] (built) or [v2, Phase N] (planned). The phases are in
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), their status in
[docs/PHASE_STATUS.md](docs/PHASE_STATUS.md), the decisions in [docs/decisions/](docs/decisions/).
The companion OCR engine is GLYPHARIS; the two meet only through its JSON output (ADR-0003).

## Ground rules

1. **No silent edits.** Every text change is an `Edit` from a named rule. Never change text
   outside a rule, and never return a changed text without its edits.
2. **Precision before recall.** A rule changes text only on strong local evidence. Every rule has
   tests for what it must leave alone; add one for each new false positive you find.
3. **The rule contract** (architecture, "Text rules") holds for every rule: offsets in the input,
   sorted non-overlapping edits, `apply_edits` reproduces the output, idempotent unless stated.
4. **Standard library only** at runtime. Ask the owner before adding a dependency.
5. **Original test data only.** No third-party scans, OCR output or documents in the repository.
6. **Public repository: no personal or sensitive data.** No secrets, tokens, personal names or
   emails, or home-directory paths in code, docs, test data or commit metadata. Commits use the
   GitHub noreply address.

## Commands

```
uv sync                         # the environment, with the dev group
uv run pytest                   # the tests (Hypothesis derandomised; HYPOTHESIS_PROFILE=explore to search)
uv run ruff check               # lint
uv run ruff format              # format (--check in CI)
uv run mypy                     # strict types over src and tests
uv run lectris clean <file>     # the CLI: clean, eval, rules
uv build                        # sdist and wheel
```

## Workflow

- One change per branch and pull request; CI must be green before merging (squash merges).
- Every pull request is checked by Repro (`.github/workflows/repro.yml`). Describe what the
  change does to the output: Repro compares that description with what the changed functions
  actually return on the base and the head.
- Update `CHANGELOG.md` under `Unreleased` for anything a user would notice.

## Research discipline

- **Parity.** Under the `parity` policy, output must stay byte for byte that of v0.1 (ADR-0006).
- **Pre-registration.** Hypotheses (`research/hypotheses.md`) and experiments
  (`research/experiments.md`) are written before they run; a hypothesis is never edited after its
  experiment starts.
- **Numbers come from generated reports only**, never typed by hand or estimated.
- **Test sets** (GDC, external) are read only in Phase 13 and every read is logged in
  `research/test_access_log.md` (and in GLYPHARIS's log for GDC).
- **The page is the unit** for splits, bootstrap and the risk guarantee.
- A phase closes through the gate in the implementation plan (§2), with its PHASE_STATUS entry.
