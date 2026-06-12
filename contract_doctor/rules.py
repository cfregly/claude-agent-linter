"""Deterministic lint rules for MCP tool contracts.

Each rule inspects one tool definition (name, description, inputSchema) and
yields findings. A finding is a dict: {rule, severity, tool, param, message, fix}.
Severities: error (-15), warn (-8), info (-3). A tool starts at 100; the floor is 0.

The rules encode one production lesson: most agent failures are vague tool
semantics, not model failures. A tool description is an API contract — the
model is the caller, and it can't read your source.
"""

from __future__ import annotations

import re
from itertools import combinations

DEDUCTION = {"error": 15, "warn": 8, "info": 3}

GENERIC_NAME_TOKENS = {
    "process", "handle", "do", "run", "manage", "data", "info", "util",
    "utils", "exec", "stuff", "thing", "things", "misc", "helper", "get_data",
    "task", "action", "item", "main", "func", "call", "general",
}

MUTATING_VERBS = (
    "create", "update", "delete", "remove", "send", "post", "write", "set_",
    "add", "insert", "upload", "execute", "deploy", "cancel", "charge", "pay",
    "transfer", "publish", "submit",
)

SIDE_EFFECT_LANGUAGE = re.compile(
    r"idempoten|side.?effect|irreversibl|creates|updates|deletes|modifies|"
    r"overwrites|sends|appends|cannot be undone|permanent|safe to retry|"
    r"no effect if|already exists",
    re.I,
)

FAILURE_LANGUAGE = re.compile(
    r"error|fail|invalid|not found|missing|returns null|empty list|raises|"
    r"reject|unknown|does not exist|out of range",
    re.I,
)

RETURN_LANGUAGE = re.compile(r"\breturn|emits|produces|outputs|respond", re.I)

SHAPE_HINT = re.compile(
    r"YYYY|ISO[- ]?8601|e\.g\.|one of|must be|format|pattern|uuid|email|url|"
    r"slug|two-letter|comma-separated|case-insensitive",
    re.I,
)

SHAPED_PARAM_NAME = re.compile(
    r"(^|_)(id|date|month|day|time|type|mode|status|level|currency|region|"
    r"lang|language|email|url|phone|code)($|_)",
    re.I,
)


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?]\s", text.strip()) if len(s) > 8])


def _finding(rule, severity, tool, message, fix, param=None):
    return {
        "rule": rule,
        "severity": severity,
        "tool": tool,
        "param": param,
        "message": message,
        "fix": fix,
    }


def lint_tool(tool: dict) -> list[dict]:
    """Run all single-tool rules. Returns a list of findings."""
    name = tool.get("name", "<unnamed>")
    desc = (tool.get("description") or "").strip()
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    props = schema.get("properties") or {}
    findings = []

    # CD001 — description is the contract; one vague line is not a contract.
    if len(desc) < 80 or _sentences(desc) < 2:
        findings.append(_finding(
            "CD001", "error", name,
            f"description is {len(desc)} chars / {_sentences(desc)} sentence(s); "
            "a contract needs semantics, valid inputs, and edge behavior",
            "Write 2+ sentences: exact behavior, supported inputs, and what "
            "happens on bad input. The model is the caller and can't read your source.",
        ))

    # CD002 — generic names make the model guess which tool to call.
    name_tokens = set(name.lower().replace("-", "_").split("_"))
    generic = name_tokens & GENERIC_NAME_TOKENS
    if name.lower() in GENERIC_NAME_TOKENS or (generic and len(name_tokens) <= 2):
        findings.append(_finding(
            "CD002", "warn", name,
            f"name '{name}' is generic ({', '.join(sorted(generic) or [name])})",
            "Rename to verb_noun with domain nouns, e.g. 'search_customer_records' "
            "not 'get_data'.",
        ))

    # CD003 — every parameter the model must fill needs a description.
    for pname, pschema in props.items():
        pdesc = (pschema.get("description") or "").strip()
        if len(pdesc) < 15:
            findings.append(_finding(
                "CD003", "error", name,
                f"parameter '{pname}' has no usable description ({len(pdesc)} chars)",
                "Describe the parameter's meaning, accepted values, and an example. "
                "Undocumented params are where agents invent arguments.",
                param=pname,
            ))

    # CD004 — shaped string params need a declared shape (enum/format/pattern
    # or an explicit hint in the description).
    for pname, pschema in props.items():
        if pschema.get("type") != "string":
            continue
        if any(k in pschema for k in ("enum", "format", "pattern", "examples")):
            continue
        pdesc = pschema.get("description") or ""
        if SHAPED_PARAM_NAME.search(pname) and not SHAPE_HINT.search(pdesc):
            findings.append(_finding(
                "CD004", "warn", name,
                f"string parameter '{pname}' looks shaped (id/date/type/...) but "
                "declares no enum, format, pattern, or example",
                "Add an enum/format/pattern to the schema, or state the shape in "
                "the description (e.g. \"month as 'YYYY-MM'\").",
                param=pname,
            ))

    # CD005 — the failure path is half the contract.
    if desc and not FAILURE_LANGUAGE.search(desc):
        findings.append(_finding(
            "CD005", "error", name,
            "description never says what happens on bad input or missing data",
            "State the failure mode explicitly, e.g. 'Returns {\"error\": ...} "
            "with valid options if the id does not exist.' Agents that don't know "
            "the failure shape hallucinate around it.",
        ))

    # CD006 — mutations must declare side effects and idempotency.
    lowered = name.lower()
    if any(lowered.startswith(v) or f"_{v}" in lowered for v in MUTATING_VERBS):
        if not SIDE_EFFECT_LANGUAGE.search(desc):
            findings.append(_finding(
                "CD006", "error", name,
                f"'{name}' looks mutating but declares no side effects or "
                "idempotency",
                "Say what changes, whether a retry is safe, and whether the "
                "action is reversible. Agent loops retry; undeclared mutations "
                "double-charge.",
            ))

    # CD007 — say what comes back, or the model invents a shape.
    if desc and not RETURN_LANGUAGE.search(desc):
        findings.append(_finding(
            "CD007", "warn", name,
            "description never documents the return value",
            "State the return shape, e.g. 'Returns JSON: {runway_months, "
            "cash_on_hand, monthly_burn}.'",
        ))

    # CD009 — declare which params are required.
    if props and "required" not in schema:
        findings.append(_finding(
            "CD009", "info", name,
            "inputSchema has properties but no 'required' array",
            "Declare required params explicitly; the model otherwise guesses "
            "which arguments it may omit.",
        ))

    # CD010 — complex tools deserve a worked example.
    if len(props) >= 3 and "example" not in (desc + str(props)).lower():
        findings.append(_finding(
            "CD010", "info", name,
            f"{len(props)} parameters and no worked example anywhere",
            "Add one example call in the description; examples beat prose for "
            "multi-param tools.",
        ))

    return findings


def lint_overlap(tools: list[dict]) -> list[dict]:
    """CD008 — near-duplicate tools make routing a coin flip."""
    findings = []

    def tokens(t):
        text = f"{t.get('name','')} {t.get('description','')}".lower()
        return set(re.findall(r"[a-z]{3,}", text))

    for a, b in combinations(tools, 2):
        ta, tb = tokens(a), tokens(b)
        if not ta or not tb:
            continue
        jaccard = len(ta & tb) / len(ta | tb)
        if jaccard > 0.55:
            findings.append(_finding(
                "CD008", "warn", a.get("name"),
                f"overlaps with '{b.get('name')}' (similarity {jaccard:.2f}); "
                "the model can't reliably choose between them",
                "Merge the tools, or sharpen each description with a 'use this "
                "when / not when' boundary.",
            ))
    return findings


def score_tool(findings: list[dict]) -> int:
    score = 100
    for f in findings:
        score -= DEDUCTION[f["severity"]]
    return max(score, 0)


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


def lint_server(tools: list[dict]) -> dict:
    """Lint every tool plus cross-tool rules. Returns the full report dict."""
    per_tool = {}
    overlap = lint_overlap(tools)
    for tool in tools:
        name = tool.get("name", "<unnamed>")
        findings = lint_tool(tool) + [f for f in overlap if f["tool"] == name]
        per_tool[name] = {
            "score": score_tool(findings),
            "grade": grade(score_tool(findings)),
            "findings": findings,
        }
    scores = [t["score"] for t in per_tool.values()] or [0]
    server_score = round(sum(scores) / len(scores))
    return {
        "server_score": server_score,
        "server_grade": grade(server_score),
        "tools": per_tool,
    }
