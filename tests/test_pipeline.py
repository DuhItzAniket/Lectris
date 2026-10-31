from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from layout_pages import skew_line
from lectris.edits import apply_edits
from lectris.io import parse, read
from lectris.lexicon import Lexicon
from lectris.model import Block, Box, Document, Line, Page, Word, union_of
from lectris.pipeline import Profile, Step, clean, rule_id, run_rules
from lectris.profiles import AGGRESSIVE, CONSERVATIVE, PROFILES, STANDARD, get
from lectris.text import hyphenation, unicode, whitespace

DATA = Path(__file__).parent / "data" / "io"
SOFT_HYPHEN = chr(0x00AD)
FI = chr(0xFB01)


def test_a_rule_id_is_its_module_and_name() -> None:
    assert rule_id(hyphenation.join) == "hyphenation.join"
    assert Step(unicode.ligatures).id == "unicode.ligatures"


class TestClean:
    def test_plain_text_is_cleaned_with_the_standard_profile(self) -> None:
        result = clean(f"An exam-\nple of {FI}ne text  with   spaces .")
        assert result.profile == "standard"
        assert result.text == "An example of fine text with spaces."
        counts = result.counts()
        assert counts["hyphenation.join"] == 1
        assert counts["unicode.ligatures"] == 1
        assert counts["whitespace.collapse"] == 2
        assert counts["punctuation.spacing"] == 1

    def test_blocks_stay_apart(self) -> None:
        result = clean("First paragraph,\nwrapped.\n\nSecond one.")
        assert result.text == "First paragraph, wrapped.\n\nSecond one."
        assert [block.index for block in result.blocks] == [0, 1]

    def test_conservative_keeps_line_breaks(self) -> None:
        result = clean("one line\nand the next", profile="conservative")
        assert result.text == "one line\nand the next"

    def test_a_soft_hyphen_at_a_line_end_rejoins_the_word(self) -> None:
        result = clean(f"Send an e{SOFT_HYPHEN}\nmail today.")
        assert result.text == "Send an email today."

    def test_noise_lines_go_in_the_standard_profile_only(self) -> None:
        text = "A real line of text.\n~~~ ,,, ' ' |||\nAnother real line."
        assert clean(text).text == "A real line of text. Another real line."
        assert "~~~" in clean(text, profile="conservative").text

    def test_a_lexicon_reaches_the_rules_that_use_one(self) -> None:
        text = "a well-\nknown result"
        assert clean(text).text == "a wellknown result"
        lexicon = Lexicon({"well-known": 5, "result": 3})
        assert clean(text, lexicon=lexicon).text == "a well-known result"

    def test_an_unknown_profile_is_refused(self) -> None:
        with pytest.raises(ValueError, match="aggressive"):
            clean("text", profile="loud")

    def test_a_profile_object_can_be_given(self) -> None:
        only_spaces = Profile("spaces", "spaces only", (Step(whitespace.collapse),))
        result = clean("a  b\nc", profile=only_spaces)
        assert result.text == "a b\nc"
        assert result.counts() == {"whitespace.collapse": 1}

    def test_every_edit_is_kept_and_replays_to_the_text(self) -> None:
        result = clean(f"The {FI}rst  line,\nand a sec-\nond one with 1O5 items .")
        for block in result.blocks:
            text = block.source
            for rule, revision in block.revisions:
                assert all(edit.rule == rule for edit in revision.edits)
                text = apply_edits(text, revision.edits)
                assert text == revision.text
            assert text == block.text
        changes = list(result.changes())
        assert len(changes) == sum(result.counts().values())
        assert {change.edit.rule for change in changes} >= {
            "unicode.ligatures",
            "confusables.in_numbers",
            "hyphenation.join",
        }

    def test_counts_list_every_rule_of_the_profile(self) -> None:
        result = clean("Nothing to do here.", profile="conservative")
        assert list(result.counts()) == list(CONSERVATIVE.rule_ids)
        assert set(result.counts().values()) == {0}

    def test_empty_blocks_are_left_out_of_the_text(self) -> None:
        result = clean("Real text.\n\n~~~ ,,, ' ' |||")
        assert result.text == "Real text."
        assert len(result.blocks) == 2
        assert result.blocks[1].text == ""


class TestDocuments:
    def test_a_two_column_page_reads_column_by_column(self) -> None:
        def line(text: str, x: float, y: float) -> Line:
            words = []
            left = x
            for part in text.split():
                width = 10.0 * len(part)
                words.append(Word(part, Box(left, y, left + width, y + 20)))
                left += width + 10
            return Line(tuple(words), Box(x, y, left - 10, y + 20))

        lines = (
            line("Right column first line", 600, 100),
            line("Left column first line", 100, 100),
            line("left column second line", 100, 130),
            line("right column second line", 600, 130),
        )
        page = Page((Block(lines),), width=1000, height=800)
        result = clean(Document((page,)))
        assert result.text.index("Left column") < result.text.index("Right column")
        assert result.text.index("left column second") < result.text.index("Right column")

    @pytest.mark.parametrize("degrees", [1.0, 1.5, 2.25, -2.25])
    def test_a_skewed_scan_keeps_its_lines_whole_and_in_order(self, degrees: float) -> None:
        def sparse_line(label: str, y: float) -> Line:
            # Three words spread over 2000: few, widely spaced words climb most under skew.
            boxes = [Box(300 + i * 667, y, 300 + (i + 0.8) * 667, y + 35) for i in range(3)]
            words = tuple(Word(f"{label}w{i}", box) for i, box in enumerate(boxes))
            return Line(words, box=union_of(boxes))

        straight = [sparse_line(f"L{i}", 300 + 45 * i) for i in range(6)]
        lines = tuple(skew_line(line, degrees, (1275, 1650)) for line in straight)
        result = clean(Document((Page((Block(lines),)),)), profile="conservative")
        assert result.text.split("\n") == [line.text for line in straight]

    def test_the_layout_can_be_left_as_it_was(self) -> None:
        unarranged = Profile("as-is", "no layout", STANDARD.steps, arrange=False)
        page = Page((Block((Line.from_text("second"),)), Block((Line.from_text("first"),))))
        assert clean(Document((page,)), profile=unarranged).text == "second\n\nfirst"

    @pytest.mark.parametrize("name", sorted(path.name for path in DATA.iterdir()))
    def test_every_sample_cleans_under_every_profile(self, name: str) -> None:
        document = read(DATA / name)
        for profile in PROFILES:
            result = clean(document, profile=profile)
            assert result.blocks or not document.text
            for block in result.blocks:
                assert block.page >= 1

    def test_confidence_is_carried_to_the_blocks(self) -> None:
        tsv = (DATA / "tesseract.tsv").read_text(encoding="utf-8")
        result = clean(parse(tsv, format="tsv"))
        assert any(block.confidence is not None for block in result.blocks)


class TestProfiles:
    def test_the_profiles_are_named(self) -> None:
        assert set(PROFILES) == {"conservative", "standard", "aggressive"}
        assert get("standard") is STANDARD

    @pytest.mark.parametrize("profile", [CONSERVATIVE, STANDARD, AGGRESSIVE], ids=lambda p: p.name)
    def test_the_order_of_the_rules(self, profile: Profile) -> None:
        ids = profile.rule_ids
        assert ids[0] == "whitespace.line_breaks"
        assert ids.index("unicode.compatibility") < ids.index("unicode.nfc")
        assert ids.index("unicode.invisible") < ids.index("hyphenation.join")
        if "unwrap.join_lines" in ids:
            unwrap = ids.index("unwrap.join_lines")
            # De-hyphenation reads the line breaks unwrapping removes; a tidy-up follows it.
            assert ids[unwrap - 1] == "hyphenation.join"
            tidy = ("unicode.invisible", "whitespace.collapse", "whitespace.trim")
            assert ids[unwrap + 1 : unwrap + 4] == tidy
            # The rules that read tokens run on the final lines.
            for rule in ("confusables.in_numbers", "numbers.separators", "punctuation.spacing"):
                assert ids.index(rule) > unwrap
        if "noise.drop_lines" in ids:
            assert ids.index("noise.drop_lines") < ids.index("hyphenation.join")

    def test_each_profile_adds_to_the_one_before(self) -> None:
        assert set(CONSERVATIVE.rule_ids) < set(STANDARD.rule_ids) < set(AGGRESSIVE.rule_ids)


IDEMPOTENCE_ALPHABET = st.sampled_from(
    [
        *"abcilmnorstyABOSIl01589 \t\n-.,;:!?()'\"|~",
        FI,
        SOFT_HYPHEN,
        chr(0x200B),  # zero width space
        chr(0xFF21),  # fullwidth A
        chr(0x0301),  # combining acute accent
        chr(0x00A0),  # no-break space
        chr(0x2026),  # ellipsis
        chr(0x201C),  # left double quote
        chr(0x2010),  # hyphen
    ]
)


@pytest.mark.parametrize("profile", [CONSERVATIVE, STANDARD, AGGRESSIVE], ids=lambda p: p.name)
@settings(max_examples=150, deadline=None)
@given(text=st.text(alphabet=IDEMPOTENCE_ALPHABET, max_size=60))
def test_running_the_rules_twice_changes_nothing_more(profile: Profile, text: str) -> None:
    once, _ = run_rules(text, profile.steps)
    twice, revisions = run_rules(once, profile.steps)
    assert twice == once
    assert all(not revision.edits for _, revision in revisions)


@settings(max_examples=200, deadline=None)
@given(st.text(alphabet=st.sampled_from([*"ab \t\r\n\f", chr(0xFEFF)]), max_size=40))
def test_plain_text_blocks_line_up_with_the_parsed_ones(text: str) -> None:
    result = clean(text, profile="conservative")
    parsed = [block for page in result.document.pages for block in page.blocks]
    assert len(result.blocks) == len(parsed)
    for block, parsed_block in zip(result.blocks, parsed, strict=True):
        assert block.source.split() == parsed_block.text.split()


def test_plain_text_spacing_reaches_the_rules() -> None:
    result = clean("two  spaces\r\nand a line end", profile="conservative")
    assert result.text == "two spaces\nand a line end"
    assert result.counts()["whitespace.collapse"] == 1
    assert result.counts()["whitespace.line_breaks"] == 1
