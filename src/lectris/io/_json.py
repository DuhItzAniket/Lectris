"""What the JSON readers share: loading, and checking each value with its path in the errors.

A path names where a value is, such as ``pages[0].blocks[2].lines[1].box``, so an error says
which value is at fault.
"""

import json
import math
from typing import Any

from lectris.errors import FormatError
from lectris.io._common import strip_bom
from lectris.model import Box, Point

_BOX_VALUES = 4
_POINT_VALUES = 2
_MIN_POLYGON_POINTS = 3


def load(content: str) -> Any:
    """``content`` parsed as JSON, or ``FormatError`` (``NaN`` and ``Infinity`` included)."""
    try:
        return json.loads(strip_bom(content), parse_constant=_refuse_constant)
    except (ValueError, RecursionError) as error:  # JSONDecodeError is a ValueError
        raise FormatError(f"not valid JSON: {error}") from None


def _refuse_constant(name: str) -> None:
    raise FormatError(f"not valid JSON: {name} is not a number JSON allows")


def box(value: Any, path: str) -> Box | None:
    """``[x0, y0, x1, y1]`` as a box; ``null`` is no box."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != _BOX_VALUES:
        raise FormatError(f"{path}: a box is an array [x0, y0, x1, y1], not {kind(value)}")
    x0, y0, x1, y1 = (number(item, f"{path}[{index}]") for index, item in enumerate(value))
    try:
        return Box(x0, y0, x1, y1)
    except ValueError as error:
        raise FormatError(f"{path}: {error}") from None


def polygon(value: Any, path: str) -> tuple[Point, ...] | None:
    """``[[x, y], ...]``, at least three points, as a polygon; ``null`` is none."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) < _MIN_POLYGON_POINTS:
        raise FormatError(
            f"{path}: a polygon is an array of at least 3 points [x, y], not {kind(value)}"
            + (f" of {len(value)}" if isinstance(value, list) else "")
        )
    points: list[Point] = []
    for index, point in enumerate(value):
        where = f"{path}[{index}]"
        if not isinstance(point, list) or len(point) != _POINT_VALUES:
            raise FormatError(f"{where}: a point is an array [x, y], not {kind(point)}")
        points.append((number(point[0], f"{where}[0]"), number(point[1], f"{where}[1]")))
    return tuple(points)


def unit(value: Any, path: str, what: str = "a confidence") -> float | None:
    """A number from 0 to 1 (``what`` names it in the error); ``null`` is ``None``."""
    if value is None:
        return None
    result = number(value, path)
    if not 0 <= result <= 1:
        raise FormatError(f"{path}: {what} is between 0 and 1, not {value!r}")
    return result


def size(data: dict[str, Any], key: str, path: str) -> float | None:
    """A page's width or height at ``key``: a number that is not negative, or ``None``."""
    value = data.get(key)
    if value is None:
        return None
    result = number(value, f"{path}.{key}")
    if result < 0:
        raise FormatError(f"{path}.{key}: a page's size is not negative, not {value!r}")
    return result


def number(value: Any, path: str) -> float:
    """A JSON number (not a boolean) that is finite, as a float."""
    if type(value) not in (int, float):
        raise FormatError(f"{path}: expected a number, not {kind(value)}")
    try:
        result = float(value)
    except OverflowError:
        result = math.inf
    if not math.isfinite(result):
        raise FormatError(f"{path}: the number is out of range")
    return result


def string(value: Any, path: str) -> str:
    """A JSON string."""
    if not isinstance(value, str):
        raise FormatError(f"{path}: expected a string, not {kind(value)}")
    return value


def optional_string(value: Any, path: str) -> str | None:
    """A JSON string, or ``None`` for ``null``, a missing value or the empty string."""
    if value is None:
        return None
    return string(value, path) or None


def obj(value: Any, path: str) -> dict[str, Any]:
    """A JSON object."""
    if not isinstance(value, dict):
        raise FormatError(f"{path or 'the top level'}: expected an object, not {kind(value)}")
    return value


def array(value: Any, path: str) -> list[tuple[int, Any]]:
    """The items of the JSON array ``value``, with their indexes."""
    if not isinstance(value, list):
        raise FormatError(f"{path}: expected an array, not {kind(value)}")
    return list(enumerate(value))


def required(data: dict[str, Any], key: str, path: str) -> Any:
    """The value at ``key``, which must be there."""
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


def kind(value: Any) -> str:
    """The JSON kind of ``value``, for an error message."""
    return _KINDS.get(type(value), type(value).__name__)
