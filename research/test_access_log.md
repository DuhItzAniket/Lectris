# Test access log

Every read of a test set (GDC, external sets), in order: date, set, what was run (code commit,
pack hash, GLYPHARIS model version), why, and the report. GDC reads are also logged in
GLYPHARIS's `research/test_access_log.md`; the owner keeps that one (LECTRIS does not write to
the GLYPHARIS repository).

| Date | Set | Run | Reason | Report |
|---|---|---|---|---|
| 2026-11-23 | GDC 1.1 (106 pages; frozen file SHA-256 `c4227f1ae6d0aa856c3e64a2bcf55325840343df48dc6810b104e62a6f092af5`) | LX-TEST-001: code `7527e49` (the registration; library code as `8a1699c`); packs `84674369200da3e3b8ab54caea5bdb5921390907af08b597a6aef57234ab147b` (calibrated) and `794e008bac538d980aae4b55967a5bd5e027b749a8dfab7b6508a4750434794a` (no engine); GLYPHARIS glypharis_v1, PyTorch on the CPU; plus the error taxonomy | Phase 13, the test | `reports/LX-TEST-001/` |
| 2026-11-23 | GDC 1.1 (the same file) | LX-TEST-002: code `e722231` (LX-TEST-001's code with the scoring fix); the same packs, engine output and pairs | the registered re-run after a scoring bug found in LX-TEST-001's report (protocol change log) | `reports/LX-TEST-002/` |
