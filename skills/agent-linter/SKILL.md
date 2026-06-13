---
name: agent-linter
description: >-
  Harden an agent's tools and protocol with Claude. Lint MCP tool definitions
  into contract-grade interfaces, scored against 14 rules including an
  OWASP/STRIDE security lens (secrets, destructive ops, injection), then
  optionally have Claude rewrite the worst tool and re-score it. Also check an
  agent protocol for the always-do / ask-first / never-do boundaries and a
  failure plan. Use when someone wants to lint MCP tools, harden an agent,
  review tool descriptions, gate tool quality in CI, or write an agent
  operating protocol. Triggers on "lint my MCP tools", "harden my agent",
  "tool descriptions", "is my agent safe", "agent protocol", or
  "always ask-first never".
---

# agent-linter

Most agent bugs are vague tool semantics, not model failures. A tool
description is an API contract: the model is the caller and cannot read your
source. This skill scores the contract, gates it, and optionally has Claude
rewrite the worst offender, then re-lints the rewrite.

## Workflow

### 1. Get the tools on the wire
Dump the MCP server's `tools/list` response to JSON, or point the linter at a
FastMCP server file. The linter reads the wire format, so it grades what the
model actually receives, in any language.

### 2. Lint and read the findings
`python -m contract_doctor your_tools.json`. Each tool starts at 100. The rules
catch thin descriptions, generic names, undocumented params and returns,
missing failure modes, undeclared mutations, overlap, and the security slice: a
raw secret as a model-visible argument, a destructive op with no safety
contract, and free-form input into a code, shell, SQL, or URL sink.

### 3. Fix, then gate
Fix every error, justify every surviving warning. Gate it in CI:
`python -m contract_doctor your_tools.json --min-score 80 || exit 1`.

### 4. Optional: the judge loop
`--judge` hands Claude the worst tool plus its findings; Claude rewrites the
contract and the linter re-scores it. The judge writes prose, the linter keeps
the score honest.

### 5. Write the agent protocol
For the agent itself, declare boundaries the way the AGENTS.md convention does:
group instructions into always-do, ask-first, and never-do, and add a failure
plan and a success metric. An agent with no stated boundaries acts on a guess.

## What NOT to do
- Never lint the source docstring instead of the published schema. Only the
  wire contract reaches the model.
- Never pass a secret through the model to satisfy a tool signature.
- Never ship a destructive tool without a stated reversibility or confirm path.
