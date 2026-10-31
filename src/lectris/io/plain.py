"""Read and write plain text: pages split by form feeds, blocks by blank lines.

A form feed (``\\f``) ends a page, so text that ends with one, as Tesseract's text output does,
has no empty page after it. Within a page, one or more blank lines (empty, or only whitespace)
separate blocks, and each other line is a line whose words are its text split on whitespace.
``\\r\\n`` and ``\\r`` are read as ``\\n``. Plain text has no boxes or confidences, and pages are
numbered by position.
"""

import re

from lectris.io._common import strip_bom
from lectris.model import Block, Document, Line, Page

_LINE_BREAK = re.compile(r"\r\n?")


def parse(text: str) -> Document:
    """Read plain text as a document of pages, blocks and lines. Any text can be read."""
    sources = _LINE_BREAK.sub("\n", strip_bom(text)).split("\f")
    if len(sources) > 1 and not sources[-1].strip():
        sources.pop()
    return Document(
        tuple(Page(_blocks(source), number=number) for number, source in enumerate(sources, 1))
    )


def dumps(document: Document) -> str:
    """``document`` as plain text: lines end with ``\\n``, blank lines separate blocks, form
    feeds separate pages.

    For a document ``parse`` returned whose last page has text, ``parse(dumps(document))``
    gives the same pages, blocks and words.
    """
    return "\f".join(page.text + "\n" if page.text else "" for page in document.pages)


def _blocks(source: str) -> tuple[Block, ...]:
    blocks: list[Block] = []
    lines: list[Line] = []
    for text in source.split("\n"):
        if text.strip():
            lines.append(Line.from_text(text))
        elif lines:
            blocks.append(Block(tuple(lines)))
            lines = []
    if lines:
        blocks.append(Block(tuple(lines)))
    return tuple(blocks)
