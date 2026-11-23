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
    """The report as plain data: the profile, the guarantee, each block's source and text, its
    edits and the decisions on its candidates, and the flags for review.

    An edit's or a decision's ``start`` and ``end`` are offsets in the text its rule received:
    the block's source after the steps before it. ``guarantee`` is ``null`` unless the policy is
    risk-controlled; ``applies`` says whether the input came from the engine it was calibrated
    for.
    """
    guarantee = result.guarantee
    return {
        "format": FORMAT_VERSION,
        "profile": result.profile,
        "guarantee": None
        if guarantee is None
        else {
            "alpha": guarantee.alpha,
            "delta": guarantee.delta,
            "threshold": guarantee.threshold,
            "engine": guarantee.engine,
            "model": guarantee.model,
            "applies": result.guarantee_applies,
        },
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
                "decisions": [
                    {
                        "step": step,
                        "rule": d.candidate.rule,
                        "start": d.candidate.start,
                        "end": d.candidate.end,
                        "before": d.candidate.before,
                        "after": d.candidate.after,
                        "accepted": d.accepted,
                        "reason": d.reason,
                        "probability": d.probability,
                        "threshold": d.threshold,
                        "features": dict(d.candidate.features),
                    }
                    for step, (_, revision) in enumerate(block.revisions)
                    for d in revision.decisions
                ],
            }
            for block in result.blocks
        ],
        "flags": [
            {
                "page": f.page,
                "block": f.block,
                "step": f.step,
                "rule": f.rule,
                "start": f.start,
                "end": f.end,
                "before": f.before,
                "after": f.after,
                "probability": f.probability,
            }
            for f in result.flags()
        ],
    }


def to_json(result: Result, *, indent: int | None = 2) -> str:
    """The report as JSON (``to_dict``), with non-ASCII characters kept as they are."""
    return json.dumps(to_dict(result), ensure_ascii=False, indent=indent) + "\n"


def to_markdown(result: Result, *, limit: int = 200) -> str:
    """A readable report: the counts, then each edit as before → after, up to ``limit``."""
    lines = [f"# LECTRIS report ({result.profile})", ""]
    guarantee = result.guarantee
    if guarantee is not None:
        applies = "applies" if result.guarantee_applies else "does NOT apply (another engine)"
        lines += [
            f"Risk-controlled: harm rate at most {guarantee.alpha} with confidence "
            f"{1 - guarantee.delta:g}, threshold {guarantee.threshold}, for "
            f"{guarantee.engine} {guarantee.model}; the guarantee {applies}.",
            "",
        ]
    lines += ["| Rule | Edits |", "|---|---:|"]
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
    flags = result.flags()
    if flags:
        lines += ["", "## For review", ""]
        lines += [
            f"- page {f.page}, block {f.block}, `{f.rule}` ({f.probability:.2f}): "
            f"{_quote(f.before)} → {_quote(f.after)}"
            for f in flags[:limit]
        ]
    return "\n".join(lines) + "\n"


def _box(box: Box) -> tuple[float, float, float, float]:
    return (box.x0, box.y0, box.x1, box.y1)


def _quote(text: str) -> str:
    """Text for a Markdown list: in backticks, with invisible characters spelled out."""
    if not text:
        return "(nothing)"
    shown = text.replace("\n", "⏎").replace("\u00ad", "[soft hyphen]").replace("`", "'")
    return f"`{shown}`"
