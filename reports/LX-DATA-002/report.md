# LX-DATA-002

LX-DATA-001 again, with layout-neutral references (R-15): the reference is laid out by the system's own layout steps, so de-hyphenation and unwrapping are scored apart. Same pairs, systems and seed. Descriptive: no hypothesis is tested on it.

- Pages: 861; lines: 30901 OCR, 37322 ground truth, 26317 matched (IoU >= 0.5)
- LECTRIS 0.3.0; manifest sha256 `cff59396f452f740b524b319b57526f69aae228681072a4c89c57f0714ff1dd0`
- Bootstrap: 1000 resamples over pages, seed 1337, 95%

| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / neutral / layout | Precision | Pages worse |
|---|---|---|---|---|---|---|---|---|
| uncorrected | 28.03% [24.67, 32.66] | 28.04% [24.68, 32.66] | 44.40% [40.59, 49.49] | — | — | — | — | — |
| B0 | 28.03% [24.67, 32.66] | 28.04% [24.68, 32.66] | 44.42% [40.61, 49.49] | -0.00 [-0.00, +0.00] | 0.000% [0.000, 0.000] | 0 / 0 / 0 / 8547 | — | 0.58% |
| B1-conservative | 28.03% [24.67, 32.66] | 28.04% [24.68, 32.66] | 44.41% [40.60, 49.49] | -0.00 [-0.00, +0.00] | 0.000% [0.000, 0.000] | 0 / 0 / 0 / 131 | — | 0.23% |
| B1-standard | 27.97% [24.61, 32.59] | 27.98% [24.62, 32.60] | 44.25% [40.46, 49.32] | -0.06 [-0.10, -0.04] | 0.013% [0.001, 0.036] | 157 / 18 / 25 / 8649 | 89.71% | 1.51% |
| B1-aggressive | 27.97% [24.61, 32.59] | 27.98% [24.62, 32.60] | 44.25% [40.46, 49.32] | -0.06 [-0.10, -0.04] | 0.013% [0.001, 0.036] | 158 / 19 / 36 / 8649 | 89.27% | 1.63% |

Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the system's normalised CER minus the uncorrected text's, in points. The harm rate is the characters broken by harmful edits per reference character (ADR-0002). Layout edits (de-hyphenation, unwrapping) are counted apart: the reference is laid out the same way (lectris.eval.scoring, R-15).

## Edits by rule

| System | Rule | Fix | Harm | Neutral | Layout | Net effect (characters) |
|---|---|---|---|---|---|---|
| B0 | `unwrap.join_lines` | 0 | 0 | 0 | 8547 | -151 |
| B1-conservative | `hyphenation.join` | 0 | 0 | 0 | 131 | -242 |
| B1-standard | `confusables.in_numbers` | 13 | 0 | 8 | 0 | -13 |
| B1-standard | `hyphenation.join` | 0 | 0 | 0 | 131 | -242 |
| B1-standard | `noise.drop_lines` | 126 | 13 | 14 | 0 | -247 |
| B1-standard | `numbers.separators` | 0 | 0 | 2 | 0 | +0 |
| B1-standard | `punctuation.spacing` | 18 | 5 | 1 | 0 | -13 |
| B1-standard | `unwrap.join_lines` | 0 | 0 | 0 | 8518 | -31 |
| B1-aggressive | `confusables.in_numbers` | 13 | 0 | 8 | 0 | -13 |
| B1-aggressive | `confusables.in_words` | 1 | 1 | 6 | 0 | +0 |
| B1-aggressive | `hyphenation.join` | 0 | 0 | 0 | 131 | -242 |
| B1-aggressive | `noise.drop_lines` | 126 | 13 | 14 | 0 | -247 |
| B1-aggressive | `numbers.separators` | 0 | 0 | 2 | 0 | +0 |
| B1-aggressive | `punctuation.quotes` | 0 | 0 | 5 | 0 | +0 |
| B1-aggressive | `punctuation.spacing` | 18 | 5 | 1 | 0 | -13 |
| B1-aggressive | `unwrap.join_lines` | 0 | 0 | 0 | 8518 | -31 |

The net effect is the sum of the edits' effects on the distance to the reference: below zero the rule repaired more than it broke. For a layout rule it is measured against a reference laid out by the same rule, so it shows agreement, not accuracy.
