"""A word list with frequencies: membership, counts and spelling suggestions.

LECTRIS bundles no dictionary: word lists carry their own licences, and the right one depends on
the language and period of the text. Supply your own: a UTF-8 file with one word per line and an
optional count (``Lexicon.from_file``, and the CLI's ``--lexicon`` option), or words or counts
in memory.
"""

import bisect
import heapq
import math
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

from lectris.distance import _OCR_INDEX, _first_row, _next_row
from lectris.errors import FormatError

_COUNT: Final = re.compile(r"[0-9]+")
_LAST_CODE_POINT: Final = 0x10FFFF


def _checked_word(word: object) -> str:
    if not isinstance(word, str):
        raise TypeError(f"a lexicon word is a string, not {word!r}")
    if word.split() != [word]:
        raise ValueError(f"a lexicon word is one non-empty token without spaces, not {word!r}")
    return word


def _checked_count(word: str, count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError(f"the count of {word!r} is an integer, not {count!r}")
    if count < 0:
        raise ValueError(f"the count of {word!r} is at least 0, not {count}")
    return count


def _after_prefix(prefix: str) -> str | None:
    """The smallest string greater than every string that starts with ``prefix``, if any."""
    last = ord(prefix[-1])
    if last == _LAST_CODE_POINT:
        return None
    return prefix[:-1] + chr(last + 1)


class Lexicon:
    """A set of words, each with a count, that the text rules consult for evidence.

    Build one from words (each occurrence counts 1) or from a mapping of words to counts; counts
    of the same word add up. A word is one token: non-empty, without whitespace. By default the
    lexicon ignores case: words are stored and looked up after ``str.lower()``, so ``"Paris" in
    Lexicon(["paris"])`` is true, and suggestions come back in lower case. With
    ``case_sensitive=True`` words are kept and compared as given.

    Raises ``ValueError`` for an empty word, a word with whitespace or a negative count, and
    ``TypeError`` for a word that is not a string or a count that is not an integer.

    >>> lexicon = Lexicon({"modern": 12, "modem": 3})
    >>> "Modern" in lexicon, lexicon.frequency("modem")
    (True, 3)
    >>> lexicon.suggest("rnodern")
    ('modern', 'modem')
    """

    __slots__ = ("_case_sensitive", "_counts", "_sorted")

    def __init__(
        self, words: Iterable[str] | Mapping[str, int] = (), *, case_sensitive: bool = False
    ) -> None:
        self._case_sensitive = case_sensitive
        self._counts: dict[str, int] = {}
        self._sorted: list[str] | None = None
        pairs: Iterable[tuple[str, int]] = (
            words.items() if isinstance(words, Mapping) else ((word, 1) for word in words)
        )
        for word, count in pairs:
            key = self._key(_checked_word(word))
            self._counts[key] = self._counts.get(key, 0) + _checked_count(word, count)

    @classmethod
    def from_lines(cls, lines: Iterable[str], *, case_sensitive: bool = False) -> "Lexicon":
        """A lexicon from lines of text: a word per line, optionally followed by its count.

        The count is separated from the word by spaces or a tab and is a non-negative integer;
        a word without one counts 1. Blank lines and lines whose first visible character is
        ``#`` are ignored, so a word cannot start with ``#``. Repeated words add their counts.

        Raises ``FormatError`` for a line with more than two fields or a count that is not a
        non-negative integer, naming the line.

        >>> lexicon = Lexicon.from_lines(["# word counts", "the\\t812", "modern 12", "", "modem"])
        >>> lexicon.frequency("the"), lexicon.frequency("modem")
        (812, 1)
        """
        counts: dict[str, int] = {}
        for number, line in enumerate(lines, start=1):
            match line.split():
                case []:
                    continue
                case [first, *_] if first.startswith("#"):
                    continue
                case [word]:
                    count = 1
                case [word, digits] if _COUNT.fullmatch(digits):
                    count = int(digits)
                case _:
                    raise FormatError(
                        f"line {number}: expected a word and an optional count, "
                        f"found {line.strip()!r}"
                    )
            counts[word] = counts.get(word, 0) + count
        return cls(counts, case_sensitive=case_sensitive)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str], *, case_sensitive: bool = False) -> "Lexicon":
        """A lexicon from a UTF-8 text file in the format of ``from_lines``.

        A byte order mark at the start of the file is ignored. Raises ``FormatError`` if the
        file is not UTF-8 or a line is malformed, and ``OSError`` if it cannot be read.
        """
        try:
            with Path(path).open(encoding="utf-8-sig") as file:
                return cls.from_lines(file, case_sensitive=case_sensitive)
        except UnicodeDecodeError as error:
            raise FormatError(f"{os.fspath(path)}: not UTF-8 text ({error.reason})") from error
        except FormatError as error:
            raise FormatError(f"{os.fspath(path)}: {error}") from error

    @property
    def case_sensitive(self) -> bool:
        """Whether words are compared as given, rather than after ``str.lower()``."""
        return self._case_sensitive

    def _key(self, word: str) -> str:
        return word if self._case_sensitive else word.lower()

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and self._key(word) in self._counts

    def __len__(self) -> int:
        """The number of distinct words (after lower-casing, unless case-sensitive)."""
        return len(self._counts)

    def frequency(self, word: str) -> int:
        """The count of ``word``, or 0 if it is not in the lexicon."""
        return self._counts.get(self._key(word), 0)

    def suggest(self, word: str, *, max_distance: float = 1.0, limit: int = 5) -> tuple[str, ...]:
        """The lexicon's words nearest to ``word``: at most ``limit`` of them, each within
        ``max_distance`` by ``lectris.distance.ocr_distance`` with ``OCR_COSTS``.

        They are ranked by distance, then by count (highest first), then alphabetically. A word
        that is in the lexicon comes first, at distance 0. In a case-insensitive lexicon the
        distance is between the lower-cased forms, so the table's confusions that involve a
        capital letter (``l``/``I``, ``8``/``B``) do not apply there.

        The search walks the sorted words once, reusing the rows of the distance computation for
        the prefix a word shares with the one before it, and skips every word that starts with a
        prefix whose rows already exceed ``max_distance``. The costs are not negative, so no word
        under that prefix can come back within range: the results are exact. The work grows
        with the number of prefixes that stay within range rather than with the number of words,
        and quickly with ``max_distance``, since larger distances prune less.

        Raises ``ValueError`` if ``max_distance`` is negative or not a number, or ``limit`` is
        below 1.
        """
        if math.isnan(max_distance) or max_distance < 0:
            raise ValueError(f"max_distance is at least 0, not {max_distance!r}")
        if limit < 1:
            raise ValueError(f"limit is at least 1, not {limit!r}")
        query = self._key(word)
        if self._sorted is None:
            self._sorted = sorted(self._counts)
        words = self._sorted
        spans = _OCR_INDEX.spans(query)
        rows = [_first_row(query)]
        minima = [0.0]
        current = ""
        found: list[tuple[float, int, str]] = []
        position = 0
        while position < len(words):
            candidate = words[position]
            shared = 0
            most = min(len(rows) - 1, len(candidate))
            while shared < most and current[shared] == candidate[shared]:
                shared += 1
            del rows[shared + 1 :], minima[shared + 1 :]
            current = candidate
            pruned_at = 0
            for j in range(shared + 1, len(candidate) + 1):
                row = _next_row(query, spans, rows, candidate, j)
                rows.append(row)
                minima.append(min(row))
                if self._beyond(minima, candidate, j, max_distance):
                    pruned_at = j
                    break
            if pruned_at:
                position = self._skip(words, position, candidate[:pruned_at])
                continue
            distance = rows[-1][-1]
            if distance <= max_distance:
                found.append((distance, -self._counts[candidate], candidate))
            position += 1
        return tuple(entry[2] for entry in heapq.nsmallest(limit, found))

    @staticmethod
    def _beyond(minima: list[float], candidate: str, j: int, max_distance: float) -> bool:
        """Whether no word that starts with ``candidate[:j]`` is within ``max_distance``.

        Every alignment to such a word passes through row ``j``, or steps over it with a table
        entry whose second string starts with ``candidate[r:j]`` from an earlier row ``r``. The
        costs are not negative, so if all those rows exceed ``max_distance``, so does the word.
        """
        if minima[j] <= max_distance:
            return False
        reach = _OCR_INDEX.longest_target
        return all(
            minima[r] > max_distance
            for r in range(max(0, j - reach + 1), j)
            if candidate[r:j] in _OCR_INDEX.target_prefixes
        )

    @staticmethod
    def _skip(words: list[str], position: int, prefix: str) -> int:
        """The index of the first word after ``position`` that does not start with ``prefix``."""
        bound = _after_prefix(prefix)
        if bound is not None:
            return bisect.bisect_left(words, bound, lo=position + 1)
        position += 1
        while position < len(words) and words[position].startswith(prefix):
            position += 1
        return position
