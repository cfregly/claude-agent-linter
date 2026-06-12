"""Render a lint report as a terminal table + findings list."""

from __future__ import annotations

SEV_MARK = {"error": "✗", "warn": "!", "info": "·"}


def render(report: dict, source: str) -> str:
    lines = []
    lines.append(f"MCP tool-contract report — {source}")
    lines.append(
        f"Server score: {report['server_score']}/100 "
        f"(grade {report['server_grade']})"
    )
    lines.append("")
    width = max((len(n) for n in report["tools"]), default=4)
    lines.append(f"{'tool':<{width}}  score  grade  findings")
    lines.append(f"{'-'*width}  -----  -----  --------")
    for name, t in sorted(report["tools"].items(), key=lambda kv: kv[1]["score"]):
        counts = {}
        for f in t["findings"]:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        summary = " ".join(
            f"{n}×{SEV_MARK[s]}" for s, n in sorted(counts.items())
        ) or "clean"
        lines.append(f"{name:<{width}}  {t['score']:>5}  {t['grade']:>5}  {summary}")
    lines.append("")
    for name, t in sorted(report["tools"].items(), key=lambda kv: kv[1]["score"]):
        for f in t["findings"]:
            param = f" ({f['param']})" if f.get("param") else ""
            lines.append(
                f"[{f['rule']} {f['severity']}] {name}{param}: {f['message']}"
            )
            lines.append(f"    fix: {f['fix']}")
    return "\n".join(lines)
