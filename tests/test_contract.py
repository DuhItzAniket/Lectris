"""The rule contract (docs/ARCHITECTURE.md, "Text rules"), checked for every rule at once.

Each text module lists its rules in ``RULES``; every rule found there, and every step of every
profile with its options, is held to the contract here. A new rule is covered without a new test.
"""

import importlib
import pkgutil
from collections.abc import Callable
from functools import partial

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import lectris.text
from lectris.edits import Revision, apply_edits
from lectris.lexicon import Lexicon
from lectris.pipeline import Step, rule_id
from lectris.profiles import PROFILES
from lectris.text import confusables, hyphenation, punctuation

SOFT_HYPHEN = chr(0x00AD)
#: Characters the rules look for, mixed with ordinary text, so that they fire often.
ALPHABET = st.sampled_from(
    [
        *"abcdeflmnorstuyABOSIl015689",
        *" \t\n\n-.,;:!?'\"()[]",
        SOFT_HYPHEN,
        chr(0x200B),  # zero width space
        chr(0xFB01),  # the fi ligature
        chr(0xFF21),  # fullwidth A
        chr(0x0301),  # combining acute accent
        chr(0x00A0),  # no-break space
        chr(0x2026),  # ellipsis
        chr(0x201C),
        chr(0x201D),  # curly double quotes
        chr(0x2010),  # hyphen
        "~",
        "|",
    ]
)
TEXT = st.lists(ALPHABET, max_size=80).map("".join)


def _text_rules() -> list[Callable[..., Revision]]:
    rules: list[Callable[..., Revision]] = []
    for module in pkgutil.iter_modules(lectris.text.__path__):
        imported = importlib.import_module(f"lectris.text.{module.name}")
        rules.extend(getattr(imported, "RULES", ()))
    return rules


RULES = _text_rules()
LEXICON = Lexicon({"information": 9, "well-known": 4, "word": 7, "simple": 3, "colour": 2})
#: Rules with options other than their defaults: each variant is held to the contract too.
VARIANTS = {
    "quotes-curly": partial(punctuation.quotes, style="curly"),
    "quotes-straight": partial(punctuation.quotes, style="straight"),
    "ellipsis-character": partial(punctuation.ellipsis, style="character"),
    "spacing-high": partial(punctuation.spacing, high_punctuation=True),
    "join-lexicon": partial(hyphenation.join, lexicon=LEXICON),
    "in-words-lexicon": partial(confusables.in_words, lexicon=LEXICON),
}
STEPS = {
    f"{profile.name}:{index}:{step.id}": step
    for profile in PROFILES.values()
    for index, step in enumerate(profile.steps)
}


def check(text: str, revision: Revision, rule: str) -> None:
    assert apply_edits(text, revision.edits) == revision.text
    starts = [edit.start for edit in revision.edits]
    assert starts == sorted(starts)
    for before, after in zip(revision.edits, revision.edits[1:], strict=False):
        assert before.end <= after.start
    for edit in revision.edits:
        assert edit.rule == rule
        assert text[edit.start : edit.end] == edit.before


def test_every_text_module_lists_its_rules() -> None:
    names = {rule_id(rule) for rule in RULES}
    for module in ("unicode", "whitespace", "punctuation", "hyphenation", "unwrap", "noise"):
        assert any(name.startswith(f"{module}.") for name in names), module
    assert len(names) == len(RULES), "a rule is listed twice"


@pytest.mark.parametrize("rule", RULES, ids=rule_id)
@settings(max_examples=300, deadline=None)
@given(text=TEXT)
def test_every_rule_keeps_the_contract(rule: Callable[..., Revision], text: str) -> None:
    revision = rule(text)
    check(text, revision, rule_id(rule))
    assert rule(revision.text).edits == (), "rules are idempotent"


@pytest.mark.parametrize("variant", VARIANTS.values(), ids=VARIANTS.keys())
@settings(max_examples=300, deadline=None)
@given(text=TEXT)
def test_every_rule_variant_keeps_the_contract(variant: "partial[Revision]", text: str) -> None:
    revision = variant(text)
    check(text, revision, rule_id(variant.func))
    assert variant(revision.text).edits == (), "rules are idempotent"


@pytest.mark.parametrize("step", STEPS.values(), ids=STEPS.keys())
@settings(max_examples=150, deadline=None)
@given(text=TEXT)
def test_every_profile_step_keeps_the_contract(step: Step, text: str) -> None:
    check(text, step.apply(text, None), step.id)
