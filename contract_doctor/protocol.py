"""Lint an agent operating protocol (AGENTS.md / SKILL.md style).

The tool linter scores the agent's *tools*; this scores the agent's *rules of
engagement*. The motion, from the AGENTS.md convention and the agent-developer
community: declare boundaries grouped into always-do / ask-first / never-do,
plus a failure plan and a success metric. An agent with no stated boundaries
acts on a guess, which is how autonomy turns into incidents.

A protocol starts at 100; each missing element is a finding. Same severity
weights as the tool linter: error -15, warn -8, info -3.
"""

from __future__ import annotations

import re

DEDUCTION = {"error": 15, "warn": 8, "info": 3}

# (rule, severity, label, detector, fix)
CHECKS = [
    ("PR001", "error", "always-do boundaries",
     re.compile(r"always[ -]?do|always:|\balways\b", re.I),
     "List what the agent may always do without asking. The 'always do' bucket."),
    ("PR002", "error", "ask-first boundaries",
     re.compile(r"ask[ -]?first|check with|confirm before|ask before|require[s]? approval", re.I),
     "List what the agent must check before doing. The 'ask first' bucket."),
    ("PR003", "error", "never-do boundaries",
     re.compile(r"never[ -]?do|never:|\bnever\b|must not|do not", re.I),
     "List what the agent must never do. The 'never do' bucket."),
    ("PR004", "warn", "a failure plan",
     re.compile(r"\bfail|failure|on error|when stuck|escalat|fallback|roll ?back|cannot complete", re.I),
     "Say what happens when the agent fails or gets stuck: escalate, roll back, or stop."),
    ("PR005", "warn", "a success metric",
     re.compile(r"success|metric|kpi|done when|definition of done|acceptance", re.I),
     "State how success is measured, so the agent knows when it is done."),
]


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def lint_agent_protocol(text: str) -> dict:
    """Score an agent-protocol document for the boundaries an agent needs."""
    t = text or ""
    findings = []
    for rule, severity, label, detector, fix in CHECKS:
        if not detector.search(t):
            findings.append({
                "rule": rule,
                "severity": severity,
                "message": f"protocol does not declare {label}",
                "fix": fix,
            })
    score = max(0, 100 - sum(DEDUCTION[f["severity"]] for f in findings))
    return {"score": score, "grade": grade(score), "findings": findings}
