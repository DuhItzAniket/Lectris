from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.align import Op, OpKind, align, align_chars, align_words


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        diagonal, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            diagonal, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, diagonal + (x != y))
    return row[-1]


def full_table_alignment(a: Sequence[str], b: Sequence[str]) -> tuple[Op, ...]:
    """The documented choice, computed on the full table: shared ends equal, then traced back
    from the end preferring pair, delete, insert."""
    n, m = len(a), len(b)
    prefix = 0
    while prefix < min(n, m) and a[prefix] == b[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(n, m) - prefix and a[n - 1 - suffix] == b[m - 1 - suffix]:
        suffix += 1
    x, y = a[prefix : n - suffix], b[prefix : m - suffix]
    table = [[i + j for j in range(len(y) + 1)] for i in range(len(x) + 1)]
    for i in range(1, len(x) + 1):
        for j in range(1, len(y) + 1):
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + (x[i - 1] != y[j - 1]),
            )
    middle: list[Op] = []
    i, j = len(x), len(y)
    while i or j:
        if i and j and table[i - 1][j - 1] + (x[i - 1] != y[j - 1]) == table[i][j]:
            kind: OpKind = "equal" if x[i - 1] == y[j - 1] else "substitute"
            middle.append(Op(kind, x[i - 1], y[j - 1]))
            i, j = i - 1, j - 1
        elif i and table[i - 1][j] + 1 == table[i][j]:
            middle.append(Op("delete", x[i - 1], ""))
            i -= 1
        else:
            middle.append(Op("insert", "", y[j - 1]))
            j -= 1
    return (
        *(Op("equal", e, e) for e in a[:prefix]),
        *reversed(middle),
        *(Op("equal", e, e) for e in a[n - suffix :]),
    )


def test_kitten_and_sitting() -> None:
    assert align_chars("kitten", "sitting") == (
        Op("substitute", "k", "s"),
        Op("equal", "i", "i"),
        Op("equal", "t", "t"),
        Op("equal", "t", "t"),
        Op("substitute", "e", "i"),
        Op("equal", "n", "n"),
        Op("insert", "", "g"),
    )


@pytest.mark.parametrize(
    ("reference", "hypothesis", "expected"),
    [
        ("", "", ()),
        ("", "ab", (Op("insert", "", "a"), Op("insert", "", "b"))),
        ("ab", "", (Op("delete", "a", ""), Op("delete", "b", ""))),
        ("ab", "ba", (Op("substitute", "a", "b"), Op("substitute", "b", "a"))),
        ("aab", "ab", (Op("equal", "a", "a"), Op("delete", "a", ""), Op("equal", "b", "b"))),
        ("m", "rn", (Op("insert", "", "r"), Op("substitute", "m", "n"))),
        ("cl", "d", (Op("delete", "c", ""), Op("substitute", "l", "d"))),
    ],
)
def test_ties_are_broken_as_documented(
    reference: str, hypothesis: str, expected: tuple[Op, ...]
) -> None:
    assert align_chars(reference, hypothesis) == expected


def test_words() -> None:
    assert align_words("the cat  sat", "the bat sat\non") == (
        Op("equal", "the", "the"),
        Op("substitute", "cat", "bat"),
        Op("equal", "sat", "sat"),
        Op("insert", "", "on"),
    )
    assert align(["one", "two"], ("one",)) == (Op("equal", "one", "one"), Op("delete", "two", ""))


def test_a_long_text_with_scattered_errors() -> None:
    reference = "It was the best of times, it was the worst of times. " * 12
    hypothesis = "".join(
        "" if index % 41 == 0 else ("#" if index % 17 == 0 else char)
        for index, char in enumerate(reference)
    )
    ops = align_chars(reference, hypothesis)
    assert sum(op.kind != "equal" for op in ops) == levenshtein(reference, hypothesis)
    assert ops == full_table_alignment(reference, hypothesis)


@pytest.mark.parametrize(
    ("kind", "reference", "hypothesis"),
    [
        ("equal", "a", "b"),
        ("substitute", "a", "a"),
        ("insert", "a", "b"),
        ("delete", "a", "b"),
        ("swap", "a", "b"),
    ],
)
def test_an_inconsistent_op_is_refused(kind: OpKind, reference: str, hypothesis: str) -> None:
    with pytest.raises(ValueError, match="op"):
        Op(kind, reference, hypothesis)


texts = st.text(alphabet="abc", max_size=30)


@given(texts, texts)
def test_an_alignment_is_minimal_and_complete(reference: str, hypothesis: str) -> None:
    ops = align_chars(reference, hypothesis)
    assert sum(op.kind != "equal" for op in ops) == levenshtein(reference, hypothesis)
    assert "".join(op.reference for op in ops) == reference
    assert "".join(op.hypothesis for op in ops) == hypothesis


@given(texts, texts)
def test_the_banded_alignment_is_the_full_table_s(reference: str, hypothesis: str) -> None:
    assert align_chars(reference, hypothesis) == full_table_alignment(reference, hypothesis)


@given(st.lists(st.sampled_from(["the", "a", "cat", "sat"]), max_size=12), st.data())
def test_word_alignments_are_minimal(reference: list[str], data: st.DataObject) -> None:
    hypothesis = data.draw(st.lists(st.sampled_from(["the", "a", "bat", "sat"]), max_size=12))
    ops = align(reference, hypothesis)
    assert sum(op.kind != "equal" for op in ops) == levenshtein(reference, hypothesis)
    assert [op.reference for op in ops if op.kind != "insert"] == reference
    assert [op.hypothesis for op in ops if op.kind != "delete"] == hypothesis
