"""Proposers: rules that guess, and so suggest candidate edits instead of making them (ADR-0001).

A text rule is a **transform** when its change is right wherever its pattern matches (Unicode,
whitespace, unwrapping, punctuation style), and a **proposer** when it guesses. LECTRIS v0.1's
guessing rules are proposers: ``PROPOSERS`` names them. ``candidates(revision)`` turns what one
of them returned into candidates, each carrying the feature ``v01 = 1``, which says the v0.1
rule, with its own conditions, applies it; ``lectris.decide.PARITY`` accepts exactly those.

**Lexicon proposers** (architecture §9) need a word list, usually a model pack's, and propose
what no v0.1 rule would (``v01 = 0``), for a calibrated decision to accept or not:

- ``Lexical`` (rule ``lexical.word``): a token of letters that is not in the lexicon gets, as
  candidates, the lexicon's words one edit away (a character deleted, inserted or substituted,
  found through a deletion index, as SymSpell does), the most frequent first (the feature
  ``lexical_rank`` is 0 for the most frequent), in the token's case;
- ``Segmentation`` (rules ``segmentation.split`` and ``segmentation.merge``): a token not in the
  lexicon that is two lexicon words run together gets a space inserted between them; two tokens
  separated by one space that make a lexicon word together, when one of them is not a word,
  get the space removed.

A token is a run of non-spaces; the punctuation around it is not part of the word, and a token
with a digit or another non-letter inside is left alone (the confusion rules handle those).
"""

import re
from collections.abc import Iterator
from itertools import pairwise
from typing import Final

from lectris.edits import Candidate, Revision
from lectris.lexicon import Lexicon

PROPOSERS: Final = frozenset(
    {
        "confusables.in_numbers",
        "confusables.in_words",
        "numbers.separators",
        "punctuation.spacing",
        "hyphenation.join",
        "noise.drop_lines",
    }
)
"""The ids of the text rules that guess, and so propose: v0.1's repairs."""

V01: Final = "v01"
"""The feature that marks a candidate the v0.1 rule applies (1) or declines (0)."""

_TOKEN: Final = re.compile(r"\S+")
_LETTERS: Final = re.compile(r"[^\W\d_]+")
_EDGES: Final = re.compile(r"^[\W_]*(.*?)[\W_]*$", re.DOTALL)
_SHORT_WORDS: Final = frozenset({"a", "i", "o"})


def candidates(revision: Revision) -> tuple[Candidate, ...]:
    """The v0.1 rule's edits in ``revision`` as candidates it applies (``v01 = 1``)."""
    return tuple(
        Candidate(edit.rule, edit.start, edit.end, edit.before, edit.after, ((V01, 1.0),))
        for edit in revision.edits
    )


def core_of(token: str) -> str:
    """``token`` without the punctuation around it."""
    core = _EDGES.match(token)
    return core.group(1) if core else token


def words_in(text: str) -> Iterator[tuple[int, int, str]]:
    """Each token's word: its span in ``text`` and its letters, for tokens whose core (without
    the punctuation around it) is all letters."""
    for token in _TOKEN.finditer(text):
        core = _EDGES.match(token.group())
        if core is None:  # pragma: no cover - the pattern matches any string
            continue
        word = core.group(1)
        if word and _LETTERS.fullmatch(word):
            start = token.start() + core.start(1)
            yield start, start + len(word), word


def in_case_of(word: str, model: str) -> str:
    """``word`` (lower case) written in the case of ``model``: upper, title or lower."""
    if model.isupper() and len(model) > 1:
        return word.upper()
    if model[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


class Lexical:
    """Candidates one edit away from tokens that are not words (``lexical.word``)."""

    RULE: Final = "lexical.word"

    def __init__(self, lexicon: Lexicon, *, limit: int = 3, min_length: int = 3) -> None:
        self._lexicon = lexicon
        self._limit = limit
        self._min_length = min_length
        self._index: dict[str, set[str]] = {}
        for word in lexicon.counts():
            if not _LETTERS.fullmatch(word):
                continue
            for key in (word, *_deletions(word)):
                self._index.setdefault(key, set()).add(word)

    def __call__(self, text: str) -> tuple[Candidate, ...]:
        found: list[Candidate] = []
        for start, end, word in words_in(text):
            lower = word.lower()
            if len(word) < self._min_length or lower in self._lexicon:
                continue
            near: set[str] = set(self._index.get(lower, ()))  # OCR lost a character
            for key in _deletions(lower):  # OCR added or changed one
                near.update(self._index.get(key, ()))
            near = {w for w in near if _one_edit(lower, w)}
            ranked = sorted(near, key=lambda w: (-self._lexicon.frequency(w), w))
            kept = [w for w in ranked[: self._limit] if in_case_of(w, word) != word]
            found.extend(
                Candidate(
                    self.RULE,
                    start,
                    end,
                    word,
                    in_case_of(w, word),
                    (("lexical_rank", float(rank)), (V01, 0.0)),
                )
                for rank, w in enumerate(kept)
            )
        return tuple(found)


class Segmentation:
    """Candidates for a missing space (``segmentation.split``) or a spurious one
    (``segmentation.merge``)."""

    SPLIT: Final = "segmentation.split"
    MERGE: Final = "segmentation.merge"

    def __init__(self, lexicon: Lexicon, *, min_length: int = 4) -> None:
        self._lexicon = lexicon
        self._min_length = min_length

    def _is_word(self, part: str) -> bool:
        return (len(part) > 1 or part.lower() in _SHORT_WORDS) and part in self._lexicon

    def __call__(self, text: str) -> tuple[Candidate, ...]:
        found: list[Candidate] = []
        tokens = list(words_in(text))
        for start, _, word in tokens:
            if len(word) < self._min_length or word in self._lexicon:
                continue
            for cut in range(1, len(word)):
                if self._is_word(word[:cut]) and self._is_word(word[cut:]):
                    position = start + cut
                    found.append(Candidate(self.SPLIT, position, position, "", " ", ((V01, 0.0),)))
        for (_, first_end, a), (second, _, b) in pairwise(tokens):
            if text[first_end:second] != " ":
                continue
            if (a in self._lexicon and b in self._lexicon) or (a + b) not in self._lexicon:
                continue
            found.append(Candidate(self.MERGE, first_end, second, " ", "", ((V01, 0.0),)))
        return tuple(found)


def _deletions(word: str) -> set[str]:
    """``word`` with one character deleted, every way."""
    return {word[:i] + word[i + 1 :] for i in range(len(word))}


def _one_edit(a: str, b: str) -> bool:
    """Whether ``b`` is ``a`` with exactly one character deleted, inserted or substituted."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    short, long = (a, b) if len(a) < len(b) else (b, a)
    return any(long[:i] + long[i + 1 :] == short for i in range(len(long)))
