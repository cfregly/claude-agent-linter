"""Optional Claude judge: rewrite the worst tool contract, then re-lint it.

Deterministic rules find the violations; the judge writes the fix. The loop
closes when the linter re-scores the rewrite — the same eval-before-vibes
discipline you'd apply to any agent change.

Requires ANTHROPIC_API_KEY and `pip install anthropic`.
"""

from __future__ import annotations

import json

MODEL = "claude-sonnet-4-6"

SYSTEM = """You rewrite MCP tool definitions into contract-grade interfaces.
You will receive one tool's JSON definition and the linter findings against it.
Return ONLY the rewritten tool as JSON with the same keys (name, description,
inputSchema). Keep the tool's purpose identical. Fix every finding: precise
2-4 sentence description with exact semantics, documented failure modes,
declared side effects/idempotency for mutations, a description for every
parameter, enums/formats/patterns for shaped strings, and a 'required' array.
Rename the tool only if the linter flagged the name as generic.
Write the contract plain: no marketing adjectives ('powerful', 'seamless',
'robust'), no filler, no em-dashes. Every sentence states semantics the
caller can act on; an adjective that carries no behavior gets cut."""


def rewrite_tool(tool: dict, findings: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                "Tool definition:\n```json\n"
                + json.dumps(tool, indent=2)
                + "\n```\n\nLinter findings:\n```json\n"
                + json.dumps(findings, indent=2)
                + "\n```"
            ),
        }],
    )
    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"judge returned no JSON object:\n{text}")
    return json.loads(text[start : end + 1])
