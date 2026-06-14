"""Deterministic lint rules for MCP tool contracts.

Each rule inspects one tool definition (name, description, inputSchema) and
yields findings. A finding is a dict: {rule, severity, tool, param, message, fix}.
Severities: error (-15), warn (-8), info (-3). A tool starts at 100; the floor is 0.

The rules encode one production lesson: most agent failures are vague tool
semantics, not model failures. A tool description is an API contract: the
model is the caller, and it can't read your source.
"""

from __future__ import annotations

import json
import pathlib
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

# CD006 wants a mutation to state its SAFETY contract, not just name the action.
# So this matches idempotency / retry-safety / reversibility language only -- not
# the verb. That makes it mood-agnostic: "Create a file" and "Creates a file"
# are treated the same (both fire unless they also declare retry-safety), instead
# of the old list where "deletes" suppressed CD006 but "removes" did not.
SIDE_EFFECT_LANGUAGE = re.compile(
    r"idempoten|side.?effect|reversibl|irreversibl|cannot be undone|permanent|"
    r"safe to (?:retry|repeat)|no-?op|no effect if|already exists|"
    r"at most once|exactly once|dedup",
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

# Marketing slop in a tool description spends tokens on vibes instead of
# semantics. The shared buzzword canon loads from slop_rules.json (synced from
# the claude-deslop repo; do not hand-edit). _AGENT_EXTRA adds the few words
# specific to tool-description fluff that do not belong in the cross-repo canon.
_RULES = json.loads((pathlib.Path(__file__).parent / "slop_rules.json").read_text())
_AGENT_EXTRA = ["powerful", "effortless", "easily", "intuitive", "magic"]

# --- security lens (CD012-CD014): the LLM/agent slice of an OWASP+STRIDE pass.
# A raw secret as a model-visible argument. "token" is left out on purpose: it
# collides with pagination tokens.
SECRET_PARAM = re.compile(
    r"(^|_)(password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|credential)($|_)", re.I)
SECRET_WORD = re.compile(
    r"\b(password|api[ _-]?key|secret key|private key|access key|"
    r"client secret|credential)\b", re.I)
# A reference to a secret, not the secret itself: a name, id, handle, or ARN
# that resolves server-side. This is the pattern CD012 tells you to use, so it
# must not be flagged as the very thing it fixes. Matches on the param name
# (secret_ref, key_id, secret_name) or a description that says it is a handle.
SECRET_HANDLE_PARAM = re.compile(
    r"(^|_)(ref|id|name|handle|alias|arn|uri|url|path|slug)($|_)", re.I)
SECRET_HANDLE_WORD = re.compile(
    r"\b(handle|reference|references|identifier|alias|by name|name of|arn|"
    r"server-side secret|secret manager|vault|never (?:passes|sent|exposed|"
    r"leaves)|not the (?:raw|actual) (?:secret|key))\b", re.I)
# Hard-to-reverse operations. Soft verbs (update, archive, send) are excluded;
# CD006 already governs ordinary mutations.
DESTRUCTIVE_VERB = re.compile(
    r"\b(delete|drop|purge|wipe|erase|truncate|charge|transfer|refund|revoke|"
    r"destroy|deploy)\b", re.I)
SAFETY_LANGUAGE = re.compile(
    r"\b(idempotent|reversible|undo|restore|recoverable|confirm|dry[ -]?run|"
    r"no-op|soft[ -]?delete|retain|suppress)", re.I)
# Executes or forwards free-form input into a powerful sink (injection / SSRF).
# The verb alternation matches conjugations on purpose: "Runs a SQL query" and
# "executes the command" are the same sink as "run"/"execute". Missing the
# plural form once let a raw-SQL tool score a clean B -- a security false
# negative is the worst kind, so the stems below cover run/runs/running,
# execute/executes/executing, evaluate/evaluates, and forward/forwards/passes.
INJECTION_SINK = re.compile(
    r"\b(?:execut\w*|eval(?:uat\w*)?|runs?|running|forward\w*|pass(?:es)?)\b"
    r"[^.]{0,30}\b(shell|command|code|sql|query|script)\b"
    r"|\bsubprocess\b|\bos\.system\b|\braw sql\b"
    r"|\brender[s]?\b[^.]{0,20}\bhtml\b"
    r"|\bfetch(?:es)?\b[^.]{0,30}\b(?:url|uri|endpoint)\b"
    r"|\bSSRF\b", re.I)
SLOP_LANGUAGE = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in _RULES["buzzwords"] + _AGENT_EXTRA)
    + r")[a-z]*",
    re.I,
)


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?]\s", text.strip()) if len(s) > 8])


# AUTO-FIX vs ASK, borrowed from gstack's review split. A finding is "auto"
# when the fix is mechanical (delete the offending tokens) and "ask" when it
# needs a judgment call: write real semantics, rename a tool, choose a shape.
# The judge applies auto fixes outright and surfaces ask findings for review.
FIX_KIND = {
    "CD011": "auto",  # delete the marketing words; nothing to decide
}


def fix_kind(rule: str) -> str:
    return FIX_KIND.get(rule, "ask")


def _finding(rule, severity, tool, message, fix, param=None):
    return {
        "rule": rule,
        "severity": severity,
        "tool": tool,
        "param": param,
        "message": message,
        "fix": fix,
        "fix_kind": fix_kind(rule),
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

    # CD003 — every parameter the model must fill needs a description that adds
    # something past the name. Empty is always a defect. A short description is
    # fine when it carries real information ("Commit message" adds "commit"), and
    # a defect when it only echoes the parameter name ("message", "id") or is
    # near-empty. Length alone is not the test: "Commit message" is 14 clear
    # characters, and flagging it as undocumented is noise on real servers.
    for pname, pschema in props.items():
        pdesc = (pschema.get("description") or "").strip()
        name_words = set(re.findall(r"[a-z]{2,}", pname.lower()))
        extra = set(re.findall(r"[a-z]{2,}", pdesc.lower())) - name_words
        if not pdesc or (len(pdesc) < 15 and not extra):
            shape = "has no description" if not pdesc \
                else f"only restates the name ({len(pdesc)} chars)"
            findings.append(_finding(
                "CD003", "error", name,
                f"parameter '{pname}' {shape}",
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

    # CD011 — marketing slop is anti-contract: it spends tokens on vibes.
    slop = sorted({m.group(0).lower() for m in SLOP_LANGUAGE.finditer(desc)})
    if slop:
        findings.append(_finding(
            "CD011", "warn", name,
            f"description contains slop ({', '.join(slop)}); adjectives are "
            "not semantics",
            "Delete the marketing words and spend the tokens on behavior: "
            "exact semantics, failure modes, return shape. The model routes "
            "on meaning, not enthusiasm.",
        ))

    # CD012 — a raw secret as a model-visible argument. The model (and its
    # transcript, and any logs) should never see the secret itself.
    for pname, pschema in props.items():
        pdesc = pschema.get("description") or ""
        if SECRET_PARAM.search(pname) or SECRET_WORD.search(pdesc):
            # A handle or reference is the fix, not the defect -- don't flag it.
            if SECRET_HANDLE_PARAM.search(pname) or SECRET_HANDLE_WORD.search(pdesc):
                continue
            findings.append(_finding(
                "CD012", "warn", name,
                f"parameter '{pname}' takes a raw secret as a model-visible argument",
                "Don't pass secrets through the model. Reference a server-side "
                "secret by name or handle and resolve it outside the model's view.",
                param=pname,
            ))

    # CD013 — a destructive, hard-to-reverse op with no stated safety contract.
    if (DESTRUCTIVE_VERB.search(name) or DESTRUCTIVE_VERB.search(desc)) \
            and not SAFETY_LANGUAGE.search(desc):
        findings.append(_finding(
            "CD013", "warn", name,
            "destructive operation with no stated safety contract",
            "State the blast radius: reversibility, idempotency, a confirm or "
            "dry-run path, or what is retained. Agents call destructive tools "
            "on a guess unless the contract says otherwise.",
        ))

    # CD014 — executes or forwards free-form input into a powerful sink. This is
    # the prompt/command-injection and SSRF surface.
    if INJECTION_SINK.search(desc):
        findings.append(_finding(
            "CD014", "warn", name,
            "injection surface: executes or forwards free-form input to a powerful sink",
            "Name the trust boundary: what is sanitized, parameterized, or "
            "allowlisted before this runs. Untrusted input into a code, shell, "
            "SQL, or URL sink is the injection path.",
        ))

    return findings


# Read/search verbs. Two tools that run the same verb-class on the same object
# ('search_tickets' vs 'find_tickets') read as distinct to a token-overlap check
# -- the synonyms 'search'/'find' and renamed params drag the score down -- yet
# they force the model into a coin flip. The shared-object signal below catches
# that case at a lower similarity bar than unrelated tools need.
_READ_VERBS = {"search", "find", "lookup", "list", "query", "fetch", "get",
               "retrieve", "read", "load", "show"}


def _name_parts(name: str) -> list[str]:
    return [p for p in re.split(r"[_\-]", (name or "").lower()) if p]


def _object_noun(name: str) -> str:
    parts = _name_parts(name)
    return parts[-1].rstrip("s") if parts else ""   # tickets -> ticket


def _lead_verb(name: str) -> str:
    parts = _name_parts(name)
    return parts[0] if parts else ""


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
        na, nb = a.get("name", ""), b.get("name", "")
        same_object = bool(_object_noun(na)) and _object_noun(na) == _object_noun(nb)
        both_read = _lead_verb(na) in _READ_VERBS and _lead_verb(nb) in _READ_VERBS
        # Unrelated tools need real text overlap; two read-verbs on the same
        # object trip at a lower bar because the names alone signal the dup.
        if jaccard > 0.55 or (same_object and both_read and jaccard > 0.30):
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
