# LX-ABL-001

H2: at the same harm budget (standard, alpha 0.02), does the acceptance model with the engine's line confidence and detection score repair more than the same model fitted without them? Both packs calibrated the same way on fit and cal; full runs on dev; paired comparison over pages.

- Pages: 433; lines: 15420 OCR, 18239 ground truth, 13346 matched (IoU >= 0.5)
- LECTRIS 0.1.0; manifest sha256 `d143f9db84c453158564d071a1a5c1d4ca75c845135b6c207dcfbd0e1ea95cfb`
- Bootstrap: 1000 resamples over pages, seed 1337, 95%

| System | CER (norm.) | CER (raw) | WER | ΔCER vs uncorrected | Harm rate | Fix / harm / neutral / layout | Precision | Pages worse |
|---|---|---|---|---|---|---|---|---|
| uncorrected | 26.17% [22.22, 30.83] | 26.17% [22.23, 30.83] | 41.92% [37.36, 46.82] | — | — | — | — | — |
| LX-standard | 26.14% [22.20, 30.81] | 26.14% [22.21, 30.81] | 41.75% [37.28, 46.56] | -0.03 [-0.06, +0.01] | 0.095% [0.044, 0.165] | 174 / 85 / 43 / 4123 | 67.18% | 8.55% |
| LX-standard-no-engine | 26.16% [22.22, 30.82] | 26.16% [22.22, 30.82] | 41.86% [37.35, 46.68] | -0.01 [-0.04, +0.03] | 0.090% [0.038, 0.160] | 115 / 74 / 14 / 4115 | 60.85% | 7.85% |

Intervals are 95% paired-bootstrap percentile intervals over pages. ΔCER is the system's normalised CER minus the uncorrected text's, in points. The harm rate is the characters broken by harmful edits per reference character (ADR-0002). Layout edits (de-hyphenation, unwrapping) are counted apart: the reference is laid out the same way (lectris.eval.scoring, R-15).

## Paired comparisons

| A vs B | CER difference (points) | Repaired, per reference character | Broken |
|---|---|---|---|
| LX-standard vs LX-standard-no-engine | -0.02 [-0.03, -0.01] | +0.03 [+0.02, +0.04] | +0.01 [+0.00, +0.01] |

Each is A minus B, paired over pages, with its 95% bootstrap interval, in points of the reference's characters.

## Edits by rule

| System | Rule | Fix | Harm | Neutral | Layout | Net effect (characters) |
|---|---|---|---|---|---|---|
| LX-standard | `confusables.in_numbers` | 5 | 0 | 4 | 0 | -10 |
| LX-standard | `hyphenation.join` | 0 | 0 | 0 | 21 | -1 |
| LX-standard | `lexical.word` | 100 | 32 | 35 | 0 | -62 |
| LX-standard | `noise.drop_lines` | 45 | 36 | 2 | 0 | -7 |
| LX-standard | `punctuation.spacing` | 9 | 11 | 1 | 0 | +2 |
| LX-standard | `segmentation.merge` | 3 | 2 | 1 | 0 | -1 |
| LX-standard | `segmentation.split` | 12 | 4 | 0 | 0 | -8 |
| LX-standard | `unwrap.join_lines` | 0 | 0 | 0 | 4102 | -59 |
| LX-standard-no-engine | `confusables.in_numbers` | 5 | 0 | 1 | 0 | -10 |
| LX-standard-no-engine | `hyphenation.join` | 0 | 0 | 0 | 13 | -1 |
| LX-standard-no-engine | `lexical.word` | 48 | 26 | 9 | 0 | -19 |
| LX-standard-no-engine | `noise.drop_lines` | 41 | 35 | 2 | 0 | -5 |
| LX-standard-no-engine | `punctuation.spacing` | 8 | 10 | 1 | 0 | +2 |
| LX-standard-no-engine | `segmentation.merge` | 2 | 2 | 1 | 0 | +0 |
| LX-standard-no-engine | `segmentation.split` | 11 | 1 | 0 | 0 | -10 |
| LX-standard-no-engine | `unwrap.join_lines` | 0 | 0 | 0 | 4102 | -66 |

The net effect is the sum of the edits' effects on the distance to the reference: below zero the rule repaired more than it broke. For a layout rule it is measured against a reference laid out by the same rule, so it shows agreement, not accuracy.
