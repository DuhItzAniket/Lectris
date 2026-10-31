import codecs
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from lectris import io
from lectris.errors import FormatError
from lectris.io import alto, hocr, jsonio, plain, tsv
from lectris.model import Document

DATA = Path(__file__).parent / "data" / "io"

READERS: list[tuple[str, str, Callable[[str], Document]]] = [
    ("two_columns.hocr", "hocr", hocr.parse),
    ("alto_v3.xml", "alto", alto.parse),
    ("tesseract.tsv", "tsv", tsv.parse),
    ("document.json", "json", jsonio.parse),
    ("flat_lines.json", "json", jsonio.parse),
    ("pages.txt", "text", plain.parse),
]


def test_the_formats() -> None:
    assert io.FORMATS == ("hocr", "alto", "tsv", "json", "text")


@pytest.mark.parametrize(("name", "format_name", "reader"), READERS)
def test_read_detects_the_format_from_the_content(
    tmp_path: Path, name: str, format_name: str, reader: Callable[[str], Document]
) -> None:
    copy = tmp_path / "scan.txt"  # an extension that says nothing true about the content
    shutil.copyfile(DATA / name, copy)
    expected = reader((DATA / name).read_text(encoding="utf-8"))
    assert io.read(copy) == expected
    assert io.read(str(copy)) == expected
    assert io.read(copy, format=format_name) == expected


@pytest.mark.parametrize(("name", "format_name", "reader"), READERS)
def test_parse_takes_text_or_bytes(
    name: str, format_name: str, reader: Callable[[str], Document]
) -> None:
    text = (DATA / name).read_text(encoding="utf-8")
    assert io.parse(text) == io.parse(text.encode("utf-8")) == reader(text)
    assert io.parse(text, format=format_name) == reader(text)


def test_a_format_overrides_detection() -> None:
    content = "\t".join(tsv.HEADER) + "\n"
    assert io.parse(content).pages == ()
    assert io.parse(content, format="text").text == " ".join(tsv.HEADER)


@pytest.mark.parametrize("format_name", ["HOCR", "xml", "txt", ""])
def test_an_unknown_format_is_a_value_error(tmp_path: Path, format_name: str) -> None:
    message = r"unknown format .*; the formats are hocr, alto, tsv, json, text"
    with pytest.raises(ValueError, match=message):
        io.parse("text", format=format_name)
    path = tmp_path / "page.txt"
    path.write_text("text", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        io.read(path, format=format_name)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xef\xbb\xbfByte order mark", "Byte order mark"),
        ("UTF-16 with a mark".encode("utf-16"), "UTF-16 with a mark"),
        (codecs.BOM_UTF16_BE + "UTF-16 big-endian".encode("utf-16-be"), "UTF-16 big-endian"),
        ("UTF-32 with a mark".encode("utf-32"), "UTF-32 with a mark"),
        (
            "caf\N{LATIN SMALL LETTER E WITH ACUTE}".encode(),
            "caf\N{LATIN SMALL LETTER E WITH ACUTE}",
        ),
    ],
)
def test_bytes_are_utf_8_unless_a_byte_order_mark_says_otherwise(
    data: bytes, expected: str
) -> None:
    assert io.parse(data).text == expected


def test_bytes_that_are_not_utf_8_are_refused() -> None:
    with pytest.raises(FormatError, match="not valid UTF-8: invalid continuation byte at byte 3"):
        io.parse(b"caf\xe9 au lait")


def test_alto_bytes_keep_their_encoding_declaration(tmp_path: Path) -> None:
    text = (DATA / "alto_v4.xml").read_text(encoding="utf-8")
    path = tmp_path / "latin.xml"
    path.write_bytes(text.replace('encoding="UTF-8"', 'encoding="ISO-8859-1"').encode("latin-1"))
    assert io.read(path) == alto.parse(text)


def test_a_file_that_cannot_be_read_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        io.read(tmp_path / "missing.hocr")


def test_a_format_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"pages": [{"blocks": 3}]}', encoding="utf-8")
    with pytest.raises(FormatError) as raised:
        io.read(path)
    assert str(raised.value) == f"{path}: pages[0].blocks: expected an array, not a number"
