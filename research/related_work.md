# Related work (notes)

> **Unverified.** Written from memory in Phase 1. Every entry must be checked (authors, year,
> venue, claim) against the source before it is cited, and the search for prior work on
> risk-controlled post-OCR correction must be done before Phase 10 (RISK_REGISTER R-03).

## Post-OCR correction
- **Surveys.** A survey of post-OCR processing approaches (Nguyen et al., ACM Computing Surveys,
  2021) organises the field into isolated-word and context-dependent methods, and dictionary,
  channel, language-model and sequence-to-sequence approaches.
- **Benchmarks.** The ICDAR 2017 and ICDAR 2019 competitions on post-OCR text correction (Chiron et
  al.; Rigaud et al.) split the task into error detection and correction, on historical text.
- **Noisy channel.** Spelling correction as P(observed | intended) · P(intended), with
  substring-level error models (Brill and Moore, 2000); applied to OCR by Kolak and Resnik (2002).
- **Lexical and anagram hashing.** TICCL (Reynaert) and SymSpell-style deletion indexes for fast
  candidate generation.
- **Neural sequence-to-sequence.** Character and byte-level models (ByT5, Xue et al., 2022);
  ensembles of character sequence-to-sequence models for documents (Ramirez-Orta et al., 2022);
  correction for low-resource and endangered languages (Rijhwani et al., 2020).
- **LLMs.** Recent work prompts or fine-tunes large language models for post-OCR correction of
  historical newspapers, reporting gains but also hallucinated or over-modernised text.

**Gap LECTRIS addresses** (to be confirmed): methods are compared on average error reduction;
harm to correct text is rarely reported per page and never, to our knowledge, bounded with a
guarantee; and correctors rarely use the engine's own uncertainty, because they receive plain
text.

## Distribution-free risk control
- Conformal prediction (Vovk et al.; Angelopoulos and Bates, a gentle introduction, 2021).
- Risk-controlling prediction sets (Bates et al., 2021).
- **Learn-then-Test** (Angelopoulos, Bates, Candès, Jordan, Lei, 2021): calibrating any
  hyperparameter to control a risk, by multiple testing; with Hoeffding–Bentkus p-values.
- Conformal risk control (Angelopoulos et al., 2022/2024).
- Selective prediction and abstention (Geifman and El-Yaniv, 2017).

## Calibration
- Calibration of modern neural networks, temperature scaling, ECE (Guo et al., 2017).
- Platt scaling (Platt, 1999).

## Language models
- Kneser–Ney smoothing (Kneser and Ney, 1995); the empirical study of smoothing (Chen and Goodman,
  1999).

## OCR engines
- GLYPHARIS (this project's companion engine), Tesseract (LSTM engine), PaddleOCR.
