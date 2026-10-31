import json

from lectris import report
from lectris.pipeline import clean

SOFT_HYPHEN = chr(0x00AD)
FI = chr(0xFB01)


def test_the_summary_lists_each_rule_and_the_total() -> None:
    result = clean(f"An exam-\nple of {FI}ne text.", profile="conservative")
    lines = report.summary(result).splitlines()
    assert lines[0].split() == ["whitespace.line_breaks", "0"]
    assert ["unicode.ligatures", "1"] in [line.split() for line in lines]
    assert lines[-1].split() == ["total", "2"]


def test_the_json_report_holds_every_edit() -> None:
    result = clean(f"An exam-\nple of {FI}ne text.\n\nSecond block.")
    data = json.loads(report.to_json(result))
    assert data["format"] == report.FORMAT_VERSION
    assert data["profile"] == "standard"
    assert [block["index"] for block in data["blocks"]] == [0, 1]
    first = data["blocks"][0]
    assert first["source"] == f"An exam-\nple of {FI}ne text."
    assert first["text"] == "An example of fine text."
    rules = [edit["rule"] for edit in first["edits"]]
    assert rules == ["unicode.ligatures", "hyphenation.join", "unwrap.join_lines"]
    ligature = first["edits"][0]
    assert (ligature["before"], ligature["after"]) == (FI, "fi")
    assert sum(len(block["edits"]) for block in data["blocks"]) == sum(data["counts"].values())


def test_the_json_report_keeps_characters_readable() -> None:
    result = clean(f"{FI}ne")
    assert FI in report.to_json(result)


def test_the_markdown_report() -> None:
    result = clean(f"An exam-\nple of {FI}ne text.")
    markdown = report.to_markdown(result)
    assert markdown.startswith("# LECTRIS report (standard)")
    assert "| `unicode.ligatures` | 1 |" in markdown
    assert f"`unicode.ligatures`: `{FI}` → `fi`" in markdown


def test_the_markdown_report_spells_out_what_cannot_be_seen() -> None:
    result = clean(f"line one\n~~~ ,,, ' ' |||\nexam{SOFT_HYPHEN}\nple", profile="aggressive")
    markdown = report.to_markdown(result)
    assert "⏎" in markdown
    assert "[soft hyphen]" in markdown


def test_the_markdown_report_stops_at_its_limit() -> None:
    result = clean("  ".join(f"word{i}  ." for i in range(30)))
    markdown = report.to_markdown(result, limit=3)
    assert markdown.count("\n- page") == 3
    assert "the JSON report has all" in markdown


def test_a_report_with_no_edits_says_so() -> None:
    assert "No edits." in report.to_markdown(clean("Clean already."))
