# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-13

### Added
- 14 contract rules (CD001-CD014), including the OWASP/STRIDE security lens, and
  5 protocol rules (PR001-PR005).
- Claude judge loop with deterministic re-scoring.
- `scripts/check_docs.py` doc-correctness gate that keeps the README rule count
  in sync with the code, and a CI workflow that reproduces the 19-to-100 marquee.
