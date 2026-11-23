# LX-TEST-001

Phase 13, the test (run once): on GDC 1.1 (106 photographed printed pages, GLYPHARIS glypharis_v1 output), what do the frozen systems change? H1, H2 and H3 confirmed on GDC: LX-standard against B0, B1 and B2; the engine-feature ablation; each profile's harm rate against its budget on a document set none of it was fitted or calibrated on. Code at 8a1699c, packs frozen by SHA-256 (research/experiments.md).

- Pages: 106; lines: 9038 OCR, 8372 ground truth, 7045 matched (IoU >= 0.5)
- LECTRIS 0.3.0; manifest sha256 `9292a679fbc9c83f8b209b958bd4f12f89b43b89d84121b28c225a66513a6447`
- Bootstrap: 1000 resamples over pages, seed 1337, 95%

| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / neutral / layout | Precision | Pages worse |
|---|---|---|---|---|---|---|---|---|
| uncorrected | 21.35% [14.14, 29.78] | 21.49% [14.29, 29.92] | 31.46% [23.35, 40.49] | — | — | — | — | — |
| B0 | 21.35% [14.14, 29.78] | 21.49% [14.29, 29.92] | 31.47% [23.36, 40.50] | -0.00 [-0.00, +0.00] | 0.000% [0.000, 0.000] | 0 / 0 / 0 / 5090 | — | 4.72% |
| B1-standard | 21.35% [14.14, 29.78] | 21.49% [14.29, 29.92] | 31.45% [23.35, 40.46] | -0.00 [-0.01, +0.00] | 0.004% [0.001, 0.007] | 12 / 10 / 7 / 5419 | 54.55% | 10.38% |
| B2-lexicon | 22.06% [14.97, 30.40] | 22.20% [15.12, 30.54] | 35.12% [27.36, 43.57] | +0.71 [+0.57, +0.87] | 0.730% [0.619, 0.841] | 324 / 2459 / 463 / 5090 | 11.64% | 85.85% |
| LX-conservative | 21.39% [14.18, 29.81] | 21.53% [14.33, 29.94] | 31.65% [23.61, 40.57] | +0.04 [+0.01, +0.07] | 0.008% [0.003, 0.014] | 106 / 22 / 37 / 104 | 82.81% | 31.13% |
| LX-standard | 21.36% [14.15, 29.79] | 21.50% [14.30, 29.92] | 31.45% [23.38, 40.41] | +0.01 [-0.01, +0.02] | 0.012% [0.006, 0.019] | 115 / 28 / 42 / 5192 | 80.42% | 26.42% |
| LX-aggressive | 21.36% [14.15, 29.79] | 21.50% [14.30, 29.92] | 31.45% [23.38, 40.41] | +0.01 [-0.01, +0.02] | 0.012% [0.006, 0.019] | 115 / 28 / 42 / 5192 | 80.42% | 26.42% |
| LX-standard-no-engine | 21.35% [14.15, 29.79] | 21.50% [14.30, 29.92] | 31.43% [23.34, 40.41] | +0.00 [-0.01, +0.02] | 0.012% [0.005, 0.021] | 89 / 23 / 19 / 5152 | 79.46% | 23.58% |

Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the system's normalised CER minus the uncorrected text's, in points. The harm rate is the characters broken by harmful edits per reference character (ADR-0002). Layout edits (de-hyphenation, unwrapping) are counted apart: the reference is laid out the same way (lectris.eval.scoring, R-15).

## Paired comparisons

| A vs B | CER difference (points) | Repaired, per reference character | Broken |
|---|---|---|---|
| LX-standard vs B0 | +0.01 [-0.01, +0.02] | +0.04 [+0.03, +0.05] | +0.01 [+0.01, +0.02] |
| LX-standard vs B1-standard | +0.01 [-0.01, +0.03] | +0.03 [+0.02, +0.04] | +0.01 [+0.00, +0.01] |
| LX-standard vs LX-standard-no-engine | +0.00 [-0.01, +0.01] | +0.01 [+0.00, +0.01] | -0.00 [-0.01, +0.00] |

Each is A minus B, paired over pages, with its 95% bootstrap interval, in points of the reference's characters.

## Edits by rule

| System | Rule | Fix | Harm | Neutral | Layout | Net effect (characters) |
|---|---|---|---|---|---|---|
| B0 | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -350 |
| B1-standard | `confusables.in_numbers` | 4 | 0 | 1 | 0 | -4 |
| B1-standard | `hyphenation.join` | 0 | 0 | 0 | 329 | -651 |
| B1-standard | `noise.drop_lines` | 1 | 2 | 0 | 0 | +2 |
| B1-standard | `numbers.separators` | 3 | 0 | 0 | 0 | -3 |
| B1-standard | `punctuation.spacing` | 4 | 8 | 6 | 0 | +4 |
| B1-standard | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -24 |
| B2-lexicon | `lexical.word` | 324 | 2459 | 463 | 0 | +2325 |
| B2-lexicon | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -350 |
| LX-conservative | `hyphenation.join` | 0 | 0 | 0 | 104 | +201 |
| LX-conservative | `lexical.word` | 95 | 22 | 36 | 0 | -67 |
| LX-conservative | `segmentation.merge` | 11 | 0 | 1 | 0 | -11 |
| LX-standard | `confusables.in_numbers` | 1 | 0 | 1 | 0 | -1 |
| LX-standard | `hyphenation.join` | 0 | 0 | 0 | 102 | -1 |
| LX-standard | `lexical.word` | 99 | 21 | 33 | 0 | -68 |
| LX-standard | `noise.drop_lines` | 1 | 2 | 0 | 0 | +2 |
| LX-standard | `punctuation.spacing` | 3 | 5 | 6 | 0 | +2 |
| LX-standard | `segmentation.merge` | 11 | 0 | 2 | 0 | -11 |
| LX-standard | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -250 |
| LX-aggressive | `confusables.in_numbers` | 1 | 0 | 1 | 0 | -1 |
| LX-aggressive | `hyphenation.join` | 0 | 0 | 0 | 102 | -1 |
| LX-aggressive | `lexical.word` | 99 | 21 | 33 | 0 | -68 |
| LX-aggressive | `noise.drop_lines` | 1 | 2 | 0 | 0 | +2 |
| LX-aggressive | `punctuation.spacing` | 3 | 5 | 6 | 0 | +2 |
| LX-aggressive | `segmentation.merge` | 11 | 0 | 2 | 0 | -11 |
| LX-aggressive | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -250 |
| LX-standard-no-engine | `hyphenation.join` | 0 | 0 | 0 | 62 | -3 |
| LX-standard-no-engine | `lexical.word` | 72 | 15 | 12 | 0 | -35 |
| LX-standard-no-engine | `noise.drop_lines` | 1 | 2 | 0 | 0 | +2 |
| LX-standard-no-engine | `punctuation.spacing` | 4 | 6 | 5 | 0 | +2 |
| LX-standard-no-engine | `segmentation.merge` | 11 | 0 | 2 | 0 | -11 |
| LX-standard-no-engine | `segmentation.split` | 1 | 0 | 0 | 0 | -1 |
| LX-standard-no-engine | `unwrap.join_lines` | 0 | 0 | 0 | 5090 | -288 |

The net effect is the sum of the edits' effects on the distance to the reference: below zero the rule repaired more than it broke. For a layout rule it is measured against a reference laid out by the same rule, so it shows agreement, not accuracy.
