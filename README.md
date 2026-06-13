# claude-agent-linter

**Harden the agent and assistant interfaces.** Turn vague MCP tools into contract-grade agent interfaces. A vague example server scores 19/100; the contract-grade rewrite scores 100/100. 14 rules, including an OWASP/STRIDE security lens.

Most agent bugs aren't model failures - they're vague tool semantics. The model
is the caller of your API, and it can't read your source. A tool description
that says `"Gets the data."` forces the model to guess inputs, invent failure
handling, and coin-flip between overlapping tools. This linter makes those
contract gaps visible, scores them, gates them in CI, and (optionally) has
Claude rewrite the worst offender - then re-lints the rewrite, because evals
beat vibes even for prose.

- **Problem it solves:** agents misuse tools whose contracts are underspecified. Teams debug the model when they should be fixing the interface.
- **Run in under 5 minutes:** `python -m contract_doctor examples/vague_tools.json` - no dependencies, stdlib only.
- **Learn in 15 minutes:** the eleven contract rules below, the CI gate, and the judge loop.
- **Claude features it proves:** MCP tool schemas as a first-class surface, plus Claude-as-judge with deterministic re-validation.
- **Production lesson it encodes:** tool descriptions are API contracts. Failure modes and side effects are half the contract.

## Quickstart

```bash
git clone https://github.com/cfregly/claude-agent-linter && cd claude-agent-linter
python -m contract_doctor examples/vague_tools.json          # the "before"
python -m contract_doctor examples/contract_grade_tools.json # the "after"
python tests/test_rules.py                                   # the test suite
```

Lint a live FastMCP server directly (needs `pip install mcp`):

```bash
python -m contract_doctor path/to/your_fastmcp_server.py
```

Or dump any MCP server's `tools/list` response to JSON and lint that - the
linter reads the wire format, so it works for servers in any language.

## The before / after (actual output, run 2026-06-10)

The vague server - five tools the model has to guess at:

```
Server score: 19/100 (grade F)

tool           score  grade  findings
-------------  -----  -----  --------
send              11      F  5×✗ 2×· 1×!
process           13      F  4×✗ 1×· 3×!
handle_record     13      F  4×✗ 1×· 3×!
update            21      F  4×✗ 1×· 2×!
get_data          36      F  3×✗ 1×· 2×!

FAIL: 5 tool(s) below --min-score 70
```

The same five tools rewritten as contracts ([examples/contract_grade_tools.json](examples/contract_grade_tools.json)):

```
Server score: 100/100 (grade A)
```

## It caught a real one: my demo repo failed its own lint

The first real server this linter ever scored was the MCP server in the sibling repo
[`claude-prompt-to-production`](https://github.com/cfregly/claude-prompt-to-production) - 
a repo whose entire pitch is teaching tool-contract discipline. Its docstrings
preach the gospel: exact semantics, failure modes, what not to infer. The repo
even says, in a comment, *"vague descriptions are the #1 agent bug in the wild."*

It scored **77/100, grade C.**

Why: every parameter description was **empty in the published schema**. FastMCP
publishes your docstring as the *tool* description - but *parameter* docs come
from the input schema, and a plain `name: str` annotation ships nothing. So the
model received beautifully documented tools whose arguments (`name`, `month`)
carried zero documentation. The docstring discipline was real. It just never
reached the wire. The contract you write and the contract the model receives
are not the same artifact - and only one of them matters.

The fix took minutes: `Annotated[str, Field(description=...)]` on each
parameter, plus explicit failure-mode sentences in two docstrings (and a real
divide-by-zero guard the lint pressured into existence). The server re-lints at
**100/100, grade A** - and that commit lives in the sibling repo's history.

Three lessons worth keeping:

1. **Discipline you can't lint will drift** - even when you're the one teaching it.
2. **Lint the wire format, not the source.** This tool reads `tools/list` output,
   so it grades what the model actually sees, in any framework or language.
3. **The fail-closed instinct cuts both ways.** A linter that had only ever seen
   its own examples would be a toy. The first outside contact found a real bug
   in the author's own showcase. That is the test worth passing.

```bash
# gate your own server the same way
python -m contract_doctor your_tools.json --min-score 80 || exit 1
```

## The judge loop (actual output, run 2026-06-10)

```bash
ANTHROPIC_API_KEY=... pip install anthropic
python -m contract_doctor examples/vague_tools.json --judge
```

The deterministic rules pick the worst tool (`send`, score 11) and hand Claude
the definition plus the findings. Claude returns a rewritten contract - 
delivery semantics, non-idempotency declared, error shape per field, enum'd
priority tiers, worked example - and the linter re-scores it:

```
re-lint: 11 (F) -> 100 (A)
```

The judge writes prose. The linter keeps the score honest. That order matters.

## The fourteen rules

| Rule | Severity | What it catches |
|---|---|---|
| CD001 | error | One-line descriptions that aren't contracts |
| CD002 | warn | Generic names (`process`, `get_data`) that force routing guesses |
| CD003 | error | Parameters with no description - where agents invent arguments |
| CD004 | warn | Shaped strings (ids, dates, modes) with no enum/format/pattern |
| CD005 | error | No failure-mode documentation - the half of the contract everyone skips |
| CD006 | error | Mutating tools that don't declare side effects or idempotency |
| CD007 | warn | Undocumented return shape |
| CD008 | warn | Near-duplicate tools the model can't choose between |
| CD009 | info | No `required` array - the model guesses what it may omit |
| CD010 | info | 3+ parameters and no worked example |
| CD011 | warn | Marketing slop (`powerful`, `seamless`, `robust`) - adjectives spending tokens that semantics needs |
| CD012 | warn | Security: a raw secret passed as a model-visible argument |
| CD013 | warn | Security: a destructive op (delete, charge, transfer) with no stated reversibility or confirmation |
| CD014 | warn | Security: executes or forwards free-form input into a code, shell, SQL, or URL sink (injection / SSRF) |

CD012-CD014 are the agent/MCP slice of an OWASP + STRIDE pass: the threats that
are specific to tools an LLM can call. Each finding also carries a `fix_kind`
(`auto` for mechanical deletions, `ask` for judgment calls).

Scoring: each tool starts at 100. Error −15, warn −8, info −3. A ≥90, B ≥80,
C ≥65, D ≥50, F below.

## Gate it in CI

```bash
python -m contract_doctor mcp_tools.json --min-score 80 || exit 1
```

Exit code 1 the moment any tool drops below the bar - the same
evals-before-vibes wiring you'd give an agent's behavior, applied to the
agent's interface.

## Why this exists

This repo encodes a field lesson from AI-infrastructure work with neo-cloud
GPU providers and the startups I advise:
a production agent's tool-call error rate is usually an interface problem.
Rewriting tool descriptions as contracts - exact semantics, failure shapes,
side-effect declarations - is the cheapest reliability win in agent
engineering, and it's lintable. So lint it.

Pair-built with Claude. That's not a disclaimer, it's the demo.

## License

[MIT](LICENSE)
