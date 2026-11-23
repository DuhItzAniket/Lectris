# Experiment registry

Every experiment is registered here **before** it runs: ID, question, data, configuration,
expected outcome, and then the report it produced. IDs: `LX-<AREA>-NNN`
([IMPLEMENTATION_PLAN.md §6](../docs/IMPLEMENTATION_PLAN.md#6-experiment-design-defaults)).

| ID | Phase | Question | Data | Config | Registered | Status | Report |
|---|---|---|---|---|---|---|---|
| LX-DATA-001 | 5 | What is GLYPHARIS glypharis_v1's error on HierText validation made of, how much of it lies inside a token (the most a local correction can reach), and what do B0 and the v0.1 rules (B1, three profiles) change? Descriptive; no hypothesis tested. Expected: a large share of missed and extra lines on scene-text pages, a smaller one on the document slice | HierText validation, fit split, GLYPHARIS glypharis_v1 | `configs/LX-DATA-001.json`; `scripts/error_taxonomy.py` on the same manifest | 2026-11-23 | done (2026-11-23); its CER changes are superseded by LX-DATA-002 (R-15) | `reports/LX-DATA-001/report.md`, `taxonomy.md` |
| LX-DATA-002 | 5 | LX-DATA-001 under layout-neutral references (R-15): how much do the v0.1 rules change CER once line-break decisions are scored apart? Descriptive; no hypothesis tested. Expected: B1-standard below the uncorrected CER, the gain coming from noise lines, confusions and punctuation spacing | HierText validation, fit split, GLYPHARIS glypharis_v1 | `configs/LX-DATA-002.json` | 2026-11-23 | done (2026-11-23) | `reports/LX-DATA-002/report.md` |
