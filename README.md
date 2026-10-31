# LECTRIS

**OCR output, read back into clean, ordered text: every change it makes is recorded and explained.**

LECTRIS reads what an OCR engine produced (hOCR, ALTO, Tesseract TSV, JSON or plain text), puts the lines in reading order, groups them into paragraphs, and repairs the text with small, conservative rules that record every edit they make.

It is being built in the open; the design is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [CONTRIBUTING.md](CONTRIBUTING.md) says how changes are made and checked.

## License

[Apache License 2.0](LICENSE).
