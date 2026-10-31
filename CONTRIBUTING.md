# Contributing to LECTRIS

Thank you for helping. The design is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); read it
before changing a rule or the model.

## Set up

LECTRIS uses [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.

```bash
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
uv run mypy
```

## What a change needs

- **Tests for what it changes and what it must leave alone.** A text rule's false positives
  matter more than its misses: OCR post-processing that damages correct text is worse than none.
  Add the cases a rule must not touch, not only the ones it fixes.
- **The rule contract** (architecture, "Text rules"): every change recorded as an edit, offsets
  in the rule's input, idempotent unless the docstring says otherwise. The property tests check
  this; a new rule gets the same tests.
- **No runtime dependencies.** LECTRIS uses the standard library only.
- **Original test data.** Write sample documents for the tests yourself; do not copy third-party
  scans or OCR output into the repository.
- **A line in [CHANGELOG.md](CHANGELOG.md)** under `Unreleased`, for anything a user would notice.

## Pull requests

Work on a branch and open a pull request against `main`. CI runs Ruff, mypy and the tests on
Linux, Windows and macOS with Python 3.12 to 3.14, and builds the package.

Every pull request is also checked by [Repro](https://github.com/DuhItzAniket/Repro), which runs
the tests on the base and the head, compares what the changed functions actually return on
each side, and posts a Reproduction Card on the pull request:

- **VERIFIED**: the behaviour that changed is the behaviour the pull request describes.
- **FLAGGED**: something changed that the description does not explain, a test was weakened, or
  a claim is contradicted. Read the card: it names the function, the inputs and both results.
- **UNVERIFIABLE**: too little could be checked, and the card says what.

So describe what your change does, including what it changes in the output. A refactor that
claims no behaviour change will be held to that.
