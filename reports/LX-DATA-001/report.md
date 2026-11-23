# LX-DATA-001

Phase 5 audit: GLYPHARIS glypharis_v1 on the HierText validation fit split. Uncorrected CER and WER, and what the v0.1 rules (B1) and the transforms alone (B0) change. Descriptive: no hypothesis is tested on it.

- Pages: 861; lines: 30901 OCR, 37322 ground truth, 26317 matched (IoU >= 0.5)
- LECTRIS 0.1.0; manifest sha256 `cff59396f452f740b524b319b57526f69aae228681072a4c89c57f0714ff1dd0`
- Bootstrap: 1000 resamples over pages, seed 1337, 95%

| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / neutral | Precision | Pages worse |
|---|---|---|---|---|---|---|---|---|
| uncorrected | 28.03% [24.67, 32.66] | 28.04% [24.68, 32.66] | 44.40% [40.59, 49.49] | — | — | — | — | — |
| B0 | 28.07% [24.70, 32.68] | 28.08% [24.71, 32.69] | 44.75% [40.99, 49.78] | +0.03 [+0.02, +0.04] | 0.016% [0.012, 0.021] | 11 / 149 / 8387 | 6.88% | 7.08% |
| B1-conservative | 28.09% [24.72, 32.70] | 28.10% [24.73, 32.70] | 44.71% [40.92, 49.74] | +0.05 [+0.04, +0.07] | 0.023% [0.016, 0.031] | 3 / 123 / 5 | 2.38% | 5.57% |
| B1-standard | 28.03% [24.66, 32.65] | 28.04% [24.68, 32.65] | 44.59% [40.85, 49.60] | -0.00 [-0.04, +0.03] | 0.041% [0.025, 0.065] | 168 / 167 / 8514 | 50.15% | 7.55% |
| B1-aggressive | 28.03% [24.66, 32.65] | 28.04% [24.68, 32.65] | 44.59% [40.85, 49.60] | -0.00 [-0.04, +0.03] | 0.041% [0.025, 0.065] | 169 / 168 / 8525 | 50.15% | 7.67% |

Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the system's normalised CER minus the uncorrected text's, in points. The harm rate is the characters broken by harmful edits per reference character (ADR-0002).

## Edits by rule

| System | Rule | Fix | Harm | Neutral | Net effect (characters) |
|---|---|---|---|---|---|
| B0 | `unwrap.join_lines` | 11 | 149 | 8387 | +138 |
| B1-conservative | `hyphenation.join` | 3 | 123 | 5 | +240 |
| B1-standard | `confusables.in_numbers` | 13 | 0 | 8 | -13 |
| B1-standard | `hyphenation.join` | 3 | 123 | 5 | +240 |
| B1-standard | `noise.drop_lines` | 126 | 13 | 14 | -247 |
| B1-standard | `numbers.separators` | 0 | 0 | 2 | +0 |
| B1-standard | `punctuation.spacing` | 18 | 5 | 1 | -13 |
| B1-standard | `unwrap.join_lines` | 8 | 26 | 8484 | +18 |
| B1-aggressive | `confusables.in_numbers` | 13 | 0 | 8 | -13 |
| B1-aggressive | `confusables.in_words` | 1 | 1 | 6 | +0 |
| B1-aggressive | `hyphenation.join` | 3 | 123 | 5 | +240 |
| B1-aggressive | `noise.drop_lines` | 126 | 13 | 14 | -247 |
| B1-aggressive | `numbers.separators` | 0 | 0 | 2 | +0 |
| B1-aggressive | `punctuation.quotes` | 0 | 0 | 5 | +0 |
| B1-aggressive | `punctuation.spacing` | 18 | 5 | 1 | -13 |
| B1-aggressive | `unwrap.join_lines` | 8 | 26 | 8484 | +18 |

The net effect is the sum of the edits' effects on the distance to the reference: below zero the rule repaired more than it broke.
