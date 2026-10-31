from pathlib import Path

import pytest

from lectris.io import tsv
from lectris.io.detect import PREFIX, detect

DATA = Path(__file__).parent / "data" / "io"
ALTO_V4 = "http://www.loc.gov/standards/alto/ns-v4#"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("two_columns.hocr", "hocr"),
        ("alto_v2.xml", "alto"),
        ("alto_v3.xml", "alto"),
        ("alto_v4.xml", "alto"),
        ("tesseract.tsv", "tsv"),
        ("document.json", "json"),
        ("flat_lines.json", "json"),
        ("pages.txt", "text"),
    ],
)
def test_the_samples(name: str, expected: str) -> None:
    content = (DATA / name).read_bytes()
    assert detect(content) == expected
    assert detect(content.decode("utf-8")) == expected


@pytest.mark.parametrize(
    "content",
    [
        "<alto/>",
        f'<alto xmlns="{ALTO_V4}"><Layout/></alto>',
        f'<a:alto xmlns:a="{ALTO_V4}"/>',
        '<?xml version="1.0"?>\n<!-- made by hand -->\n<?pi data?>\n<alto/>',
        "<!DOCTYPE alto [\n<!ELEMENT alto ANY>\n]>\n<alto/>",
        '  \n<!DOCTYPE alto SYSTEM "alto.dtd"><alto/>',
    ],
)
def test_xml_with_an_alto_root_is_alto(content: str) -> None:
    assert detect(content) == "alto"


@pytest.mark.parametrize(
    "content",
    [
        "<html><body><div class='ocr_page' title='bbox 0 0 1 1'></div></body></html>",
        '<div class="ocr_page">',
        "<DIV CLASS=ocr_page>",
        '<?xml version="1.0"?><html><div class="first ocr_page last">',
        "<!DOCTYPE html>\n<html><head><title>alto</title></head><body class='ocr_page'>",
    ],
)
def test_html_with_an_ocr_page_class_is_hocr(content: str) -> None:
    assert detect(content) == "hocr"


@pytest.mark.parametrize(
    "content",
    [
        "<html><body><p>No OCR here.</p></body></html>",
        "<div class='ocr_pages'>",
        "<div class='x-ocr_page'>",
        "<meta name='ocr-capabilities' content='ocr_page ocr_line'/>",
        "<mets:mets xmlns:mets='http://www.loc.gov/METS/'/>",
        "<altogether/>",
    ],
)
def test_other_markup_is_text(content: str) -> None:
    assert detect(content) == "text"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"pages": []}', "json"),
        ('  {\n  "lines": []}', "json"),
        ("{}", "json"),
        ('[{"text": "a"}]', "json"),
        ("[ ]", "json"),
        ("[Illegible] the rest of the line", "text"),
        ("{sic} a correction", "text"),
        ("[1, 2]", "text"),
    ],
)
def test_json_objects_and_arrays_of_objects(content: str, expected: str) -> None:
    assert detect(content) == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("\t".join(tsv.HEADER) + "\n1\t1\t0\t0\t0\t0\t0\t0\t10\t10\t-1\t\n", "tsv"),
        ("\t".join(tsv.HEADER) + "\r\n", "tsv"),
        ("\t".join(tsv.HEADER), "tsv"),
        (" ".join(tsv.HEADER) + "\n", "text"),
        ("\n" + "\t".join(tsv.HEADER), "text"),
    ],
)
def test_the_tsv_header(content: str, expected: str) -> None:
    assert detect(content) == expected


@pytest.mark.parametrize("content", ["", "   \n\t", "Plain prose, nothing more.", "<"])
def test_anything_else_is_text(content: str) -> None:
    assert detect(content) == "text"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xef\xbb\xbf<alto/>", "alto"),
        ('<?xml version="1.0" encoding="UTF-16"?><alto/>'.encode("utf-16"), "alto"),
        ("<alto/>".encode("utf-16-be"), "text"),  # UTF-16 without a byte order mark
        ('{"lines": []}'.encode("utf-32"), "json"),
        (b"\xff\xfe\xfd not text in any encoding", "text"),
        (b"\x80\x81 caf\xe9", "text"),
    ],
)
def test_bytes(data: bytes, expected: str) -> None:
    assert detect(data) == expected


def test_only_the_prefix_is_read() -> None:
    padding = "<!--" + " " * PREFIX + "-->"
    assert detect(f"<html>{padding}<div class='ocr_page'>") == "text"
    assert detect(f"<html><div class='ocr_page'>{padding}") == "hocr"
