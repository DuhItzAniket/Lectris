"""A model pack: the fitted evidence models and what they were fitted on (architecture §12).

A pack is one gzip JSON file (``*.lectris.json.gz``):

- ``manifest``: the pack format, the LECTRIS version, the engine and model it was fitted for, and
  each source it read with its SHA-256 and size;
- ``language``: the character language model (``charlm.CharLM``);
- ``channel``: the engine's confusions (``channel.Channel``);
- ``lexicon``: word counts.

``fit`` builds one: the channel from the OCR and ground-truth lines matched on the pages of a
pairs manifest (both sides in the normalised track, the form the proposers see), the language
model and the word counts from the ground truth of those pages and, optionally, from plain-text
files (``texts``, read in name order up to ``max_chars`` characters). Fitting is deterministic:
the same inputs give the same file, byte for byte. Evidence that depends on the engine (the
channel) holds for that engine's model only: ``ModelPack.matches`` says whether a document came
from it (ADR-0003).
"""

import gzip
import hashlib
import io as stdio
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from lectris import __version__
from lectris.errors import LectrisError
from lectris.lexicon import Lexicon
from lectris.model import Document
from lectris.models.channel import Channel
from lectris.models.charlm import CharLM

FORMAT: Final = "lectris-pack-1"
"""The pack format this LECTRIS reads and writes."""

_EDGES: Final = re.compile(r"^[\W_]+|[\W_]+$")  # the punctuation around a token
_APOSTROPHE: Final = chr(0x2019)  # a typographic apostrophe, inside a word like 's
_WORD: Final = re.compile(rf"[^\W\d_]+(?:['{_APOSTROPHE}-][^\W\d_]+)*")


class PackError(LectrisError):
    """A model pack that cannot be read or used."""


@dataclass(frozen=True, slots=True)
class Source:
    """A file a pack was fitted on: its name, its SHA-256 and what it gave."""

    name: str
    sha256: str
    role: str


@dataclass(frozen=True)
class ModelPack:
    """The fitted models, and the manifest of what they were fitted on."""

    engine: str
    model: str
    language: CharLM
    channel: Channel
    lexicon: Lexicon
    sources: tuple[Source, ...]
    lectris_version: str = __version__

    def matches(self, document: Document) -> bool:
        """Whether ``document`` came from the engine and model this pack was fitted for."""
        engine = document.engine
        return engine is not None and (engine.name, engine.model) == (self.engine, self.model)

    def to_data(self) -> dict[str, Any]:
        return {
            "manifest": {
                "format": FORMAT,
                "lectris_version": self.lectris_version,
                "engine": {"name": self.engine, "model": self.model},
                "sources": [
                    {"name": s.name, "sha256": s.sha256, "role": s.role} for s in self.sources
                ],
            },
            "language": self.language.to_data(),
            "channel": self.channel.to_data(),
            "lexicon": dict(sorted(self.lexicon.counts().items())),
        }


def words(text: str) -> list[str]:
    """The words of ``text`` as the lexicon counts them, lowercased: each whitespace-separated
    token, without the punctuation around it, that is all letters (with inner apostrophes or
    hyphens). A token with a digit in it (``1O5``, ``l0ng``) is not a word: the lexicon must not
    learn OCR errors."""
    found = []
    for token in text.split():
        core = _EDGES.sub("", token)
        if _WORD.fullmatch(core):
            found.append(core.lower())
    return found


def fit(
    pairs: Sequence[tuple[str, str]],
    truth_texts: Sequence[str],
    *,
    engine: str,
    model: str,
    texts: Iterable[Path] = (),
    max_chars: int = 3_000_000,
    order: int = 5,
    min_count: int = 2,
    sources: Sequence[Source] = (),
) -> ModelPack:
    """A pack from matched ``(intended, observed)`` line pairs and ground-truth texts, and
    plain-text files up to ``max_chars`` characters (see the module's documentation)."""
    corpus: list[str] = list(truth_texts)
    read: list[Source] = list(sources)
    total = 0
    for path in sorted(texts, key=lambda p: p.name):
        if total >= max_chars:
            break
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")[: max_chars - total]
        total += len(text)
        corpus.extend(line for line in text.splitlines() if line.strip())
        read.append(Source(path.name, hashlib.sha256(data).hexdigest(), "language, lexicon"))
    counts = Counter(word for line in corpus for word in words(line))
    lexicon = Lexicon({word: n for word, n in counts.items() if n >= min_count})
    return ModelPack(
        engine=engine,
        model=model,
        language=CharLM.fit(corpus, order=order, prune=True),
        channel=Channel.fit(pairs),
        lexicon=lexicon,
        sources=tuple(read),
    )


def save(pack: ModelPack, path: str | Path) -> None:
    """Write ``pack`` to ``path`` as gzip JSON, the same bytes for the same pack."""
    text = json.dumps(pack.to_data(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    buffer = stdio.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as handle:
        handle.write(text.encode("utf-8"))
    Path(path).write_bytes(buffer.getvalue())


def load(path: str | Path) -> ModelPack:
    """The pack at ``path``; ``PackError`` if it is not one this LECTRIS reads."""
    try:
        data = json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))
        manifest = data["manifest"]
        if manifest.get("format") != FORMAT:
            raise PackError(f"{path}: the pack format is {manifest.get('format')!r}, not {FORMAT}")
        return ModelPack(
            engine=str(manifest["engine"]["name"]),
            model=str(manifest["engine"]["model"]),
            language=CharLM.from_data(data["language"]),
            channel=Channel.from_data(data["channel"]),
            lexicon=Lexicon({str(w): int(n) for w, n in data["lexicon"].items()}),
            sources=tuple(
                Source(str(s["name"]), str(s["sha256"]), str(s["role"]))
                for s in manifest["sources"]
            ),
            lectris_version=str(manifest["lectris_version"]),
        )
    except PackError:
        raise
    except (OSError, EOFError, ValueError, KeyError, TypeError) as error:
        raise PackError(f"{path}: not a LECTRIS model pack ({error})") from None
