# Releasing

LECTRIS is released by `.github/workflows/release.yml`, in two stages, with PyPI's Trusted
Publishing: no token is stored anywhere, and PyPI receives exactly the files a dry run checked.

## One-time setup (the owner)

1. **PyPI: a pending publisher.** On PyPI, under *Your projects → Publishing → Add a new pending
   publisher* (GitHub), enter:
   - PyPI project name: `lectris`
   - Owner: the GitHub account that owns this repository
   - Repository name: `Lectris`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

   The project is created on PyPI by the first upload.
2. **GitHub: the `pypi` environment.** In the repository's *Settings → Environments*, create
   `pypi`, add yourself as a required reviewer, and limit it to protected branches and tags
   (or to `v*` tags). The upload job waits for your approval there.

## Each release

1. On a branch, set `version` in `pyproject.toml`, turn `Unreleased` in `CHANGELOG.md` into
   `## [X.Y.Z] - YYYY-MM-DD` (with the compare links at the bottom), and merge the pull request.
2. **Dry run.** *Actions → Release → Run workflow* on `main`, with the would-be tag `vX.Y.Z` and
   *dry run* ticked. It checks that the tag matches the version and that CHANGELOG has the
   section, runs the tests, builds the sdist and the wheel, installs the wheel alone in a fresh
   environment and runs it, and writes SHA256SUMS. It creates nothing.
3. **Tag** the merged commit: `git tag -a vX.Y.Z -m "LECTRIS X.Y.Z"` and push the tag.
4. **Draft.** Run the workflow again with the tag and *dry run* off. It builds from the tag, runs
   the same checks, and creates a **draft** GitHub release with the two files, SHA256SUMS, and the
   CHANGELOG section as its notes.
5. **Publish** the draft on GitHub after reading it. That starts the `pypi` job, which waits for
   your approval in the `pypi` environment, then checks the release's files against SHA256SUMS
   and uploads them to PyPI.

A tag push alone never runs the workflow, and a published release cannot be replaced by it.
