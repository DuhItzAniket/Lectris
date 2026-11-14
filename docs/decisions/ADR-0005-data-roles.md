# ADR-0005: Fixed roles and page-level splits for every dataset

- **Status:** Accepted (2026-11-14, Phase 1)

## Context
LECTRIS is fitted and evaluated on **pairs**: what an engine read from a page image, and the
page's ground truth. Those pairs come from datasets GLYPHARIS already uses, with roles fixed by
GLYPHARIS ADR-0005. Two projects touching one test set is a leakage risk.

## Decision

| Source | Pairs from | LECTRIS role |
|---|---|---|
| HierText validation | GLYPHARIS (and Tesseract) on its pages | split by page: **fit** 50%, **cal** 25%, **dev** 25%, stratified by the document-slice flag |
| GlyphSynth validation | GLYPHARIS on its lines | auxiliary fit and dev (synthetic; reported apart) |
| GDC v1 | GLYPHARIS (and Tesseract) on its pages | **test**, frozen; evaluated once, in Phase 13 |
| PG-19 (public-domain books) | text only | language model and lexicon counts (fit) |
| HierText train, GlyphSynth train | — | not used: GLYPHARIS trained on them, so its errors there are not representative |
| FUNSD, OmniDocBench | Tesseract / GLYPHARIS | optional external test, evaluation only, Phase 13 |

- Splits are by page and deterministic (a hash of the page id with a fixed salt), written to
  manifests with counts and hashes.
- Every access to a test set is logged in `research/test_access_log.md`, here and in GLYPHARIS's
  log when it is a GLYPHARIS test set (GDC).
- The GDC evaluation runs only on the GLYPHARIS model version the GLYPHARIS paper reports, after
  that model is frozen, so LECTRIS cannot influence GLYPHARIS's choices.
- No pairs, images or third-party text enter this repository (ground rule 5): manifests and
  scripts only; the data lives in a git-ignored `data/` folder.

## Consequences
- GLYPHARIS selected checkpoints on HierText validation, so its errors there are slightly fewer
  than on unseen pages. The dev numbers are therefore conservative for correction gains; GDC is
  the unbiased test. Stated as a limitation.
- HierText is mostly scene text; the document slice (pages with ≥ 100 validation lines, the
  GLYPHARIS Phase 12 proxy) is the primary dev slice.

## Revisit if
A permissively licensed post-OCR correction dataset with page images or line alignment becomes
available, which could serve as a second test set.
