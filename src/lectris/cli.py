"""The ``lectris`` command: clean OCR output, evaluate it against a reference, list the rules."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from lectris import io, metrics, report
from lectris.errors import LectrisError
from lectris.io._common import decode
from lectris.io.detect import detect
from lectris.lexicon import Lexicon
from lectris.model import Document
from lectris.pipeline import clean
from lectris.profiles import PROFILES

_REPORT_FORMATS = ("json", "markdown")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lectris",
        description="OCR output, read back into clean, ordered text, with every change recorded.",
    )
    parser.add_argument("--version", action="version", version=f"lectris {version('lectris')}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    run = commands.add_parser("clean", help="clean an OCR file and write its text")
    run.add_argument("input", help="hOCR, ALTO, TSV, JSON or text; - reads standard input")
    run.add_argument("-f", "--format", choices=io.FORMATS, help="the input's format (detected)")
    run.add_argument("-p", "--profile", choices=tuple(PROFILES), default="standard")
    run.add_argument("-o", "--output", type=Path, help="write the text here (standard output)")
    run.add_argument("-l", "--lexicon", type=Path, help="a word list: one word per line")
    run.add_argument("-r", "--report", type=Path, help="write the report of every edit here")
    run.add_argument(
        "--report-format", choices=_REPORT_FORMATS, default="json", help="the report's format"
    )
    run.add_argument(
        "-s", "--summary", action="store_true", help="print each rule's edit count to stderr"
    )

    score = commands.add_parser("eval", help="character and word error rates against a reference")
    score.add_argument("reference", type=Path, help="the correct text")
    score.add_argument("hypothesis", type=Path, help="the text to score")
    score.add_argument(
        "--normalize", action="store_true", help="NFC and collapsed whitespace on both sides"
    )
    score.add_argument("--ignore-case", action="store_true", help="compare case-insensitively")

    commands.add_parser("rules", help="list the profiles and the rules each one runs")
    return parser


def _write(text: str) -> None:
    """Write ``text`` to standard output as UTF-8, whatever the console's or the system's code
    page (Windows writes a pipe or a file in its ANSI code page by default)."""
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _read_input(argument: str, format_name: str | None) -> Document | str:
    """The input as a document, or as text when it is plain text.

    Plain text goes to ``clean()`` as a string, so the rules see its spacing and line breaks as
    they are written and record what they change (a document keeps only its words).
    """
    data = sys.stdin.buffer.read() if argument == "-" else Path(argument).read_bytes()
    chosen = format_name or detect(data)
    if chosen == "text":
        return decode(data)
    if argument == "-":
        return io.parse(data, format=chosen)
    return io.read(argument, format=chosen)


def _clean(arguments: argparse.Namespace) -> int:
    document = _read_input(arguments.input, arguments.format)
    lexicon = None if arguments.lexicon is None else Lexicon.from_file(arguments.lexicon)
    result = clean(document, profile=arguments.profile, lexicon=lexicon)
    text = result.text + "\n" if result.text else ""
    if arguments.output is None:
        _write(text)
    else:
        arguments.output.write_text(text, encoding="utf-8", newline="\n")
    if arguments.report is not None:
        rendered = (
            report.to_json(result)
            if arguments.report_format == "json"
            else report.to_markdown(result)
        )
        arguments.report.write_text(rendered, encoding="utf-8", newline="\n")
    if arguments.summary:
        sys.stderr.write(report.summary(result))
    return 0


def _eval(arguments: argparse.Namespace) -> int:
    # The same decoding as the readers: UTF-8, a byte order mark (UTF-8, 16 or 32) dropped.
    reference = decode(arguments.reference.read_bytes())
    hypothesis = decode(arguments.hypothesis.read_bytes())
    options = {"normalize": arguments.normalize, "ignore_case": arguments.ignore_case}
    for name, counts in (
        ("CER", metrics.char_errors(reference, hypothesis, **options)),
        ("WER", metrics.word_errors(reference, hypothesis, **options)),
    ):
        sys.stdout.write(
            f"{name} {counts.rate:.4f}  ({counts.errors} errors in {counts.reference_length}: "
            f"{counts.substitutions} substituted, {counts.deletions} deleted, "
            f"{counts.insertions} inserted)\n"
        )
    return 0


def _rules() -> int:
    for profile in PROFILES.values():
        sys.stdout.write(f"{profile.name}: {profile.description}\n")
        for step in profile.steps:
            sys.stdout.write(f"  {step.id}\n")
        sys.stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit status (0 done, 1 an input it cannot read, 2 usage)."""
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "clean":
            return _clean(arguments)
        if arguments.command == "eval":
            return _eval(arguments)
        return _rules()
    except (LectrisError, OSError, ValueError) as error:
        sys.stderr.write(f"lectris: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
