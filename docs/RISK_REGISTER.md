# Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Owner of the check |
|---|---|---|---|---|---|
| R-01 | HierText is mostly scene text: few locally correctable errors on its pages, so effects are small | high | high | primary dev slice is the document slice; GlyphSynth reported apart; GDC as test; Phase 5 audit measures the correctable share first | Phase 5 |
| R-02 | GLYPHARIS exports no character uncertainty, so the character-level part of RQ2 cannot run | medium | medium | ADR-0003 proposes `chars`; RQ2 still compares line-level evidence against none | owner, Phase 2 |
| R-03 | The novelty claim (distribution-free harm control for post-OCR correction) is already published | medium | high | literature search before Phase 10; if found, the contribution becomes engine-aware evidence and the joint system, and the paper cites it | Phase 1 follow-up |
| R-04 | Edits on one page are dependent; edit-level statistics would be too optimistic | high | high | page is the unit for splits, bootstrap and risk (ADR-0002) | protocol |
| R-05 | Too few calibration pages: λ̂ very strict, low recall | medium | high | power check in Phase 7; pool cal pages across slices; report the recall cost against the oracle | Phase 7 |
| R-06 | Harm labels wrong where alignment is ambiguous | medium | medium | windowed alignment on matched lines; 200 edits checked by hand (protocol §3.2) | Phase 4, 10 |
| R-07 | The GLYPHARIS model changes after packs are fitted | high | medium | packs keyed by `model_version`; refit on the final model before reported runs (ADR-0003, 0007) | every phase |
| R-08 | Pure-Python fitting too slow | medium | low | pruning, capped corpus; measured in Phase 6; ADR-0004 revisit condition | Phase 6 |
| R-09 | The neural baseline is weak because of the 6 GB GPU or a small budget, which a reviewer would call unfair | medium | medium | report the budget; ByT5-small at line level fits; state the limitation | Phase 9 |
| R-10 | Test leakage between the two projects (GDC) | low | high | ADR-0005: GDC read once in Phase 13, after the GLYPHARIS model freeze, logged in both logs | Phase 13 |
| R-11 | Normalisation credited as correction | medium | medium | normalised track is primary (protocol §2) | protocol |
| R-12 | A derived word list or pack carries a share-alike licence (HierText CC BY-SA 4.0) | medium | low | word counts from PG-19 only; HierText text used for fitting packs that are not published unless the licence is cleared | Phase 6, 17 |
| R-13 | The 24-hour target for v0.2 slips | high | low | v0.2 is the integration only; the research phases do not depend on the deadline | roadmap |
| R-14 | Parity with v0.1 blocks needed fixes | low | medium | ADR-0006 revisit: fix in both, document | Phase 3 |
