import pytest
from hypothesis import given
from hypothesis import strategies as st

from lectris.edits import Edit, apply_edits, unchanged
from lectris.quality import is_noise
from lectris.text.noise import RULE, RULES, drop_lines


def drop(start: int, end: int, before: str) -> Edit:
    return Edit(RULE, start, end, before, "")


@pytest.mark.parametrize(
    ("text", "expected", "edits"),
    [
        (
            "Chapter 3\n~~~ ,,, ' ' |||\nIt was a dark night.",
            "Chapter 3\nIt was a dark night.",
            [drop(10, 26, "~~~ ,,, ' ' |||\n")],
        ),
        (".:;:.:;\nText", "Text", [drop(0, 8, ".:;:.:;\n")]),
        ("Text\n@#%&*", "Text", [drop(4, 10, "\n@#%&*")]),
        (
            "Text\n@#%&*\nlllllllll",
            "Text",
            [drop(4, 10, "\n@#%&*"), drop(10, 20, "\nlllllllll")],
        ),
        (
            "|||||\nOne\n_____\nTwo",
            "One\nTwo",
            [drop(0, 6, "|||||\n"), drop(10, 16, "_____\n")],
        ),
        ("lllllllll", "", [drop(0, 9, "lllllllll")]),
        ("@#%&*\n.:;:.:;", "", [drop(0, 6, "@#%&*\n"), drop(6, 13, ".:;:.:;")]),
        ("Text\n\n|||||\n\nMore", "Text\n\n\nMore", [drop(6, 12, "|||||\n")]),
    ],
)
def test_noise_lines_are_dropped_with_one_line_break(
    text: str, expected: str, edits: list[Edit]
) -> None:
    revision = drop_lines(text)
    assert revision.text == expected
    assert list(revision.edits) == edits


@pytest.mark.parametrize(
    "text",
    [
        "Chapter 3\nTable 2.\nTotal 1,250.00 USD\n- 12 -",
        "Introduction .......... 1\nIndex . . . . . . 245",
        "if (x > 0) {\n    return x;\n} else {",
        "The law states that\nV = I R\nwhere V is the voltage.",
        "Solve\nx = y + z\na = b + c\nfor x.",
        "R & D\nQ & A",
        "| a | b |\nA B C D",
        "Text\n\nMore\n",
        "",
        "\n\n",
    ],
)
def test_text_and_blank_lines_are_kept(text: str) -> None:
    assert drop_lines(text) == unchanged(text)


@pytest.mark.parametrize("section_break", ["* * *", "***", "  *  *  *  ", "* * * * *"])
def test_a_section_break_of_asterisks_is_kept(section_break: str) -> None:
    text = f"The end of one scene.\n{section_break}\nThe start of the next."
    assert drop_lines(text) == unchanged(text)


@pytest.mark.parametrize("not_a_break", ["* *", "*~*~*", "** ~~ **"])
def test_other_symbol_lines_are_still_noise(not_a_break: str) -> None:
    assert drop_lines(f"Text.\n{not_a_break}\nMore text.").text == "Text.\nMore text."


def test_min_length_keeps_short_lines() -> None:
    assert drop_lines("Text\n}\nMore").text == "Text\nMore"
    assert drop_lines("Text\n}\nMore", min_length=2) == unchanged("Text\n}\nMore")


def test_the_threshold_is_passed_to_the_score() -> None:
    assert drop_lines("Text\nx y z") == unchanged("Text\nx y z")
    assert drop_lines("Text\nx y z", threshold=0.5).text == "Text"
    assert drop_lines("Text\n@#%&*", threshold=0.0) == unchanged("Text\n@#%&*")


@pytest.mark.parametrize(("threshold", "min_length"), [(1.5, 1), (-0.1, 1), (0.35, 0)])
def test_invalid_options_are_refused(threshold: float, min_length: int) -> None:
    with pytest.raises(ValueError, match=r"threshold|min_length"):
        drop_lines("Text", threshold=threshold, min_length=min_length)


def test_the_rule_is_registered_under_its_id() -> None:
    assert (drop_lines,) == RULES
    assert RULE == "noise.drop_lines"


lines_of_text = st.lists(
    st.sampled_from(["Text here", "- 12 -", "", "  ", "@#%&*", "lllllllll", "i i ! l ;"])
    | st.text(alphabet="al1.,;|~ -", max_size=12),
    max_size=8,
).map("\n".join)


@given(lines_of_text)
def test_the_revision_reproduces_its_text_and_keeps_every_other_line(text: str) -> None:
    revision = drop_lines(text)
    assert apply_edits(text, revision.edits) == revision.text
    assert revision.text == "\n".join(line for line in text.split("\n") if not is_noise(line))
    for earlier, later in zip(revision.edits, revision.edits[1:], strict=False):
        assert earlier.end <= later.start


@given(lines_of_text)
def test_dropping_lines_is_idempotent(text: str) -> None:
    assert drop_lines(drop_lines(text).text).edits == ()
