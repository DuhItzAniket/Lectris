"""Learned evidence, as data (ADR-0004; architecture §10 and §12).

- ``charlm``: a character n-gram language model, interpolated modified Kneser-Ney.
- ``channel``: what an engine confuses: substitutions, insertions, deletions and pairs of up to
  two characters (``rn`` for ``m``), from aligned OCR and ground-truth lines.
- ``pack``: a model pack, the fitted models with a manifest of what they were fitted on, as a
  versioned gzip JSON file; ``load`` and ``save``.

Everything is standard library, at fitting and at run time, and deterministic: the same data
gives the same pack, byte for byte.
"""
