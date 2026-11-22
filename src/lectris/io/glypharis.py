"""Read GLYPHARIS's JSON: one page, as ``OCRResult.to_dict`` writes it (GLYPHARIS 1.0).

.. code-block:: json

    {"glypharis_version": "1.0.0", "model_version": "glypharis-1.0.0",
     "width": 1240, "height": 1754, "text": "Orchards bloom late",
     "lines": [{"text": "Orchards bloom late", "confidence": 0.97, "det_score": 0.91,
                "bbox": [100, 120, 880, 160],
                "polygon": [[100, 121], [880, 120], [880, 160], [100, 160]],
                "quad": [[100, 121], [880, 120], [880, 160], [100, 160]]}],
     "seconds": {"detect": 0.41, "recognise": 0.88}}

What is read, and where it goes:

- ``glypharis_version`` (required) and ``model_version``: the document's ``Engine``, named
  ``"glypharis"``. An empty ``model_version`` (GLYPHARIS's default) is no model.
- ``width`` and ``height``: the page's size.
- ``lines`` (required), in GLYPHARIS's reading order, as one page of one block; the layout steps
  split it into paragraphs. Each line's ``text`` (required) is split on whitespace into words
  without boxes, since GLYPHARIS reads whole lines. A line whose text is empty is dropped.
- A line's ``confidence`` (the recognizer's, calibrated) is the line's confidence, ``det_score``
  its detection score, ``polygon`` its polygon, and ``bbox`` its box; without ``bbox``, the box is
  the polygon's bounds.
- A line's ``chars``, when present (proposed in LECTRIS's ADR-0003; GLYPHARIS 1.0 does not write
  it): one entry per character of its text, spaces included, ``{"c": ..., "p": ..., "alt":
  [[character, probability], ...]}``, become its words' glyphs, each with ``p`` as its confidence
  and ``alt`` as its alternatives (sorted from the most to the least likely, and without ``c``
  itself; ``""`` is the CTC blank). The characters must spell the text; the spaces' entries are
  not kept, since words hold no spaces.

What is ignored, deliberately: the top-level ``text`` (the lines' text joined, which would repeat
them), ``seconds`` (timings), a line's ``quad`` (the rectangle around its polygon, which is kept)
and ``confidence_at`` (confidences at other temperatures, for GLYPHARIS's own diagnostics). Other
keys are ignored too, so a later GLYPHARIS that adds keys is still read. Every error names the
path of the value at fault, such as ``lines[3].det_score``.
"""

import re
from typing import Any

from lectris.errors import FormatError
from lectris.io._common import make_block
from lectris.io._json import (
    array,
    box,
    load,
    obj,
    optional_string,
    polygon,
    required,
    size,
    string,
    unit,
)
from lectris.model import Box, Document, Engine, Glyph, Line, Page, Point, Word

ENGINE = "glypharis"
"""The name of the engine a GLYPHARIS document is read as coming from."""

READ = frozenset({"glypharis_version", "model_version", "width", "height", "lines"})
"""The top-level keys this reader reads."""

IGNORED = frozenset({"text", "seconds"})
"""The top-level keys GLYPHARIS writes that this reader ignores, deliberately."""

LINE_READ = frozenset({"text", "confidence", "det_score", "bbox", "polygon"})
"""The keys of a line this reader reads."""

LINE_IGNORED = frozenset({"quad", "confidence_at"})
"""The keys of a line GLYPHARIS writes that this reader ignores, deliberately."""

LINE_PROPOSED = frozenset({"chars"})
"""The keys of a line this reader reads that GLYPHARIS 1.0 does not write (ADR-0003)."""

_WORD = re.compile(r"\S+")
_PAIR = 2


def parse(content: str) -> Document:
    """Read a page of GLYPHARIS output (see the module's documentation).

    Raises ``FormatError`` if the input is not JSON, is not an object with ``glypharis_version``
    and ``lines``, or holds a value of the wrong kind; the message names its path.
    """
    data = obj(load(content), "")
    version = string(required(data, "glypharis_version", ""), "glypharis_version")
    if not version.strip():
        raise FormatError("glypharis_version: the version is not empty")
    engine = Engine(ENGINE, version, optional_string(data.get("model_version"), "model_version"))
    lines = (
        _line(item, f"lines[{index}]")
        for index, item in array(required(data, "lines", ""), "lines")
    )
    block = make_block(line for line in lines if line is not None)
    page = Page(
        () if block is None else (block,),
        width=size(data, "width", ""),
        height=size(data, "height", ""),
    )
    return Document((page,), engine=engine)


def _line(value: Any, path: str) -> Line | None:
    line = obj(value, path)
    text = string(required(line, "text", path), f"{path}.text")
    glyphs = _chars(line["chars"], text, f"{path}.chars") if "chars" in line else None
    words = tuple(
        Word(
            match.group(),
            glyphs=None if glyphs is None else glyphs[match.start() : match.end()],
        )
        for match in _WORD.finditer(text)
    )
    if not words:
        return None
    outline = polygon(line.get("polygon"), f"{path}.polygon")
    bounds = box(line["bbox"], f"{path}.bbox") if "bbox" in line else _bounds(outline)
    return Line(
        words,
        bounds,
        unit(line.get("confidence"), f"{path}.confidence"),
        outline,
        unit(line.get("det_score"), f"{path}.det_score", "a detection score"),
    )


def _chars(value: Any, text: str, path: str) -> tuple[Glyph, ...] | None:
    """A line's ``chars`` as one glyph per character of ``text``; ``null`` is none."""
    if value is None:
        return None
    glyphs: list[Glyph] = []
    for index, item in array(value, path):
        where = f"{path}[{index}]"
        entry = obj(item, where)
        char = string(required(entry, "c", where), f"{where}.c")
        if len(char) != 1:
            raise FormatError(f"{where}.c: one character, not {char!r}")
        readings: list[tuple[str, float]] = []
        for position, pair in array(entry.get("alt", []), f"{where}.alt"):
            at = f"{where}.alt[{position}]"
            if not isinstance(pair, list) or len(pair) != _PAIR:
                raise FormatError(f"{at}: an alternative is [character, probability]")
            reading = string(pair[0], f"{at}[0]")
            if len(reading) > 1:
                raise FormatError(f"{at}[0]: one character or '', not {reading!r}")
            probability = unit(pair[1], f"{at}[1]", "a probability")
            if probability is None:
                raise FormatError(f"{at}[1]: expected a number, not null")
            if reading != char and reading not in {r for r, _ in readings}:
                readings.append((reading, probability))
        readings.sort(key=lambda pair: -pair[1])
        glyphs.append(Glyph(char, unit(entry.get("p"), f"{where}.p"), tuple(readings)))
    spelled = "".join(glyph.char for glyph in glyphs)
    if spelled != text:
        raise FormatError(f"{path}: the characters spell {spelled!r}, not the text {text!r}")
    return tuple(glyphs)


def _bounds(outline: tuple[Point, ...] | None) -> Box | None:
    """The box around ``outline``, or ``None`` if there is none."""
    if outline is None:
        return None
    xs = [x for x, _ in outline]
    ys = [y for _, y in outline]
    return Box(min(xs), min(ys), max(xs), max(ys))
