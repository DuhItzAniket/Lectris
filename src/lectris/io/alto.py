"""Read ALTO XML, versions 2, 3 and 4.

The root element is ``alto``, in the namespace of ALTO 2, 3 or 4
(``http://www.loc.gov/standards/alto/ns-v4#`` and its ``-v2#`` and ``-v3#`` siblings) or in no
namespace. Each ``Layout/Page`` is a page:

- ``WIDTH`` and ``HEIGHT`` give its size, and ``PHYSICAL_IMG_NR`` its number (else its position).
- Its ``TextBlock`` elements are its blocks, including those inside a ``ComposedBlock``. They are
  read space by space in the page's reading order, ``TopMargin``, ``LeftMargin``, ``PrintSpace``,
  ``RightMargin``, ``BottomMargin`` (the schema lists ``PrintSpace`` last), and in document order
  within a space. A ``TextBlock`` or ``ComposedBlock`` placed directly in the ``Page``, outside
  any space (the schema has no place for one, but some producers write it), is read too, where
  it stands in document order among the page's spaces.
- A ``TextLine`` is a line, a ``String`` a word (``CONTENT``, and ``WC``, already 0 to 1, as its
  confidence). ``SP`` is the space between words and is skipped. ``HYP`` marks a hyphen at the
  line's end: its ``CONTENT`` (``-`` when it has none) is appended to the line's last word, and
  its box joins that word's box. ``SUBS_CONTENT`` is not used: joining hyphenated words is the
  text rules' work, and they record it.

A box is ``HPOS, VPOS, HPOS + WIDTH, VPOS + HEIGHT`` when all four attributes are present, and
missing otherwise. Coordinates are kept in the document's ``MeasurementUnit`` (``pixel``,
``mm10`` or ``inch1200``), not converted. ALTO has no line confidence, so a line's confidence
is ``None``.

The input is untrusted. It is parsed by the standard library's expat, which fetches no external
DTD or entity. A document that declares entities is refused. So is one that names an external
DTD without declaring itself ``standalone="yes"``: expat would skip, without a word, every
reference to an entity that DTD might declare, and a ``CONTENT`` would lose text. In a
standalone document, a reference to an undeclared entity is an error.
"""

import xml.etree.ElementTree as ET
from xml.parsers import expat

from lectris.errors import FormatError
from lectris.io._common import (
    make_block,
    make_box,
    make_line,
    make_word,
    parse_confidence,
    parse_number,
    strip_bom,
)
from lectris.model import Block, Box, Document, Line, Page, Word

NAMESPACES = (
    "http://www.loc.gov/standards/alto/ns-v2#",
    "http://www.loc.gov/standards/alto/ns-v3#",
    "http://www.loc.gov/standards/alto/ns-v4#",
)
"""The namespaces of ALTO 2, 3 and 4. A document in no namespace is read too."""

_SPACES = ("TopMargin", "LeftMargin", "PrintSpace", "RightMargin", "BottomMargin")


def parse(content: str | bytes) -> Document:
    """Read an ALTO document.

    Pass ``bytes`` to let the XML declaration's encoding apply; ``str`` is read as it is.
    Raises ``FormatError`` if the input is not well-formed XML, declares entities or depends on
    an external DTD, if its root is not an ALTO 2-4 ``alto`` element or it has no ``Page``, or
    if an attribute that holds a number does not.
    """
    root, source_lines = _parse_xml(content)
    namespace, _, name = root.tag[1:].partition("}") if root.tag[:1] == "{" else ("", "", root.tag)
    if name != "alto":
        raise FormatError(f"the root element is <{name}>, not <alto>: the input is not ALTO")
    if namespace and namespace not in NAMESPACES:
        raise FormatError(
            f"the <alto> element is in the namespace {namespace!r}; "
            "LECTRIS reads ALTO 2, 3 and 4, or ALTO with no namespace"
        )
    reader = _Reader(f"{{{namespace}}}" if namespace else "", source_lines)
    pages = root.findall(f"{reader.prefix}Layout/{reader.prefix}Page")
    if not pages:
        raise FormatError("the ALTO document has no Layout/Page element")
    return Document(tuple(reader.page(page, position) for position, page in enumerate(pages, 1)))


def _parse_xml(content: str | bytes) -> tuple[ET.Element, dict[ET.Element, int]]:
    """The document's root element, and each element's line in the input.

    Expat is driven directly, rather than through ``ET.XMLParser``, so that entity declarations
    and external DTDs can be refused before anything is expanded or skipped.
    """
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator="}")
    source_lines: dict[ET.Element, int] = {}

    def start(name: str, attributes: dict[str, str]) -> None:
        element = builder.start(
            _qualified(name), {_qualified(key): value for key, value in attributes.items()}
        )
        source_lines[element] = parser.CurrentLineNumber

    def end(name: str) -> None:
        builder.end(_qualified(name))

    def refuse_declaration(name: str, *_: object) -> None:
        raise FormatError(
            f"the document declares the entity {name!r}; "
            "LECTRIS does not read XML that declares entities"
        )

    def refuse_external_dtd() -> int:
        raise FormatError(
            'the document names an external DTD and is not standalone="yes"; LECTRIS does not '
            "load external DTDs, so it could not expand the entities one may declare"
        )

    parser.buffer_text = True
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = builder.data
    parser.EntityDeclHandler = refuse_declaration
    parser.NotStandaloneHandler = refuse_external_dtd
    try:
        parser.Parse(strip_bom(content) if isinstance(content, str) else content, True)
    except expat.ExpatError as error:
        raise FormatError(
            f"not well-formed XML: {expat.ErrorString(error.code)} "
            f"(line {error.lineno}, column {error.offset})"
        ) from None
    return builder.close(), source_lines


def _qualified(name: str) -> str:
    """Expat's ``namespace}local`` as ElementTree's ``{namespace}local``."""
    return "{" + name if "}" in name else name


class _Reader:
    """Reads the elements of one document, whose ALTO elements' tags start with ``prefix``."""

    def __init__(self, prefix: str, source_lines: dict[ET.Element, int]) -> None:
        self.prefix = prefix
        self._source_lines = source_lines

    def page(self, element: ET.Element, position: int) -> Page:
        number = position
        physical = self._number(element, "PHYSICAL_IMG_NR")
        if physical is not None:
            if not physical.is_integer():
                what = self._what(element, "PHYSICAL_IMG_NR")
                raise FormatError(f"{what} is not a whole number: {physical!r}")
            number = int(physical)
        blocks = [
            block
            for region in self._regions(element)
            for text_block in region.iter(self.prefix + "TextBlock")
            if (block := self.block(text_block)) is not None
        ]
        return Page(
            tuple(blocks),
            width=self._number(element, "WIDTH"),
            height=self._number(element, "HEIGHT"),
            number=number,
        )

    def _regions(self, page: ET.Element) -> list[ET.Element]:
        """The page's spaces and the blocks outside them, in the order their text is read.

        The children keep their document order, except that the spaces among them are taken in
        reading order: each space's place goes to the next space in ``_SPACES`` order.
        """
        ranks = {self.prefix + name: rank for rank, name in enumerate(_SPACES)}
        loose = {self.prefix + "TextBlock", self.prefix + "ComposedBlock"}
        children = [child for child in page if child.tag in ranks or child.tag in loose]
        spaces = iter(
            sorted((child for child in children if child.tag in ranks), key=lambda c: ranks[c.tag])
        )
        return [next(spaces) if child.tag in ranks else child for child in children]

    def block(self, element: ET.Element) -> Block | None:
        lines = [
            line
            for text_line in element.findall(self.prefix + "TextLine")
            if (line := self.line(text_line)) is not None
        ]
        return make_block(lines, self._box(element))

    def line(self, element: ET.Element) -> Line | None:
        words: list[Word] = []
        for child in element:
            if child.tag == self.prefix + "String":
                wc = child.get("WC")
                confidence = (
                    None if wc is None else parse_confidence(wc.strip(), self._what(child, "WC"))
                )
                word = make_word(child.get("CONTENT", ""), self._box(child), confidence)
                if word is not None:
                    words.append(word)
            elif child.tag == self.prefix + "HYP":
                hyphen = (child.get("CONTENT") or "").strip() or "-"
                words = self._hyphenate(words, hyphen, self._box(child))
        return make_line(words, self._box(element))

    @staticmethod
    def _hyphenate(words: list[Word], hyphen: str, box: Box | None) -> list[Word]:
        """``words`` with ``hyphen`` appended to the last one, or as a word if there is none."""
        if not words:
            return [Word(hyphen, box)]
        last = words[-1]
        joined = last.box.union(box) if last.box is not None and box is not None else last.box
        return [*words[:-1], Word(last.text + hyphen, joined, last.confidence)]

    def _box(self, element: ET.Element) -> Box | None:
        hpos, vpos, width, height = (
            self._number(element, name) for name in ("HPOS", "VPOS", "WIDTH", "HEIGHT")
        )
        if hpos is None or vpos is None or width is None or height is None:
            return None
        return make_box(hpos, vpos, hpos + width, vpos + height, self._what(element, "box"))

    def _number(self, element: ET.Element, attribute: str) -> float | None:
        value = element.get(attribute)
        if value is None:
            return None
        return parse_number(value.strip(), self._what(element, attribute))

    def _what(self, element: ET.Element, attribute: str) -> str:
        """``attribute`` of ``element``, for an error message."""
        name = element.tag.rpartition("}")[2]
        ident = element.get("ID")
        named = f"{name} {ident!r}" if ident else name
        return f"{named} (input line {self._source_lines.get(element, '?')}): {attribute}"
