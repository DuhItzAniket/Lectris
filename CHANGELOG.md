# Changelog

All notable changes to LECTRIS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- The research plan for v2: a target architecture in which rules propose candidate edits, evidence
  (including the OCR engine's uncertainty) scores them, and a threshold that bounds the harm rate
  accepts them; decision records, phases, roadmap, experiment protocol, risk register, dataset
  cards and hypotheses. No change to what LECTRIS does.
- A reader for the JSON the GLYPHARIS OCR engine writes (`OCRResult.to_json()`), detected from
  its `glypharis_version` key, or chosen with `--format glypharis`. It keeps what the flat JSON
  form dropped: the page's size, each line's polygon and detection score, and the engine and
  model versions. The cleaned text is the same as before.
- The model: a line's `polygon` and `detection` score, and the document's `engine` (`Engine`:
  name, version, model). Layout and `clean()` keep them, and LECTRIS's JSON form writes and reads
  them when they are set.
- `lectris.edits.OffsetMap`: maps a span of a revision's output, or of the output of several
  revisions in turn, back to the span of the input it came from.
- Character uncertainty: a word's `glyphs` (`Glyph`: each character's confidence and the other
  characters the engine weighed) and its `alternatives` (other readings of the whole word). ALTO
  `CC` and `ALTERNATIVE` are read into them, and so is the per-character `chars` field proposed
  for GLYPHARIS, when present. LECTRIS's JSON form writes and reads them when set.
- The candidate core: the rules that guess (confusions, separators in numbers, spaces before
  punctuation, de-hyphenation, noise lines) now propose `Candidate` edits, and `lectris.decide`
  accepts them under a policy, recording a `Decision` for each (`Result.decisions()`). The
  default policy, `PARITY`, accepts what LECTRIS v0.1 did, so the output is unchanged;
  `Threshold` accepts candidates by a score. `clean()` takes `policy`.
- `lectris.eval` and `lectris experiment run`: score cleaned pages against their ground truth
  (lines matched by box overlap, CER and WER in a raw and a normalised track, every edit labelled
  a fix, a harm or neutral, the harm rate), with a seeded paired bootstrap over pages, and run a
  registered experiment from its configuration into a JSON and Markdown report.

### Changed
- GLYPHARIS output is now detected as `glypharis` instead of `json`. Its words, boxes and
  confidences are read as before.
- In LECTRIS's own JSON form, `engine` at the top level, `polygon` and `detection` in a line,
  and `glyphs` and `alternatives` in a word are now read, so a value of the wrong kind there is
  an error, where it used to be ignored.
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
