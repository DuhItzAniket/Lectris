# LX-BASE-001

Phase 9: baseline B2, a lexicon corrector (each word not in the pack's lexicon becomes its most frequent word one edit away), against B0, B1 and LECTRIS-standard under the risk policy, on dev. Descriptive.

- Pages: 433; lines: 15420 OCR, 18239 ground truth, 13346 matched (IoU >= 0.5)
- LECTRIS 0.1.0; manifest sha256 `d143f9db84c453158564d071a1a5c1d4ca75c845135b6c207dcfbd0e1ea95cfb`
- Bootstrap: 1000 resamples over pages, seed 1337, 95%

| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / neutral / layout | Precision | Pages worse |
|---|---|---|---|---|---|---|---|---|
| uncorrected | 26.17% [22.22, 30.83] | 26.17% [22.23, 30.83] | 41.92% [37.36, 46.82] | — | — | — | — | — |
| B0 | 26.17% [22.22, 30.83] | 26.17% [22.23, 30.84] | 41.96% [37.39, 46.85] | +0.00 [+0.00, +0.01] | 0.000% [0.000, 0.000] | 0 / 0 / 0 / 4130 | — | 2.31% |
| B1-standard | 26.17% [22.22, 30.83] | 26.17% [22.22, 30.83] | 41.93% [37.36, 46.78] | +0.00 [-0.03, +0.04] | 0.078% [0.027, 0.147] | 60 / 51 / 7 / 4175 | 54.05% | 6.00% |
| B2-lexicon | 27.15% [23.20, 31.77] | 27.15% [23.21, 31.77] | 46.46% [42.02, 51.15] | +0.98 [+0.86, +1.10] | 1.410% [1.292, 1.539] | 610 / 2686 / 707 / 4130 | 18.51% | 78.06% |
| LX-standard | 26.14% [22.20, 30.81] | 26.14% [22.21, 30.81] | 41.75% [37.28, 46.56] | -0.03 [-0.06, +0.01] | 0.095% [0.044, 0.165] | 174 / 85 / 43 / 4123 | 67.18% | 8.55% |

Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the system's normalised CER minus the uncorrected text's, in points. The harm rate is the characters broken by harmful edits per reference character (ADR-0002). Layout edits (de-hyphenation, unwrapping) are counted apart: the reference is laid out the same way (lectris.eval.scoring, R-15).

## Edits by rule

| System | Rule | Fix | Harm | Neutral | Layout | Net effect (characters) |
|---|---|---|---|---|---|---|
| B0 | `unwrap.join_lines` | 0 | 0 | 0 | 4130 | -79 |
| B1-standard | `confusables.in_numbers` | 5 | 0 | 4 | 0 | -10 |
| B1-standard | `hyphenation.join` | 0 | 0 | 0 | 73 | -128 |
| B1-standard | `noise.drop_lines` | 46 | 37 | 2 | 0 | -7 |
| B1-standard | `numbers.separators` | 0 | 2 | 0 | 0 | +2 |
| B1-standard | `punctuation.spacing` | 9 | 12 | 1 | 0 | +3 |
| B1-standard | `unwrap.join_lines` | 0 | 0 | 0 | 4102 | -17 |
| B2-lexicon | `lexical.word` | 610 | 2686 | 707 | 0 | +2187 |
| B2-lexicon | `unwrap.join_lines` | 0 | 0 | 0 | 4130 | -79 |
| LX-standard | `confusables.in_numbers` | 5 | 0 | 4 | 0 | -10 |
| LX-standard | `hyphenation.join` | 0 | 0 | 0 | 21 | -1 |
| LX-standard | `lexical.word` | 100 | 32 | 35 | 0 | -62 |
| LX-standard | `noise.drop_lines` | 45 | 36 | 2 | 0 | -7 |
| LX-standard | `punctuation.spacing` | 9 | 11 | 1 | 0 | +2 |
| LX-standard | `segmentation.merge` | 3 | 2 | 1 | 0 | -1 |
| LX-standard | `segmentation.split` | 12 | 4 | 0 | 0 | -8 |
| LX-standard | `unwrap.join_lines` | 0 | 0 | 0 | 4102 | -59 |

The net effect is the sum of the edits' effects on the distance to the reference: below zero the rule repaired more than it broke. For a layout rule it is measured against a reference laid out by the same rule, so it shows agreement, not accuracy.
