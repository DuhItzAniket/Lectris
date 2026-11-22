"""Evaluation: how much a correction helps and how much it harms (experiment protocol).

- ``truth``: a page's ground truth, as lines with their text and box.
- ``matching``: OCR lines matched one to one with ground-truth lines by box overlap, so that a
  difference in reading order is not counted as recognition errors.
- ``scoring``: each block compared with the ground truth of its lines; character and word error
  rates in the raw and the normalised tracks; every edit labelled a fix, a harm or neutral; the
  harm rate of a page.
- ``stats``: the paired bootstrap over pages.
- ``experiment``: a registered experiment run from its configuration into a report.

It reads files and writes reports, so, like ``lectris.io`` and the CLI, it does I/O; its numbers
are deterministic for a seed.
"""
