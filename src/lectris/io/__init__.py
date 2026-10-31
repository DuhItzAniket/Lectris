"""Readers for OCR output formats.

Each format has a module whose ``parse`` builds a ``Document`` from the content: ``hocr``,
``alto``, ``tsv`` (Tesseract's TSV), ``jsonio`` (LECTRIS's JSON, and flat lists of lines) and
``plain`` (plain text). ``parse`` and ``read`` here choose the reader, by name or by
``detect.detect``.

Readers treat their input as untrusted: they fetch nothing, resolve no external entity, and
raise ``lectris.errors.FormatError`` for content they cannot read. In every format, a word whose
text is empty after stripping is dropped, and so are lines without words and blocks without
lines; a line's or block's box is the one the format gives, else the union of its parts' boxes.
"""

import os
from pathlib import Path

from lectris.errors import FormatError
from lectris.io import alto, detect, hocr, jsonio, plain, tsv
from lectris.io._common import decode
from lectris.model import Document

__all__ = ["FORMATS", "parse", "read"]

FORMATS = ("hocr", "alto", "tsv", "json", "text")
"""The names of the formats LECTRIS reads, as ``parse`` and ``read`` take them."""

_TEXT_READERS = {"hocr": hocr.parse, "tsv": tsv.parse, "json": jsonio.parse, "text": plain.parse}


def parse(content: str | bytes, *, format: str | None = None) -> Document:
    """Read ``content`` in ``format``, or in the format ``detect.detect`` finds if it is ``None``.

    Bytes are decoded as UTF-8, or UTF-16 or UTF-32 when a byte order mark says so, except for
    ALTO, whose bytes go to the XML parser so that its encoding declaration applies.
    Raises ``ValueError`` for a format name not in ``FORMATS``, and ``FormatError`` for content
    the format's reader cannot read.
    """
    if format is not None and format not in FORMATS:
        raise ValueError(f"unknown format {format!r}; the formats are {', '.join(FORMATS)}")
    name = detect.detect(content) if format is None else format
    if name == "alto":
        return alto.parse(content)
    return _TEXT_READERS[name](decode(content) if isinstance(content, bytes) else content)


def read(path: str | os.PathLike[str], *, format: str | None = None) -> Document:
    """Read the file at ``path``, in ``format`` or in the format its content shows.

    The format is detected from the content, never from the file's extension. Raises
    ``OSError`` if the file cannot be read, and ``FormatError``, with the path in its message,
    if its content cannot.
    """
    try:
        return parse(Path(path).read_bytes(), format=format)
    except FormatError as error:
        raise FormatError(f"{os.fspath(path)}: {error}") from error
