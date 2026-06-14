# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.8] - 2026-06-13

### Fixed
- CD015 detection is narrowed to genuine raw-query passthroughs. A bare `raw` or
  `eval` token in a name is not an escape hatch: `import_model_eval` (model
  evaluation) and `raw_bench_compare` (raw benchmark data) are curated tools.
  Found by dogfooding the rule on a real 51-tool MCP server, where it false-fired
  on three of them.

## [0.1.7] - 2026-06-13

### Added
- CD015, a tool-discovery rule: a raw query/exec escape hatch (`run_sql`, a tool
  that forwards free-form SQL) sitting beside curated tools makes the agent
  prefer the passthrough and bypass the surface. This is the thin-zymtrace
  failure, where a coarse MCP surface drove agents to raw ClickHouse SELECTs
  instead of the server. Discovery is part of the contract: if the agent can
  route around your tools, they go unused.

## [0.1.6] - 2026-06-13

### Fixed
- CD006 mutation detection reads the verb's position, not just the leading
  token: a verb anywhere but the trailing object noun counts, so service-prefixed
  names ("slack_post_message", "stripe_charge_card") are mutations again while
  trailing verb-nouns ("list_charges", "github_get_post") stay reads.

## [0.1.5] - 2026-06-13

### Fixed
- CD006 judges "mutating" by the name's tokens, not a raw substring. A read
  whose object noun contains a verb ("list_charges", "get_payments", "get_post")
  is no longer mislabelled a mutation. Found by linting the real Stripe MCP.

## [0.1.4] - 2026-06-13

### Fixed
- CD012 catches auth-flavored tokens (`access_token`, `bearer_token`,
  `refresh_token`, `oauth_token`, `session_token`) passed as model-visible
  arguments. The broad `token` exclusion that avoids pagination false positives
  used to let a real bearer-token leak through unflagged. Pagination tokens
  (`next_token`, `page_token`, `cursor`) and secret handles stay exempt.

## [0.1.3] - 2026-06-13

### Fixed
- CD003 no longer flags a short but informative parameter description (for
  example "Commit message"). It fires on an empty description or one that only
  echoes the parameter name. Found by linting the official GitHub MCP server,
  which the linter used to flunk on clear descriptions.
- CD006 requires an idempotency or retry-safety statement in any verb mood, so
  "Create a file" and "Creates a file" are judged the same. The old list let
  "deletes" suppress the rule but not "removes", and imperative mood always
  tripped it.

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
