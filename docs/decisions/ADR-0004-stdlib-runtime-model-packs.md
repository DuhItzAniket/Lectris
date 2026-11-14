# ADR-0004: Standard library at run time; learned models as data packs; neural baselines isolated

- **Status:** Accepted for the run time (2026-11-14, Phase 1). **Proposed** for the research
  environment (point 3), which adds dependencies outside the package and needs the owner's
  approval (ground rule 4).

## Context
LECTRIS has no runtime dependencies, and that is part of its value: it installs anywhere, next to
any engine. The research plan needs learned components and, for a fair comparison, a neural
post-correction baseline.

## Decision
1. **Run time: standard library only**, as in v0.1. Every learned component is a small
   statistical model whose inference is plain Python: a character n-gram language model, a
   confusion (channel) model, word counts, a logistic regression.
2. **Learned parameters are data**: a versioned model pack (JSON, gzip) with a manifest of the data
   it was fitted on (architecture §12). Fitting (`lectris fit`) is standard library too, so the
   whole method reproduces with LECTRIS alone.
3. **Neural baselines** (ByT5-small fine-tuned on the fit split; an optional LLM zero-shot
   corrector) live in `research/baselines/` with their own locked environment (`torch`,
   `transformers`), outside the package and its CI. They read and write the same JSON as LECTRIS
   and are scored by `lectris.eval`. Nothing in `src/` imports them.

## Consequences
- The package's `dependencies = []` is unchanged.
- Fitting a 6-gram model in pure Python is slower than with numpy; corpus size is capped
  _(tunable)_ and pruning is part of the fit. Measured in Phase 6.
- The baselines use the GPU (RTX 4050) and will compete with GLYPHARIS training for it; they run
  after GLYPHARIS training ends.

## Alternatives considered
- **numpy at run time.** Faster fitting; breaks the zero-dependency promise for a speed gain only
  fitting needs.
- **No neural baseline.** Cheaper, but a reviewer will ask how the method compares with
  sequence-to-sequence correction.

## Revisit if
Fitting time in pure Python exceeds _(tunable)_ one hour on the fit split, or the owner declines
the research environment (then the baselines are dropped and the paper states it).
