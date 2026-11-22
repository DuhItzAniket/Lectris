# Phase status

Live record of every phase. Values are measured or quoted from generated reports, never invented.
The phases are defined in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

| Phase | Name | Status | Tag |
|---|---|---|---|
| 0 | v0.1 rule engine | **COMPLETE** | `v0.1.0` |
| 1 | Research planning | **COMPLETE** (merged in #15; no phase tag) | — |
| 2 | Engine-aware input and the GLYPHARIS contract | **IN PROGRESS** (part 1 of 3: the GLYPHARIS reader) | — |
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
| Decide whether GLYPHARIS exports per-character `chars` (ADR-0003); GLYPHARIS 1.0 does not | Phase 6 (RQ2 character arm) | open |
| GLYPHARIS v1.1 installable on Python 3.12+ (1.0 pins `<3.12`, LECTRIS needs `>=3.12`); the CLI handoff through JSON works across two environments meanwhile | joint Python use | open (GLYPHARIS side) |
| GLYPHARIS output (JSON) on HierText validation and GlyphSynth validation pages, with the model version | Phase 5 | open |
| Tesseract installed, its version, for the transfer engine | Phase 5 | open |
| Target venue (journal or conference) and its page limit | Phase 16 | open |

---

## Phase 0 — v0.1 rule engine

**Status:** COMPLETE (released 2026-10-31 as v0.1.0; one rule change since, in `Unreleased`).

**Results (measured):** 1,270 tests pass (2026-11-14, `uv run pytest`).

---

## Phase 1 — Research planning

**Status:** COMPLETE (opened 2026-11-14 on `docs/research-plan`, merged 2026-11-14 as #15).

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

---

## Phase 2 — Engine-aware input and the GLYPHARIS contract

**Status:** IN PROGRESS (opened 2026-11-22). Lands in three pull requests:
1. the GLYPHARIS reader and the model's detection fields (this branch, `phase/02-glypharis-reader`);
2. `OffsetMap`, from edits and composed across stages, with property tests;
3. ALTO `CC` and `ALTERNATIVE`, and `Glyph`, once a real input that carries them is in hand.

**Part 1, implemented**
- `Engine`, `Line.polygon`, `Line.detection`, `Document.engine`, validated; kept by layout and
  `clean()`; written and read by LECTRIS's JSON form only when set.
- `lectris.io.glypharis`: reads every key GLYPHARIS 1.0's `OCRResult.to_dict` writes, or ignores
  it on purpose (`READ`, `IGNORED`, `LINE_READ`, `LINE_IGNORED`); detection by the first key;
  `--format glypharis`.
- A hand-written fixture in the exact shape of GLYPHARIS 1.0's JSON, and a contract test: the
  fixture holds every key, and every key is either read or ignored.

**Deviations from the plan**
- `Page.source` (ADR-0003) is not added: no format names its image, and the caller knows the file.
- `Glyph` and the `chars` field wait for GLYPHARIS to write them (it does not in 1.0).

**Results (measured):** `uv run pytest`: 1,335 passed (2026-11-22). Cleaning the fixture gives
the same text through the new reader as through the flat JSON reading, for all three profiles
(a test).
