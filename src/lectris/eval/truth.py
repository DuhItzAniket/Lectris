"""A page's ground truth: its lines, each with its text and, when known, its box.

One page per JSON file:

.. code-block:: json

    {"page": "a1b2c3", "width": 1240, "height": 1754,
     "lines": [{"text": "Orchards bloom late", "box": [100, 120, 880, 160]}, ...]}

``page`` and ``lines`` are required, and each line's ``text``; ``box`` is ``[x0, y0, x1, y1]``
or ``null``. A line's text is kept as it is: the scoring normalises both sides alike.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lectris.errors import FormatError
from lectris.io._common import decode
from lectris.io._json import array, box, load, obj, required, size, string
from lectris.model import Box


@dataclass(frozen=True, slots=True)
class TruthLine:
    """One line of the ground truth."""

    text: str
    box: Box | None = None


@dataclass(frozen=True, slots=True)
class TruthPage:
    """A page's ground truth: its id and its lines, in their reading order."""

    page: str
    lines: tuple[TruthLine, ...]
    width: float | None = None
    height: float | None = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


def parse(content: str) -> TruthPage:
    """A ground-truth page from its JSON (see the module's documentation)."""
    data = obj(load(content), "")
    page = string(required(data, "page", ""), "page")
    lines = tuple(
        _line(item, f"lines[{index}]")
        for index, item in array(required(data, "lines", ""), "lines")
    )
    return TruthPage(page, lines, size(data, "width", ""), size(data, "height", ""))


def read(path: str | Path) -> TruthPage:
    """The ground-truth page in the file at ``path``."""
    try:
        return parse(decode(Path(path).read_bytes()))
    except FormatError as error:
        raise FormatError(f"{path}: {error}") from error


def dumps(page: TruthPage) -> str:
    """``page`` as JSON; ``parse`` reads it back as an equal page."""
    import json  # noqa: PLC0415 - only writing needs it

    data: dict[str, Any] = {
        "page": page.page,
        "width": page.width,
        "height": page.height,
        "lines": [
            {
                "text": line.text,
                "box": None
                if line.box is None
                else [line.box.x0, line.box.y0, line.box.x1, line.box.y1],
            }
            for line in page.lines
        ],
    }
    return json.dumps(data, ensure_ascii=False, allow_nan=False)


def _line(value: Any, path: str) -> TruthLine:
    line = obj(value, path)
    text = string(required(line, "text", path), f"{path}.text")
    return TruthLine(text, box(line.get("box"), f"{path}.box"))
