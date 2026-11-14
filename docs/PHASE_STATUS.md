# Phase status

Live record of every phase. Values are measured or quoted from generated reports, never invented.
The phases are defined in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

| Phase | Name | Status | Tag |
|---|---|---|---|
| 0 | v0.1 rule engine | **COMPLETE** | `v0.1.0` |
| 1 | Research planning | **IN PROGRESS** (owner review) | — |
| 2 | Engine-aware input and the GLYPHARIS contract | not started | — |
| 3 | Candidate core with v0.1 parity | not started | — |
| 4 | Evaluation harness | not started | — |
| 5 | Paired data | not started (needs GLYPHARIS output) | — |
| 6 | Evidence models and model packs | not started | — |
| 7 | Acceptance model and risk control | not started | — |
| 8 | Explanations, flags and the v0.3 interface | not started | — |
| 9 | Baselines | not started | — |
| 10 | Main study (dev) | not started | — |
| 11 | Ablations | not started | — |
| 12 | Engine transfer | not started | — |
| 13 | Test evaluation | not started | — |
| 14 | Error analysis | not started | — |
| 15 | Efficiency | not started | — |
| 16 | Research package | not started | — |
| 17 | Release v1.0 | not started | — |

## Open items for the owner

| Item | Needed by | Status |
|---|---|---|
| Review the v2 architecture and the research framing (ADR-0001, 0002) | Phase 2 | open |
| Approve or decline the research environment for neural baselines (ADR-0004, point 3) | Phase 9 | open |
| Decide whether GLYPHARIS exports per-character `chars` (ADR-0003) | Phase 6 (RQ2 character arm) | open |
| GLYPHARIS output (JSON) on HierText validation and GlyphSynth validation pages, with the model version | Phase 5 | open |
| Tesseract installed, its version, for the transfer engine | Phase 5 | open |
| Target venue (journal or conference) and its page limit | Phase 16 | open |

---

## Phase 0 — v0.1 rule engine

**Status:** COMPLETE (released 2026-10-31 as v0.1.0; one rule change since, in `Unreleased`).

**Results (measured):** 1,270 tests pass (2026-11-14, `uv run pytest`).

---

## Phase 1 — Research planning

**Status:** IN PROGRESS (opened 2026-11-14 on `docs/research-plan`).

**Implemented**
- Target architecture v2 (`docs/ARCHITECTURE.md`), ADR-0001 to ADR-0007.
- Implementation plan, roadmap, experiment protocol, risk register, dataset cards.
- Hypotheses H1–H6, experiment registry, research log, test access log, related-work notes, paper
  outline.

**Known issues**
- Related-work notes are written from memory and are unverified; the novelty claim (risk control
  over harm in post-OCR correction) must be checked by a literature search before Phase 16
  (RISK_REGISTER R-03).
- Dataset licences are quoted from GLYPHARIS's DATASETS.md and must be re-checked for LECTRIS's
  uses (derived word counts, pack publication).
