"""Read and write LECTRIS's JSON form of a document, and read the flat line lists OCR engines write.

LECTRIS's own form mirrors the model:

.. code-block:: json

    {"pages": [{"number": 1, "width": 1200, "height": 1600, "blocks": [
        {"box": [40, 60, 580, 140], "lines": [
            {"box": [40, 60, 580, 92], "confidence": null, "words": [
                {"text": "Barges", "box": [40, 60, 150, 92], "confidence": 0.93}]}]}]}]}

A box is ``[x0, y0, x1, y1]``, the corners, not a width and height. ``number`` defaults to the
page's position; ``width``, ``height``, ``box`` and ``confidence`` are optional. ``blocks``,
``lines`` and a word's ``text`` are required. A line gives either ``words`` or ``text``; from
``text`` its words are the text split on whitespace, without boxes. A line's or a block's box
that is absent is the union of its parts' boxes, while ``null`` means it has none (which is what
``dumps`` writes for a missing box, so that reading back gives the same document).

Three keys are optional and written only when the document has them: a line's ``polygon``
(``[[x, y], ...]``, at least three points) and ``detection`` (the detector's score, 0 to 1), and
the top-level ``engine`` (``{"name": ..., "version": ..., "model": ...}``, only ``name``
required).

The flat form is ``{"lines": [...]}`` or a top-level list of lines, each
``{"text": ..., "bbox": [x0, y0, x1, y1], "confidence": ...}``, with only ``text`` required. It is
read as one page of one block holding every line, in the order given; the block's box is the
union of the lines' boxes. The layout steps split that block into paragraphs.

Keys that LECTRIS does not know are ignored. Every error names where it is, as a path such as
``pages[0].blocks[2].lines[1].box``.
"""

import json
from typing import Any

from lectris.errors import FormatError
from lectris.io._common import make_block, make_word
from lectris.io._json import (
    array,
    box,
    kind,
    load,
    obj,
    optional_string,
    polygon,
    required,
    size,
    string,
    unit,
)
from lectris.model import Block, Box, Document, Engine, Line, Page, Word, union_of


def parse(content: str) -> Document:
    """Read a document in LECTRIS's JSON form, or in the flat form of a list of lines.

    Raises ``FormatError`` if the input is not JSON (``NaN`` and ``Infinity`` included), or does
    not have the structure above; the message names the path of the value at fault.
    """
    data = load(content)
    if isinstance(data, list):
        return _flat(data, "")
    if isinstance(data, dict):
        if "pages" in data and "lines" in data:
            raise FormatError("the document has both 'pages' and 'lines'; give one")
        if "pages" in data:
            pages = array(data["pages"], "pages")
            return Document(
                tuple(_page(value, f"pages[{index}]", index + 1) for index, value in pages),
                engine=_engine(data.get("engine"), "engine"),
            )
        if "lines" in data:
            return _flat(data["lines"], "lines")
        raise FormatError("the top-level object needs 'pages' or 'lines'")
    raise FormatError(f"the top level is {kind(data)}, not an object or an array")


def dumps(document: Document, *, indent: int | None = 2) -> str:
    """``document`` in LECTRIS's JSON form; ``parse`` reads it back as an equal document.

    Every key is written; missing boxes and confidences are ``null``. A line's ``polygon`` and
    ``detection``, and the document's ``engine``, are written only when they are set. ``indent``
    is passed to ``json.dumps`` (``None`` for one line). Text is written as UTF-8, not as ``\\u``
    escapes.
    """
    data: dict[str, Any] = {"pages": [_page_data(page) for page in document.pages]}
    if document.engine is not None:
        engine = document.engine
        data["engine"] = {"name": engine.name, "version": engine.version, "model": engine.model}
    return json.dumps(data, indent=indent, ensure_ascii=False, allow_nan=False)


def _engine(value: Any, path: str) -> Engine | None:
    if value is None:
        return None
    data = obj(value, path)
    name = string(required(data, "name", path), f"{path}.name")
    if not name.strip():
        raise FormatError(f"{path}.name: an engine's name is not empty")
    return Engine(
        name,
        optional_string(data.get("version"), f"{path}.version"),
        optional_string(data.get("model"), f"{path}.model"),
    )


def _flat(value: Any, path: str) -> Document:
    """The flat form's array of lines at ``path``, as one page of one block."""
    lines = (_line(item, f"{path}[{index}]", box_key="bbox") for index, item in array(value, path))
    block = make_block(line for line in lines if line is not None)
    return Document((Page(() if block is None else (block,)),))


def _page(value: Any, path: str, position: int) -> Page:
    page = obj(value, path)
    number = page.get("number", position)
    if type(number) is not int:
        raise FormatError(f"{path}.number: a page number is a whole number, not {kind(number)}")
    blocks = (
        _block(item, f"{path}.blocks[{index}]")
        for index, item in array(required(page, "blocks", path), f"{path}.blocks")
    )
    return Page(
        tuple(block for block in blocks if block is not None),
        width=size(page, "width", path),
        height=size(page, "height", path),
        number=number,
    )


def _block(value: Any, path: str) -> Block | None:
    block = obj(value, path)
    lines = (
        _line(item, f"{path}.lines[{index}]", box_key="box")
        for index, item in array(required(block, "lines", path), f"{path}.lines")
    )
    kept = tuple(line for line in lines if line is not None)
    if not kept:
        return None
    return Block(kept, _box_or_union(block, "box", path, [line.box for line in kept]))


def _line(value: Any, path: str, *, box_key: str) -> Line | None:
    line = obj(value, path)
    if "words" in line and "text" in line:
        raise FormatError(f"{path}: a line gives 'words' or 'text', not both")
    if "words" in line:
        items = array(line["words"], f"{path}.words")
        words = [word for index, item in items if (word := _word(item, f"{path}.words[{index}]"))]
    elif "text" in line:
        words = [Word(part) for part in string(line["text"], f"{path}.text").split()]
    else:
        raise FormatError(f"{path}: a line needs 'words' or 'text'")
    if not words:
        return None
    own_form = box_key == "box"
    return Line(
        tuple(words),
        _box_or_union(line, box_key, path, [word.box for word in words]),
        unit(line.get("confidence"), f"{path}.confidence"),
        polygon(line.get("polygon"), f"{path}.polygon") if own_form else None,
        unit(line.get("detection"), f"{path}.detection", "a detection score") if own_form else None,
    )


def _word(value: Any, path: str) -> Word | None:
    word = obj(value, path)
    text = string(required(word, "text", path), f"{path}.text")
    return make_word(
        text,
        box(word.get("box"), f"{path}.box"),
        unit(word.get("confidence"), f"{path}.confidence"),
    )


def _box_or_union(data: dict[str, Any], key: str, path: str, parts: list[Box | None]) -> Box | None:
    """The box at ``key`` when the key is present (``null`` is no box), else the parts' union."""
    if key in data:
        return box(data[key], f"{path}.{key}")
    return union_of(parts)


def _page_data(page: Page) -> dict[str, Any]:
    return {
        "number": page.number,
        "width": page.width,
        "height": page.height,
        "blocks": [
            {"box": _box_data(block.box), "lines": [_line_data(line) for line in block.lines]}
            for block in page.blocks
        ],
    }


def _line_data(line: Line) -> dict[str, Any]:
    data: dict[str, Any] = {
        "box": _box_data(line.box),
        "confidence": line.confidence,
        "words": [
            {"text": word.text, "box": _box_data(word.box), "confidence": word.confidence}
            for word in line.words
        ],
    }
    if line.polygon is not None:
        data["polygon"] = [list(point) for point in line.polygon]
    if line.detection is not None:
        data["detection"] = line.detection
    return data


def _box_data(value: Box | None) -> list[float] | None:
    return None if value is None else [value.x0, value.y0, value.x1, value.y1]
