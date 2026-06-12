"""CLI: lint an MCP server's tool contracts.

    python -m contract_doctor <tools.json | fastmcp_server.py> [options]

Options:
    --json           emit the full report as JSON instead of the table
    --min-score N    exit 1 if any tool scores below N (default 70) — CI gate
    --judge          rewrite the worst-scoring tool with Claude, re-lint it,
                     and print the before/after (needs ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import sys

from .loaders import load_tools
from .report import render
from .rules import grade, lint_server, lint_tool, score_tool


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="contract_doctor", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", help="tools JSON file or FastMCP server .py")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument("--judge", action="store_true")
    args = parser.parse_args(argv)

    tools = load_tools(args.source)
    report = lint_server(tools)

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report, args.source))

    if args.judge:
        worst_name = min(report["tools"], key=lambda n: report["tools"][n]["score"])
        worst = next(t for t in tools if t.get("name") == worst_name)
        worst_report = report["tools"][worst_name]
        print(f"\n--- judge: rewriting '{worst_name}' "
              f"(score {worst_report['score']}) with Claude ---")
        from .judge import rewrite_tool

        fixed = rewrite_tool(worst, worst_report["findings"])
        fixed_findings = lint_tool(fixed)
        fixed_score = score_tool(fixed_findings)
        print(json.dumps(fixed, indent=2))
        print(f"\nre-lint: {worst_report['score']} ({worst_report['grade']}) "
              f"-> {fixed_score} ({grade(fixed_score)})")
        if fixed_findings:
            for f in fixed_findings:
                print(f"  remaining [{f['rule']} {f['severity']}]: {f['message']}")

    failing = [
        name for name, t in report["tools"].items() if t["score"] < args.min_score
    ]
    if failing:
        print(
            f"\nFAIL: {len(failing)} tool(s) below --min-score {args.min_score}: "
            + ", ".join(sorted(failing)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
