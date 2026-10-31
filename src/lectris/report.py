"""Reports of what ``clean()`` changed: a summary, JSON for tools, Markdown for people."""

import json
from typing import Any, Final

from lectris.model import Box
from lectris.pipeline import Result

#: The JSON report's format version; it changes when a field changes meaning or goes away.
FORMAT_VERSION: Final = 1


def summary(result: Result) -> str:
    """One line per rule with its number of edits, then the total."""
    counts = result.counts()
    width = max((len(rule) for rule in counts), default=0)
    lines = [f"{rule:<{width}}  {count:>6}" for rule, count in counts.items()]
    total = sum(counts.values())
    lines.append(f"{'total':<{width}}  {total:>6}")
    return "\n".join(lines) + "\n"


def to_dict(result: Result) -> dict[str, Any]:
    """The report as plain data: the profile, each block's source and text, and its edits.

    An edit's ``start`` and ``end`` are offsets in the text its rule received: the block's
    source after the steps before it.
    """
    return {
        "format": FORMAT_VERSION,
        "profile": result.profile,
        "counts": result.counts(),
        "blocks": [
            {
                "page": block.page,
                "index": block.index,
                "box": None if block.box is None else list(_box(block.box)),
                "confidence": block.confidence,
                "source": block.source,
                "text": block.text,
                "edits": [
                    {
                        "step": step,
                        "rule": edit.rule,
                        "start": edit.start,
                        "end": edit.end,
                        "before": edit.before,
                        "after": edit.after,
                    }
                    for step, (_, revision) in enumerate(block.revisions)
                    for edit in revision.edits
                ],
            }
            for block in result.blocks
        ],
    }


def to_json(result: Result, *, indent: int | None = 2) -> str:
    """The report as JSON (``to_dict``), with non-ASCII characters kept as they are."""
    return json.dumps(to_dict(result), ensure_ascii=False, indent=indent) + "\n"


def to_markdown(result: Result, *, limit: int = 200) -> str:
    """A readable report: the counts, then each edit as before → after, up to ``limit``."""
    lines = [f"# LECTRIS report ({result.profile})", "", "| Rule | Edits |", "|---|---:|"]
    lines += [f"| `{rule}` | {count} |" for rule, count in result.counts().items()]
    lines += ["", "## Edits", ""]
    shown = 0
    for change in result.changes():
        if shown == limit:
            lines.append(f"… and more; the JSON report has all {sum(result.counts().values())}.")
            break
        edit = change.edit
        lines.append(
            f"- page {change.page}, block {change.block}, `{edit.rule}`: "
            f"{_quote(edit.before)} → {_quote(edit.after)}"
        )
        shown += 1
    if shown == 0:
        lines.append("No edits.")
    return "\n".join(lines) + "\n"


def _box(box: Box) -> tuple[float, float, float, float]:
    return (box.x0, box.y0, box.x1, box.y1)


def _quote(text: str) -> str:
    """Text for a Markdown list: in backticks, with invisible characters spelled out."""
    if not text:
        return "(nothing)"
    shown = text.replace("\n", "⏎").replace("\u00ad", "[soft hyphen]").replace("`", "'")
    return f"`{shown}`"
