"""Tell an input's format from its first characters.

``detect`` looks at the first 64 KiB of the content, after a byte order mark and leading
whitespace, and applies these rules in order:

1. Markup (it starts with ``<``):
   - ``"alto"`` if the root element, after any XML declaration, comments, processing
     instructions and DOCTYPE, is named ``alto`` (with or without a namespace prefix);
   - else ``"hocr"`` if an element has ``ocr_page`` among its classes;
   - else ``"text"``: markup LECTRIS does not read.
2. ``"json"`` if it starts like a JSON object (``{`` then ``"`` or ``}``) or like an array of
   objects (``[`` then ``{`` or ``]``). Text such as ``[Illegible]`` or ``{sic}`` does not.
3. ``"tsv"`` if the first line is Tesseract's TSV header.
4. ``"text"`` otherwise.

Bytes are decoded as UTF-8, or UTF-16 or UTF-32 when a byte order mark says so; undecodable
bytes do not stop detection.
"""

import re

from lectris.io._common import decode, strip_bom
from lectris.io.tsv import HEADER

PREFIX = 64 * 1024
"""How many characters (or bytes) of the content ``detect`` looks at."""

# What can come before XML's root element: a declaration, processing instructions, comments, and
# a DOCTYPE with or without an internal subset.
_PROLOG_ITEM = re.compile(
    r"\s*(?:<\?.*?\?>|<!--.*?-->|<!DOCTYPE(?:[^\[>]|\[.*?\])*>)", re.DOTALL | re.IGNORECASE
)
_ROOT = re.compile(r"\s*<(?:[A-Za-z_][\w.-]*:)?([A-Za-z_][\w.-]*)")
# An attribute named class, in any case as HTML allows, with ocr_page among its values.
_OCR_PAGE = re.compile(r"""(?<![\w-])(?i:class)\s*=\s*["']?[^"'<>]*(?<![\w-])ocr_page(?![\w-])""")
_JSON_START = re.compile(r'\{\s*["}]|\[\s*[{\]]')
_TSV_HEADER = "\t".join(HEADER)


def detect(content: str | bytes) -> str:
    """The format of ``content``: ``"hocr"``, ``"alto"``, ``"tsv"``, ``"json"`` or ``"text"``.

    See the module's documentation for the rules. Any content gets an answer: ``"text"`` is the
    fallback, and the format's reader decides whether the content is valid.
    """
    head = content[:PREFIX]
    text = strip_bom(head) if isinstance(head, str) else decode(head, errors="replace")
    start = text.lstrip()
    if start.startswith("<"):
        if _root_name(start) == "alto":
            return "alto"
        return "hocr" if _OCR_PAGE.search(start) else "text"
    if _JSON_START.match(start):
        return "json"
    if text.split("\n", 1)[0].rstrip() == _TSV_HEADER:
        return "tsv"
    return "text"


def _root_name(markup: str) -> str | None:
    """The local name of the first element in ``markup``, after the XML prolog."""
    position = 0
    while match := _PROLOG_ITEM.match(markup, position):
        position = match.end()
    root = _ROOT.match(markup, position)
    return root.group(1) if root else None
