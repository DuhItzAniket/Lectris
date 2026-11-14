# Datasets

Provenance, licence and role of every dataset LECTRIS uses. Roles are fixed by
[ADR-0005](docs/decisions/ADR-0005-data-roles.md). No data from these sources is stored in this
repository: only manifests (ids, counts, hashes) and the scripts that build the pairs.

Licences below are quoted from GLYPHARIS's dataset cards (checked there on 2026-10-10) and must be
re-checked for LECTRIS's own uses before Phase 5: deriving word counts and n-gram counts, and
publishing model packs.

| Dataset | What LECTRIS takes | Role | Licence (as stated by the publisher) | Packs publishable? |
|---|---|---|---|---|
| HierText validation | page images through GLYPHARIS / Tesseract, and line ground truth | fit / cal / dev | CC BY-SA 4.0 (images from Open Images, CC BY 2.0) | to check (share-alike) |
| GlyphSynth validation (GLYPHARIS's own) | lines through GLYPHARIS, and ground truth | auxiliary fit / dev | inherits open font and public-domain / Apache-2.0 text licences | likely yes |
| GDC v1 (GLYPHARIS's own) | page images through GLYPHARIS / Tesseract, and ground truth | test (Phase 13 only) | openly licensed source PDFs; GLYPHARIS's annotations | evaluation only |
| PG-19 | book text | language model and word counts | Apache 2.0 (public-domain books) | yes, to confirm |
| FUNSD (optional) | form images through the engines | external test | non-commercial research and education only | evaluation only |
| OmniDocBench (optional) | page images through the engines | external test | research use only | evaluation only |

## Engine outputs

Pairs are produced by:
- **GLYPHARIS**: `glypharis-ocr --input-dir <pages> --format json`, a fixed model bundle (its
  `model_version` recorded in the manifest).
- **Tesseract**: `tesseract <page> <out> hocr` (and ALTO), its version and language data recorded.

Engine outputs are derived from the dataset images and inherit their terms; they stay outside the
repository.

## Candidate post-OCR datasets (not yet used)

Public post-OCR correction corpora (such as the ICDAR 2017 and 2019 post-OCR competitions, and
historical newspaper sets) mostly pair text with text, without page images or the engine's
uncertainty, and use historical OCR engines. They could serve as an engine-agnostic external
test of the text-only path. Their licences and fit for this role are unverified.
