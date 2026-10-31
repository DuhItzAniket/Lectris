import codecs
import io
import json
from importlib.metadata import version
from pathlib import Path

import pytest

from lectris.cli import main

DATA = Path(__file__).parent / "data" / "io"
FI = chr(0xFB01)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.strip() == f"lectris {version('lectris')}"


def test_clean_writes_the_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write(tmp_path / "page.txt", f"An exam-\nple of {FI}ne text.\n")
    assert main(["clean", str(source)]) == 0
    assert capsys.readouterr().out == "An example of fine text.\n"


def test_the_text_is_written_as_utf8(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    source = write(tmp_path / "page.txt", "Renée wrote ŝ and ő.\n")
    assert main(["clean", str(source)]) == 0
    assert capsysbinary.readouterr().out == "Renée wrote ŝ and ő.\n".encode()


def test_clean_to_a_file_with_a_report_and_a_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = write(tmp_path / "page.txt", f"An exam-\nple of {FI}ne text.\n")
    output, json_report = tmp_path / "out.txt", tmp_path / "report.json"
    status = main(
        [
            "clean",
            str(source),
            "-o",
            str(output),
            "-r",
            str(json_report),
            "--summary",
            "-p",
            "conservative",
        ]
    )
    assert status == 0
    assert output.read_text(encoding="utf-8") == "An example\nof fine text.\n"
    assert json.loads(json_report.read_text(encoding="utf-8"))["profile"] == "conservative"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "hyphenation.join" in captured.err


def test_every_change_to_plain_text_is_in_the_report(tmp_path: Path) -> None:
    source = write(tmp_path / "page.txt", "Two  spaces and   three.\n    Indented line.\n")
    json_report = tmp_path / "report.json"
    assert main(["clean", str(source), "-p", "conservative", "-r", str(json_report)]) == 0
    data = json.loads(json_report.read_text(encoding="utf-8"))
    block = data["blocks"][0]
    assert block["source"] == "Two  spaces and   three.\n    Indented line."
    assert block["text"] == "Two spaces and three.\nIndented line."
    assert data["counts"]["whitespace.collapse"] == 2
    assert data["counts"]["whitespace.trim"] == 1


def test_a_markdown_report(tmp_path: Path) -> None:
    source = write(tmp_path / "page.txt", f"{FI}ne\n")
    markdown = tmp_path / "report.md"
    assert main(["clean", str(source), "-r", str(markdown), "--report-format", "markdown"]) == 0
    assert markdown.read_text(encoding="utf-8").startswith("# LECTRIS report")


def test_clean_reads_standard_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdin = io.TextIOWrapper(io.BytesIO(f"two  spaces and a {FI}nal word\n".encode()))
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["clean", "-"]) == 0
    assert capsys.readouterr().out == "two spaces and a final word\n"


@pytest.mark.parametrize("name", sorted(path.name for path in DATA.iterdir()))
def test_clean_reads_every_sample_format(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["clean", str(DATA / name)]) == 0
    assert capsys.readouterr().out.strip()


def test_a_lexicon_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write(tmp_path / "page.txt", "a well-\nknown result\n")
    words = write(tmp_path / "words.txt", "well-known 5\nresult 2\n")
    assert main(["clean", str(source), "--lexicon", str(words)]) == 0
    assert capsys.readouterr().out == "a well-known result\n"


def test_an_input_that_cannot_be_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = write(tmp_path / "broken.json", '{"pages": [{"blocks": 3}]}')
    assert main(["clean", str(broken)]) == 1
    assert capsys.readouterr().err.startswith("lectris: ")


def test_a_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["clean", str(tmp_path / "missing.hocr")]) == 1
    assert "lectris: " in capsys.readouterr().err


def test_eval(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    reference = write(tmp_path / "reference.txt", "kitten sat")
    hypothesis = write(tmp_path / "hypothesis.txt", "sitting sat")
    assert main(["eval", str(reference), str(hypothesis)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("CER 0.3000  (3 errors in 10:")
    assert out[1].startswith("WER 0.5000  (1 errors in 2:")


def test_eval_with_normalisation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    reference = write(tmp_path / "reference.txt", "Same  Text\n")
    hypothesis = write(tmp_path / "hypothesis.txt", "same text")
    assert main(["eval", str(reference), str(hypothesis), "--normalize", "--ignore-case"]) == 0
    assert capsys.readouterr().out.startswith("CER 0.0000")


def test_eval_ignores_a_byte_order_mark(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    reference = tmp_path / "reference.txt"
    reference.write_bytes(codecs.BOM_UTF8 + b"the same text")
    hypothesis = write(tmp_path / "hypothesis.txt", "the same text")
    assert main(["eval", str(reference), str(hypothesis)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("CER 0.0000")
    assert out[1].startswith("WER 0.0000")


def test_rules_lists_every_profile(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rules"]) == 0
    out = capsys.readouterr().out
    for name in ("conservative:", "standard:", "aggressive:", "  hyphenation.join"):
        assert name in out


def test_a_command_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main([])
    assert stop.value.code == 2
    assert "COMMAND" in capsys.readouterr().err
