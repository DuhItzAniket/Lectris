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

The flat form is ``{"lines": [...]}`` or a top-level list of lines, each
``{"text": ..., "bbox": [x0, y0, x1, y1], "confidence": ...}``, with only ``text`` required. It is
read as one page of one block holding every line, in the order given; the block's box is the
union of the lines' boxes. The layout steps split that block into paragraphs.

Keys that LECTRIS does not know are ignored. Every error names where it is, as a path such as
``pages[0].blocks[2].lines[1].box``.
"""

import json
import math
from typing import Any

from lectris.errors import FormatError
from lectris.io._common import make_block, make_word, strip_bom
from lectris.model import Block, Box, Document, Line, Page, Word, union_of

_BOX_VALUES = 4


def parse(content: str) -> Document:
    """Read a document in LECTRIS's JSON form, or in the flat form of a list of lines.

    Raises ``FormatError`` if the input is not JSON (``NaN`` and ``Infinity`` included), or does
    not have the structure above; the message names the path of the value at fault.
    """
    try:
        data = json.loads(strip_bom(content), parse_constant=_refuse_constant)
    except (ValueError, RecursionError) as error:  # JSONDecodeError is a ValueError
        raise FormatError(f"not valid JSON: {error}") from None
    if isinstance(data, list):
        return _flat(data, "")
    if isinstance(data, dict):
        if "pages" in data and "lines" in data:
            raise FormatError("the document has both 'pages' and 'lines'; give one")
        if "pages" in data:
            pages = _array(data["pages"], "pages")
            return Document(
                tuple(_page(value, f"pages[{index}]", index + 1) for index, value in pages)
            )
        if "lines" in data:
            return _flat(data["lines"], "lines")
        raise FormatError("the top-level object needs 'pages' or 'lines'")
    raise FormatError(f"the top level is {_kind(data)}, not an object or an array")


def dumps(document: Document, *, indent: int | None = 2) -> str:
    """``document`` in LECTRIS's JSON form; ``parse`` reads it back as an equal document.

    Every key is written; missing boxes and confidences are ``null``. ``indent`` is passed to
    ``json.dumps`` (``None`` for one line). Text is written as UTF-8, not as ``\\u`` escapes.
    """
    data = {"pages": [_page_data(page) for page in document.pages]}
    return json.dumps(data, indent=indent, ensure_ascii=False, allow_nan=False)


def _refuse_constant(name: str) -> None:
    raise FormatError(f"not valid JSON: {name} is not a number JSON allows")


def _flat(value: Any, path: str) -> Document:
    """The flat form's array of lines at ``path``, as one page of one block."""
    lines = (_line(item, f"{path}[{index}]", box_key="bbox") for index, item in _array(value, path))
    block = make_block(line for line in lines if line is not None)
    return Document((Page(() if block is None else (block,)),))


def _page(value: Any, path: str, position: int) -> Page:
    page = _object(value, path)
    number = page.get("number", position)
    if type(number) is not int:
        raise FormatError(f"{path}.number: a page number is a whole number, not {_kind(number)}")
    blocks = (
        _block(item, f"{path}.blocks[{index}]")
        for index, item in _array(_required(page, "blocks", path), f"{path}.blocks")
    )
    return Page(
        tuple(block for block in blocks if block is not None),
        width=_size(page, "width", path),
        height=_size(page, "height", path),
        number=number,
    )


def _block(value: Any, path: str) -> Block | None:
    block = _object(value, path)
    lines = (
        _line(item, f"{path}.lines[{index}]", box_key="box")
        for index, item in _array(_required(block, "lines", path), f"{path}.lines")
    )
    kept = tuple(line for line in lines if line is not None)
    if not kept:
        return None
    return Block(kept, _box_or_union(block, "box", path, [line.box for line in kept]))


def _line(value: Any, path: str, *, box_key: str) -> Line | None:
    line = _object(value, path)
    if "words" in line and "text" in line:
        raise FormatError(f"{path}: a line gives 'words' or 'text', not both")
    if "words" in line:
        items = _array(line["words"], f"{path}.words")
        words = [word for index, item in items if (word := _word(item, f"{path}.words[{index}]"))]
    elif "text" in line:
        words = [Word(part) for part in _string(line["text"], f"{path}.text").split()]
    else:
        raise FormatError(f"{path}: a line needs 'words' or 'text'")
    if not words:
        return None
    return Line(
        tuple(words),
        _box_or_union(line, box_key, path, [word.box for word in words]),
        _confidence(line.get("confidence"), f"{path}.confidence"),
    )


def _word(value: Any, path: str) -> Word | None:
    word = _object(value, path)
    text = _string(_required(word, "text", path), f"{path}.text")
    box = _box(word.get("box"), f"{path}.box")
    return make_word(text, box, _confidence(word.get("confidence"), f"{path}.confidence"))


def _box_or_union(data: dict[str, Any], key: str, path: str, parts: list[Box | None]) -> Box | None:
    """The box at ``key`` when the key is present (``null`` is no box), else the parts' union."""
    if key in data:
        return _box(data[key], f"{path}.{key}")
    return union_of(parts)


def _box(value: Any, path: str) -> Box | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != _BOX_VALUES:
        raise FormatError(f"{path}: a box is an array [x0, y0, x1, y1], not {_kind(value)}")
    x0, y0, x1, y1 = (_number(item, f"{path}[{index}]") for index, item in enumerate(value))
    try:
        return Box(x0, y0, x1, y1)
    except ValueError as error:
        raise FormatError(f"{path}: {error}") from None


def _confidence(value: Any, path: str) -> float | None:
    if value is None:
        return None
    confidence = _number(value, path)
    if not 0 <= confidence <= 1:
        raise FormatError(f"{path}: a confidence is between 0 and 1, not {value!r}")
    return confidence


def _size(data: dict[str, Any], key: str, path: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    size = _number(value, f"{path}.{key}")
    if size < 0:
        raise FormatError(f"{path}.{key}: a page's size is not negative, not {value!r}")
    return size


def _number(value: Any, path: str) -> float:
    if type(value) not in (int, float):
        raise FormatError(f"{path}: expected a number, not {_kind(value)}")
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    if not math.isfinite(number):
        raise FormatError(f"{path}: the number is out of range")
    return number


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise FormatError(f"{path}: expected a string, not {_kind(value)}")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError(f"{path or 'the top level'}: expected an object, not {_kind(value)}")
    return value


def _array(value: Any, path: str) -> list[tuple[int, Any]]:
    """The items of the array ``value``, with their indexes."""
    if not isinstance(value, list):
        raise FormatError(f"{path}: expected an array, not {_kind(value)}")
    return list(enumerate(value))


def _required(data: dict[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise FormatError(f"{path}: {key!r} is missing" if path else f"{key!r} is missing")
    return data[key]


_KINDS: dict[type, str] = {
    dict: "an object",
    list: "an array",
    str: "a string",
    bool: "a boolean",
    int: "a number",
    float: "a number",
    type(None): "null",
}


def _kind(value: Any) -> str:
    """The JSON kind of ``value``, for an error message."""
    return _KINDS.get(type(value), type(value).__name__)


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
    return {
        "box": _box_data(line.box),
        "confidence": line.confidence,
        "words": [
            {"text": word.text, "box": _box_data(word.box), "confidence": word.confidence}
            for word in line.words
        ],
    }


def _box_data(box: Box | None) -> list[float] | None:
    return None if box is None else [box.x0, box.y0, box.x1, box.y1]
