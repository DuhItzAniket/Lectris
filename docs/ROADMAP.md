# Roadmap

Milestones, the order of the phases, and where LECTRIS and GLYPHARIS meet. The phases are in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Milestones

| Version | Contents | Phases | Depends on |
|---|---|---|---|
| v0.1.0 ✅ | rule engine, five readers, layout, metrics | 0 | — |
| v0.2.0 | **integration-ready**: GLYPHARIS reader and contract, uncertainty model, propose/decide core with v0.1 parity, evaluation harness | 2, 3, 4 | — |
| v0.3.0 | **the method**: evidence models, model packs, acceptance model, risk control, explanations and flags | 6, 7, 8 | Phase 5 data (GLYPHARIS output) |
| v0.4.0 | **results on dev**: baselines, main study, ablations, engine transfer | 9–12 | final GLYPHARIS model for reported numbers |
| v1.0.0 | test evaluation, error analysis, efficiency, paper, release | 13–17 | GLYPHARIS test-set freeze and its paper's model |

## Order and dependencies

```
 1 planning ─► 2 input/contract ─► 3 candidate core ─► 4 eval harness ─► v0.2 ══ joint test with GLYPHARIS v0.1
                                                                │
 GLYPHARIS output on HierText-val, GlyphSynth-val ─► 5 paired data
                                                                │
                                  6 evidence/packs ─► 7 acceptance/risk ─► 8 explanations ─► v0.3
                                                                │
                                  9 baselines ─► 10 main ─► 11 ablations ─► 12 transfer ─► v0.4
                                                                │
 GLYPHARIS final model + GDC ───────────────────────────► 13 test ─► 14 errors ─► 15 efficiency ─► 16 paper ─► 17 v1.0
```

- Phases 2, 3 and 4 do not need any external data and can start now.
- Phase 6 can start on synthetic and PG-19 text before Phase 5 finishes; its fit on real pairs
  waits for Phase 5.
- Phase 9's neural baselines need the GPU, so they run after GLYPHARIS training ends.

## The next 24 hours (owner's target: LECTRIS ready when GLYPHARIS finishes)

| Block | Work | Result |
|---|---|---|
| 1 | Phase 1 merged (this plan) | the plan in the repository |
| 2 | Phase 2: data model additions, GLYPHARIS reader, fixture, offset maps | `lectris clean page.json` reads every GLYPHARIS field |
| 3 | Phase 3: proposers, decision layer, parity test | v2 core, same output as v0.1 |
| 4 | Phase 4: edit scoring, line matching, bootstrap | the harness the study needs |
| 5 | v0.2 and the joint test on a few pages | the two projects tested together |

This is tight: Phases 2–4 are roughly a day of focused work each in a normal pace. What fits in
24 hours is v0.2 with Phase 4 possibly partial. The learned components (Phases 6–7) and every
research number come after, and do not block the joint test.

## Success criteria for v1.0

- H1–H6 each decided (supported, not supported or inconclusive) from generated reports.
- The guarantee's validity measured on dev (re-splits) and on GDC.
- Zero runtime dependencies; parity with v0.1 kept or retired by a documented decision.
- Every number in the paper regenerates from a script and a manifest.
