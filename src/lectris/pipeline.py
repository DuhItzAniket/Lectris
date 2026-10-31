"""The pipeline: layout, then the text rules in order, with every edit kept.

``clean()`` takes a ``Document`` (from ``lectris.io``) or plain text, arranges each page into
blocks in reading order (when the profile asks for it and the lines have boxes), and runs each
block's text through the profile's rules. The result holds the cleaned text, each block's source
and revisions, and the layout document.
"""

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from lectris.confidence import block_confidence
from lectris.edits import Edit, Revision
from lectris.io import plain
from lectris.io._common import strip_bom
from lectris.layout import arrange
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document


def rule_id(rule: Callable[..., Revision]) -> str:
    """A rule's stable id: its module's last name and its own, as in ``"hyphenation.join"``."""
    return f"{rule.__module__.rsplit('.', 1)[-1]}.{rule.__name__}"


@dataclass(frozen=True, slots=True)
class Step:
    """One text rule in a profile, with its options.

    ``lexicon`` steps receive the pipeline's lexicon, when one is given, as their ``lexicon``
    option.
    """

    rule: Callable[..., Revision]
    options: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    lexicon: bool = False

    @property
    def id(self) -> str:
        return rule_id(self.rule)

    def apply(self, text: str, lexicon: Lexicon | None) -> Revision:
        options = dict(self.options)
        if self.lexicon and lexicon is not None:
            options["lexicon"] = lexicon
        return self.rule(text, **options)


@dataclass(frozen=True, slots=True)
class Profile:
    """A named configuration: whether to arrange the layout, and the text rules in order."""

    name: str
    description: str
    steps: tuple[Step, ...]
    arrange: bool = True

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(step.id for step in self.steps)


@dataclass(frozen=True, slots=True)
class Change:
    """One edit, located: the page, the block within the page, and the rule's step number.

    The edit's offsets are in the text the rule received, which is the block's text after the
    steps before it.
    """

    page: int
    block: int
    step: int
    edit: Edit


@dataclass(frozen=True, slots=True)
class CleanBlock:
    """A block after the text rules: where it is, what it was, what it is now, and why."""

    page: int
    index: int
    box: Box | None
    confidence: float | None
    source: str
    text: str
    revisions: tuple[tuple[str, Revision], ...]

    @property
    def edits(self) -> tuple[Edit, ...]:
        return tuple(edit for _, revision in self.revisions for edit in revision.edits)


@dataclass(frozen=True, slots=True)
class Result:
    """What ``clean()`` returns."""

    profile: str
    document: Document
    blocks: tuple[CleanBlock, ...]

    @property
    def text(self) -> str:
        """The cleaned text: blocks separated by a blank line; empty blocks left out."""
        return "\n\n".join(block.text for block in self.blocks if block.text)

    def changes(self) -> Iterator[Change]:
        """Every edit, block by block and step by step."""
        for block in self.blocks:
            for step, (_, revision) in enumerate(block.revisions):
                for edit in revision.edits:
                    yield Change(block.page, block.index, step, edit)

    def counts(self) -> dict[str, int]:
        """How many edits each rule made, in the profile's order (rules with none included)."""
        counts: dict[str, int] = {}
        for block in self.blocks:
            for rule, revision in block.revisions:
                counts[rule] = counts.get(rule, 0) + len(revision.edits)
        return counts


def run_rules(
    text: str, steps: tuple[Step, ...], *, lexicon: Lexicon | None = None
) -> tuple[str, tuple[tuple[str, Revision], ...]]:
    """``text`` through each step in order: the final text and each step's revision."""
    revisions: list[tuple[str, Revision]] = []
    for step in steps:
        revision = step.apply(text, lexicon)
        revisions.append((step.id, revision))
        text = revision.text
    return text, tuple(revisions)


def _clean_block(
    source: str,
    block: Block,
    *,
    page: int,
    index: int,
    profile: Profile,
    lexicon: Lexicon | None,
) -> CleanBlock:
    text, revisions = run_rules(source, profile.steps, lexicon=lexicon)
    return CleanBlock(
        page=page,
        index=index,
        box=block.box,
        confidence=block_confidence(block),
        source=source,
        text=text,
        revisions=revisions,
    )


_LINE: Final = re.compile(r"([^\r\n]*)(\r\n|\r|\n|$)")


def _raw_blocks(text: str) -> list[list[str]]:
    """Each page's blocks of ``text`` as they are written, spacing and line breaks included.

    Pages and blocks are split exactly as ``lectris.io.plain.parse`` splits them (form feeds,
    then lines with nothing but whitespace), so the n-th raw block is the n-th parsed one.
    """
    sources = strip_bom(text).split("\f")
    if len(sources) > 1 and not sources[-1].strip():
        sources.pop()
    pages: list[list[str]] = []
    for source in sources:
        blocks: list[str] = []
        current = ""
        for match in _LINE.finditer(source):
            line, end = match.group(1), match.group(2)
            if line.strip():
                current += line + end
            elif current:
                blocks.append(current.rstrip("\r\n"))
                current = ""
            if not end:
                break
        if current:
            blocks.append(current.rstrip("\r\n"))
        pages.append(blocks)
    return pages


def clean(
    source: Document | str,
    *,
    profile: "Profile | str" = "standard",
    lexicon: Lexicon | None = None,
) -> Result:
    """Clean OCR output: arrange each page, then run every block's text through the rules.

    ``source`` is a ``Document`` (see ``lectris.io.read``) or plain text, whose blocks are
    separated by blank lines and pages by form feeds. The rules receive plain text's blocks as
    they are written, so a change to their spacing or line breaks is recorded like any other;
    a document's blocks reach them as their lines' text (``Block.text``). ``profile`` is a
    ``Profile`` or the name of one in ``lectris.profiles.PROFILES``. A ``lexicon`` makes the
    rules that can use one more precise (de-hyphenation, confusions in words); without one they
    rely on their local evidence.
    """
    from lectris.profiles import get  # noqa: PLC0415 - the profiles import this module

    chosen = get(profile) if isinstance(profile, str) else profile
    if isinstance(source, str):
        document = plain.parse(source)
        raw = _raw_blocks(source)
        blocks = tuple(
            _clean_block(
                raw[page_index][index],
                block,
                page=page.number,
                index=index,
                profile=chosen,
                lexicon=lexicon,
            )
            for page_index, page in enumerate(document.pages)
            for index, block in enumerate(page.blocks)
        )
        return Result(chosen.name, document, blocks)
    document = source
    if chosen.arrange:
        document = Document(tuple(arrange(page) for page in document.pages))
    blocks = tuple(
        _clean_block(
            block.text, block, page=page.number, index=index, profile=chosen, lexicon=lexicon
        )
        for page in document.pages
        for index, block in enumerate(page.blocks)
    )
    return Result(chosen.name, document, blocks)
