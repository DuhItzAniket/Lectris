# Changelog

All notable changes to LECTRIS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- The property tests try a fixed set of examples by default, so every run of the suite is the
  same and a failure reproduces exactly; `HYPOTHESIS_PROFILE=explore` searches with random
  examples.
- `confusables.in_numbers` reads an `O` before a decimal separator and a digit as the zero OCR
  misread: `O.5` becomes `0.5`, `O,75` becomes `0,75`. `O5`, `O.K.` and words are left alone.

## [0.1.0] - 2026-10-31

The first release: OCR output read from five formats, laid out in reading order, and cleaned by
seventeen rules in three profiles, with every edit recorded.

### Added
- The document model (pages, blocks, lines and words, with boxes and confidences) and edits:
  every text change is recorded as its rule, its span, what was there and what replaced it.
- Readers for hOCR, ALTO XML (versions 2 to 4), Tesseract TSV, JSON and plain text, and
  detection of the format from the content. ALTO with entity declarations is refused.
- Normalisation rules: Unicode (NFC, ligatures, invisible characters, compatibility forms),
  whitespace (line breaks, runs of spaces, trimming), punctuation (spacing, quotes, dashes,
  ellipses), and unwrapping a paragraph onto one line.
- Repairs: words hyphenated across line breaks rejoined, letters and digits that OCR confuses in
  numbers and words, spaces inside numbers; Levenshtein, Damerau and OCR-weighted edit
  distances, and an optional lexicon.
- Layout: words grouped into lines, columns, reading order by recursive XY-cut with skew
  correction, and paragraphs, with every threshold relative to the size of the text.
- Confidence aggregation and low-confidence spans; text-quality heuristics and a rule that drops
  noise lines; character and word alignment; character and word error rates.
- The pipeline, with the `conservative`, `standard` and `aggressive` profiles; reports (summary,
  JSON, Markdown); the `lectris` command (`clean`, `eval`, `rules`).

[Unreleased]: https://github.com/DuhItzAniket/Lectris/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/DuhItzAniket/Lectris/releases/tag/v0.1.0
