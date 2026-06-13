# Contributing

Thanks for helping. This repo keeps a small, deterministic core and gates every
change in CI.

## Before you open a PR

Run the checks CI runs (see `.github/workflows/ci.yml` for the exact commands):

- the test suite
- `python scripts/check_docs.py` (the README stays consistent with the code)
- the de-slop gate on the README (`python -m deslop README.md`)

## House rules

- Keep it stdlib where the module already is. A new runtime dependency needs a
  reason.
- Numbers over adjectives. If you change a claim, change the measurement.
- One rule per change. A new lint rule ships with an example and a test.
- Plain prose: no em-dashes, no marketing words. The de-slop gate enforces it.

## Reporting bugs

Open an issue with the smallest input that reproduces the problem and the output
you expected.
