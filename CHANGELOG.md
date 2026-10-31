# Changelog

All notable changes to LECTRIS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
