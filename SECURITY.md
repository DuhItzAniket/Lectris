# Security policy

LECTRIS reads files produced by OCR engines, which may come from anywhere. Treat every input as
untrusted.

## What the readers do and do not do

- No reader fetches anything: no network access, no external entities, no linked images or
  stylesheets.
- XML (ALTO) is parsed with the standard library's expat. It resolves no external entities, and
  a document type with entity declarations is refused before parsing.
- hOCR is parsed with the standard library's HTML parser; no scripts are run and nothing is
  rendered.

## Supported versions

Only the latest release is supported. Fixes go into `main` and the next release.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting on this
repository: the "Security" tab, then "Report a vulnerability". Include an input that shows the
problem and the version you used. We aim to answer within 7 days.
