"""Read hOCR: the HTML or XHTML that Tesseract, Kraken and other OCR engines write.

The structure comes from the elements' classes and the geometry from their ``title`` properties
(``bbox x0 y0 x1 y1; x_wconf 93``):

- ``ocr_page`` is a page. Its ``bbox`` gives the page's width and height. ``ppageno`` counts
  pages from 0, so the page's ``number`` is ``ppageno + 1``; without it, the page's position.
- ``ocr_par`` is a block. An ``ocr_carea`` with no ``ocr_par`` inside is one block; one with
  paragraphs is only their container. Lines outside any block form a block of their own.
- ``ocr_line``, ``ocrx_line``, ``ocr_header``, ``ocr_caption`` and ``ocr_textfloat`` are lines
  (Tesseract writes the last three for lines in headings, pull-outs and captions). One that holds
  other lines is only their container.
- ``ocrx_word`` is a word. Its text is everything inside it, with entities decoded and inner tags
  such as ``<strong>`` flattened; ``x_wconf`` (0 to 100) becomes its confidence over 100.
  Words outside any line form a line of their own. A line with no ``ocrx_word`` inside takes its
  words from its text, without word boxes.

A missing ``bbox`` gives no box, and a line or block then takes the union of its parts' boxes.
hOCR has no line confidence, so a line's confidence is ``None``. Text outside any word or line,
in the ``<head>`` for example, is not read.

The input may be XHTML or HTML. An element ends at its end tag, as in XHTML, with two of HTML's
implied ends: a void element such as ``<br>`` has none, and an ``ocr_par`` or ``ocr_carea`` that
starts while a ``<p>`` is open ends that ``<p>``, so an unclosed ``<p class="ocr_par">`` does not
take in the paragraphs after it.
"""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import override

from lectris.errors import FormatError
from lectris.io._common import (
    make_block,
    make_box,
    make_line,
    make_word,
    parse_integer,
    parse_number,
    parse_percentage,
    strip_bom,
)
from lectris.model import Block, Box, Document, Line, Page, Word

_PAGE = "ocr_page"
_AREA = "ocr_carea"
_PARAGRAPH = "ocr_par"
_LINES = frozenset({"ocr_line", "ocrx_line", "ocr_header", "ocr_caption", "ocr_textfloat"})
_WORD = "ocrx_word"
# Classes whose element, when it starts, ends an open <p>.
_ENDS_A_PARAGRAPH = frozenset({_PARAGRAPH, _AREA})

# Elements HTML closes without an end tag.
_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

_BBOX_VALUES = 4
# A property runs to the next semicolon that is not inside double quotes.
_PROPERTY = re.compile(r'(?:[^;"]|"[^"]*(?:"|$))+')


@dataclass(slots=True, eq=False)
class _Element:
    tag: str
    classes: frozenset[str]
    title: str
    ident: str
    source_line: int
    children: list["_Element | str"] = field(default_factory=list)

    def describe(self) -> str:
        """The element, for an error message: its hOCR class, id and line in the input."""
        kind = next((name for name in sorted(self.classes) if name.startswith("ocr")), self.tag)
        named = f"{kind} {self.ident!r}" if self.ident else kind
        return f"{named} (input line {self.source_line})"


class _TreeBuilder(HTMLParser):
    """Builds a tree of elements; see the module's documentation for where an element ends."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("", frozenset(), "", "", 0)
        self._open = [self.root]

    def _element(self, tag: str, attributes: list[tuple[str, str | None]]) -> _Element:
        values = {name: value or "" for name, value in attributes}
        return _Element(
            tag,
            frozenset(values.get("class", "").split()),
            values.get("title", ""),
            values.get("id", ""),
            self.getpos()[0],
        )

    def _start(self, element: _Element, *, opens: bool) -> None:
        if element.classes & _ENDS_A_PARAGRAPH:
            self._close("p")
        self._open[-1].children.append(element)
        if opens:
            self._open.append(element)

    def _close(self, tag: str) -> None:
        """Close the innermost open ``tag`` and everything opened inside it, if one is open."""
        for depth in range(len(self._open) - 1, 0, -1):
            if self._open[depth].tag == tag:
                del self._open[depth:]
                return

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(self._element(tag, attrs), opens=tag not in _VOID)

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(self._element(tag, attrs), opens=False)

    @override
    def handle_endtag(self, tag: str) -> None:
        self._close(tag)

    @override
    def handle_data(self, data: str) -> None:
        self._open[-1].children.append(data)


def parse(content: str) -> Document:
    """Read an hOCR document.

    Raises ``FormatError`` if the input has no ``ocr_page`` element, or a ``bbox``, ``x_wconf``
    or ``ppageno`` that is not a valid number.
    """
    builder = _TreeBuilder()
    builder.feed(strip_bom(content))
    builder.close()
    pages = _find(builder.root, _PAGE)
    if not pages:
        raise FormatError("no element has the class ocr_page: the input is not hOCR")
    try:
        return Document(tuple(_page(page, position) for position, page in enumerate(pages, 1)))
    except RecursionError:
        raise FormatError("the hOCR elements are nested too deeply to read") from None


def _page(element: _Element, position: int) -> Page:
    properties = _properties(element)
    bbox = _bbox(element, properties)
    number = position
    if "ppageno" in properties:
        ppageno = parse_integer(properties["ppageno"], f"{element.describe()}: ppageno")
        if ppageno < 0:
            raise FormatError(f"{element.describe()}: ppageno is negative: {ppageno}")
        number = ppageno + 1
    tokens: list[_Token] = []
    _walk(element, tokens, in_block=False)
    return Page(
        _group(tokens),
        width=bbox.width if bbox is not None else None,
        height=bbox.height if bbox is not None else None,
        number=number,
    )


@dataclass(frozen=True, slots=True)
class _Open:
    """A block element starts."""

    box: Box | None


@dataclass(frozen=True, slots=True)
class _Close:
    """The block element that last started ends."""


@dataclass(frozen=True, slots=True)
class _Break:
    """A content area starts or ends: lines on either side are not one block."""


type _Token = _Open | _Close | _Break | Line | Word


def _walk(element: _Element, tokens: list[_Token], *, in_block: bool) -> None:
    """Append the page's structure to ``tokens``: blocks' bounds, lines and loose words."""
    for child in element.children:
        if isinstance(child, str):
            continue
        classes = child.classes
        if _WORD in classes:
            word = _word(child)
            if word is not None:
                tokens.append(word)
        elif classes & _LINES and not _find(child, *_LINES):
            line = _line(child)
            if line is not None:
                tokens.append(line)
        elif not in_block and (
            _PARAGRAPH in classes or (_AREA in classes and not _find(child, _PARAGRAPH))
        ):
            tokens.append(_Open(_bbox(child, _properties(child))))
            _walk(child, tokens, in_block=True)
            tokens.append(_Close())
        elif not in_block and _AREA in classes:
            tokens.append(_Break())
            _walk(child, tokens, in_block=False)
            tokens.append(_Break())
        else:
            _walk(child, tokens, in_block=in_block)


def _group(tokens: list[_Token]) -> tuple[Block, ...]:
    """The blocks ``tokens`` describe: loose words make a line, loose lines make a block."""
    blocks: list[Block] = []
    lines: list[Line] = []
    words: list[Word] = []

    def end_line() -> None:
        line = make_line(words)
        if line is not None:
            lines.append(line)
        words.clear()

    def end_block(box: Box | None) -> None:
        end_line()
        block = make_block(lines, box)
        if block is not None:
            blocks.append(block)
        lines.clear()

    block_box: Box | None = None
    for token in tokens:
        if isinstance(token, Word):
            words.append(token)
        elif isinstance(token, Line):
            end_line()
            lines.append(token)
        elif isinstance(token, _Open):
            end_block(None)
            block_box = token.box
        elif isinstance(token, _Close):
            end_block(block_box)
            block_box = None
        else:
            end_block(None)
    end_block(None)
    return tuple(blocks)


def _line(element: _Element) -> Line | None:
    properties = _properties(element)
    word_elements = _find(element, _WORD)
    if word_elements:
        words = [word for word in map(_word, word_elements) if word is not None]
    else:
        words = [Word(part) for part in _text(element).split()]
    return make_line(words, _bbox(element, properties))


def _word(element: _Element) -> Word | None:
    properties = _properties(element)
    confidence = None
    if "x_wconf" in properties:
        confidence = parse_percentage(properties["x_wconf"], f"{element.describe()}: x_wconf")
    return make_word(_text(element), _bbox(element, properties), confidence)


def _properties(element: _Element) -> dict[str, str]:
    """The element's ``title`` properties: each key and the rest of its text."""
    properties: dict[str, str] = {}
    for match in _PROPERTY.finditer(element.title):
        parts = match.group().split(None, 1)
        if parts and parts[0] not in properties:
            properties[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    return properties


def _bbox(element: _Element, properties: dict[str, str]) -> Box | None:
    if "bbox" not in properties:
        return None
    what = f"{element.describe()}: bbox"
    values = properties["bbox"].split()
    if len(values) != _BBOX_VALUES:
        raise FormatError(f"{what} needs four numbers, not {properties['bbox']!r}")
    x0, y0, x1, y1 = (parse_number(value, what) for value in values)
    return make_box(x0, y0, x1, y1, what)


def _find(element: _Element, *classes: str) -> list[_Element]:
    """The outermost elements inside ``element`` with any of ``classes``, in document order."""
    wanted = frozenset(classes)
    found: list[_Element] = []
    pending = list(reversed(element.children))
    while pending:
        child = pending.pop()
        if isinstance(child, str):
            continue
        if child.classes & wanted:
            found.append(child)
        else:
            pending.extend(reversed(child.children))
    return found


def _text(element: _Element) -> str:
    """Every piece of text inside ``element``, in document order."""
    pieces: list[str] = []
    pending = list(reversed(element.children))
    while pending:
        child = pending.pop()
        if isinstance(child, str):
            pieces.append(child)
        else:
            pending.extend(reversed(child.children))
    return "".join(pieces)
