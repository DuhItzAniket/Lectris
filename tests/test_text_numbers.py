import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, apply_edits
from lectris.text.numbers import RULES, SEPARATORS, separators


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pi is 3 .14 exactly", "pi is 3.14 exactly"),
        ("a crowd of 1 ,000", "a crowd of 1,000"),
        ("1 ,000 ,000 people", "1,000,000 people"),
        ("1 ,000 .5 m", "1,000.5 m"),
        ("price $1 ,250.", "price $1,250."),
        ("-3 .14 and 0 .5", "-3.14 and 0.5"),
        ("12345 .67", "12345.67"),
        ("on 31 .10 .2024", "on 31.10.2024"),
        ("version 1.2 .3", "version 1.2.3"),
    ],
)
def test_spaces_inside_a_number_are_removed(text: str, expected: str) -> None:
    assert separators(text).text == expected


@pytest.mark.parametrize(
    "text",
    [
        "items 1, 2 and 3",
        "1, 2, 3",
        "codes 100, 200, 300",
        "12 , 5",
        "12 ,5",
        "at 10 : 30",
        "v1. 2",
        "v1 .2",
        "chapter 3. 14 people came",
        "chapter 3.\n14 people came",
        "3 .\n14",
        "1 000 000",
        "1 ,00 ,000",
        "2024 ,500",
        "3 .14abc",
        "pages 10 - 20",
        "1.5, 2.5 and 3",
    ],
)
def test_sentence_ends_lists_dates_times_and_versions_are_left_alone(text: str) -> None:
    assert separators(text).edits == ()


def test_one_edit_per_separator() -> None:
    revision = separators("3 .14 and 1 ,000")
    assert revision.edits == (
        Edit(SEPARATORS, 1, 3, " .", "."),
        Edit(SEPARATORS, 11, 13, " ,", ","),
    )
    assert revision.text == "3.14 and 1,000"


def test_rules_lists_the_rule() -> None:
    assert (separators,) == RULES


@given(st.text(alphabet="0123 .,:\nav-", max_size=40))
def test_the_rule_contract_holds(text: str) -> None:
    revision = separators(text)
    assert apply_edits(text, revision.edits) == revision.text
    assert separators(revision.text).edits == ()
    assert revision.text.count("\n") == text.count("\n")
    assert revision.text.replace(" ", "") == text.replace(" ", "")
