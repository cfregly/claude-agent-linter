# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-06-13

### Fixed
- CD012 no longer flags a secret handle or reference (`secret_ref`, `key_id`, or
  a description that says the raw key never reaches the model). That is the
  pattern CD012 recommends, so flagging it punished the fix. A raw secret as a
  model-visible argument still trips it.

### Changed
- Synced the deslop canon to 1.1.0 (extended dash set).

## [0.1.1] - 2026-06-13

### Fixed
- CD014 (injection sink) now catches conjugated verbs (`Runs a SQL query`,
  `executes the command`), closing a security false negative where a tool that
  forwards raw SQL scored a clean B.
- CD008 (overlap) flags the same object under synonym verbs (`search_tickets`
  vs `find_tickets`) that raw token overlap missed, using a shared-object plus
  read-verb signal.

## [0.1.0] - 2026-06-13

### Added
- 14 contract rules (CD001-CD014), including the OWASP/STRIDE security lens, and
  5 protocol rules (PR001-PR005).
- Claude judge loop with deterministic re-scoring.
- `scripts/check_docs.py` doc-correctness gate that keeps the README rule count
  in sync with the code, and a CI workflow that reproduces the 19-to-100 marquee.
