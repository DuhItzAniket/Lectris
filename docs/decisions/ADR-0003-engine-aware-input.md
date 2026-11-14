# ADR-0003: Engine uncertainty in the data model; the GLYPHARIS JSON contract

- **Status:** Accepted (2026-11-14, Phase 1). The `chars` field is **Proposed** to GLYPHARIS and
  needs a change there.

## Context
LECTRIS v0.1 reads GLYPHARIS output through the generic flat JSON form. It keeps line text, box
and confidence, and loses the page size, the detector score, the polygon and the engine's
identity. Neither repository names the other, so nothing tests the handoff. GLYPHARIS's
recognizer has per-frame CTC posteriors internally but exports only a line confidence.

## Decision
1. **Data model.** `Word.glyphs` (character, confidence, alternatives), `Line.polygon`,
   `Line.detection`, `Page.source`, `Document.engine` (architecture §4). All optional.
2. **A dedicated reader**, `lectris.io.glypharis`, recognised by the `glypharis_version` key. It
   reads every field `OCRResult.to_dict` writes today:
   `glypharis_version`, `model_version`, `width`, `height`, `lines[].text`, `confidence`,
   `det_score`, `bbox`, `polygon`, `quad`, optional `confidence_at`. Unknown keys are ignored.
3. **Proposed addition to GLYPHARIS** (optional, backwards compatible): per line,
   ```json
   "chars": [{"c": "e", "p": 0.91, "alt": [["c", 0.06], ["o", 0.02]]}, ...]
   ```
   one entry per emitted character in the greedy CTC path (spaces included), `p` the mean
   posterior of the character's frames, `alt` the top-k _(tunable, k = 3)_ other classes over
   those frames (`""` for blank), at the recognizer's temperature. `"".join(c) == text`.
4. **Contract tests on both sides.** LECTRIS keeps a hand-written sample of the JSON as a test
   fixture (original data). GLYPHARIS should test that `to_dict` still has the keys the contract
   lists. A change to either side updates the fixture in the same pull request.
5. **Packs are per engine version.** Engine-specific evidence (channel model, acceptance weights,
   λ̂) is fitted on one `model_version`. A new GLYPHARIS model means a new pack.

## Consequences
- Without `chars`, LECTRIS still has line confidence and detector score; RQ2 then compares
  line-level against no engine evidence, and the character-level arm waits for GLYPHARIS.
- The paper reports results for a fixed GLYPHARIS model version.
- Tesseract input (hOCR/ALTO) is the engine-transfer case (RQ4).

## Revisit if
GLYPHARIS changes its output format, or adds beam search with n-best lines (then candidates can
come from the n-best list as well).
