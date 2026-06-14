"""Run with: python -m tests.test_rules (stdlib only, no pytest needed)."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from contract_doctor.rules import grade, lint_server, lint_tool, score_tool

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


def load(name):
    return json.loads((EXAMPLES / name).read_text())["tools"]


def test_vague_server_fails():
    report = lint_server(load("vague_tools.json"))
    assert report["server_grade"] == "F", report["server_score"]
    assert all(t["score"] < 70 for t in report["tools"].values())


def test_contract_grade_server_passes():
    report = lint_server(load("contract_grade_tools.json"))
    assert report["server_grade"] == "A", report["server_score"]
    assert all(t["score"] >= 90 for t in report["tools"].values())


def test_mutation_without_side_effects_is_flagged():
    tool = {
        "name": "delete_account",
        "description": "Removes the account from the database immediately. "
        "Returns the deleted id, or an error if the id is unknown.",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Account id, e.g. 'acc_12345678'."}
        }, "required": ["id"]},
    }
    rules = {f["rule"] for f in lint_tool(tool)}
    # "Removes the account" describes behavior but never declares idempotency
    # or retry safety, so CD006 must still fire.
    assert "CD006" in rules, rules


def test_slop_description_is_flagged():
    tool = {
        "name": "search_invoices",
        "description": "A powerful tool that seamlessly searches invoices. "
        "Returns matching invoice records, or an error if the query is invalid.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Full-text query over invoice fields."}
        }, "required": ["query"]},
    }
    findings = lint_tool(tool)
    cd011 = [f for f in findings if f["rule"] == "CD011"]
    assert cd011, findings
    # The finding names the offending words so the fix is mechanical.
    assert "powerful" in cd011[0]["message"] and "seamlessly" in cd011[0]["message"]


def test_overlap_is_flagged():
    twins = [
        {"name": "fetch_user", "description": "Fetch the user profile record "
         "by id and return it as JSON for display in the dashboard."},
        {"name": "get_user", "description": "Fetch the user profile record "
         "by id and return it as JSON for display in the profile page."},
    ]
    report = lint_server(twins)
    rules = {f["rule"] for t in report["tools"].values() for f in t["findings"]}
    assert "CD008" in rules, rules


def test_findings_carry_auto_vs_ask_fix_kind():
    tool = {
        "name": "search_invoices",
        "description": "A powerful tool that seamlessly searches invoices.",
        "inputSchema": {"type": "object", "properties": {}},
    }
    by_rule = {f["rule"]: f["fix_kind"] for f in lint_tool(tool)}
    # marketing slop is mechanical: delete the words
    assert by_rule["CD011"] == "auto"
    # a thin description needs real semantics written: a judgment call
    assert by_rule["CD001"] == "ask"


def test_security_rules_flag_secret_destructive_and_injection():
    secret = {
        "name": "open_db_connection",
        "description": "Open a pooled database connection and return a connection "
        "handle as JSON. Idempotent: calling twice returns the same handle.",
        "inputSchema": {"type": "object", "properties": {
            "password": {"type": "string", "description": "The database password to authenticate with."}
        }, "required": ["password"]},
    }
    assert "CD012" in {f["rule"] for f in lint_tool(secret)}

    destructive = {
        "name": "delete_account",
        "description": "Permanently delete the account and all associated data from "
        "the database. Returns the deleted id, or an error if the id is unknown.",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Account id, e.g. 'acc_12345678'."}
        }, "required": ["id"]},
    }
    assert "CD013" in {f["rule"] for f in lint_tool(destructive)}

    injection = {
        "name": "run_analytics_query",
        "description": "Execute the given SQL query against the analytics warehouse "
        "and return matching rows as a JSON list. The query runs read-only.",
        "inputSchema": {"type": "object", "properties": {
            "sql": {"type": "string", "description": "A SQL SELECT statement, e.g. 'SELECT 1'."}
        }, "required": ["sql"]},
    }
    assert "CD014" in {f["rule"] for f in lint_tool(injection)}


def test_contract_grade_tools_have_no_security_findings():
    # The clean example must not trip the security lens (keeps it grade A).
    report = lint_server(load("contract_grade_tools.json"))
    sec = {"CD012", "CD013", "CD014"}
    for t in report["tools"].values():
        assert not (sec & {f["rule"] for f in t["findings"]}), t["findings"]


def test_injection_sink_catches_conjugated_verbs():
    # Regression: "Runs"/"executes" must trip CD014 like "run"/"execute". The
    # plural form slipped through once and a raw-SQL tool scored a clean B --
    # a security false negative is the worst kind.
    for desc in [
        "Runs a SQL query against the warehouse and returns the rows. Pass any "
        "SQL string and it executes against the read replica.",
        "Forwards the command to the system shell and returns stdout.",
    ]:
        tool = {"name": "do_thing", "description": desc,
                "inputSchema": {"type": "object", "properties": {}}}
        assert "CD014" in {f["rule"] for f in lint_tool(tool)}, desc


def test_overlap_catches_synonym_verbs_on_same_object():
    # 'search_tickets' vs 'find_tickets' share no verb token and rename their
    # params, so raw token overlap is low (~0.43) -- but they are the same
    # tool. The shared-object + read-verb signal must still flag the dup.
    twins = [
        {"name": "search_tickets", "description": "Search the support ticket "
         "database by keyword and status. Returns tickets matching the query so "
         "the agent can find the relevant conversation before acting."},
        {"name": "find_tickets", "description": "Look up support tickets in the "
         "database using a search term and an optional status filter. Returns the "
         "tickets that match so the agent can locate the right conversation."},
    ]
    report = lint_server(twins)
    rules = {f["rule"] for t in report["tools"].values() for f in t["findings"]}
    assert "CD008" in rules, rules


def test_realistic_server_lands_in_the_middle_band_with_security_findings():
    # The bundled realistic server scores in the C band, between the vague
    # example (19) and the contract-grade rewrite (100). The dangerous tools
    # must surface the security lens: a secret-as-arg and a destructive money
    # tool with no safety contract, a raw-SQL sink, and a duplicate pair.
    report = lint_server(load("realistic_tools.json"))
    assert 55 <= report["server_score"] < 80, report["server_score"]
    refund = {f["rule"] for f in report["tools"]["issue_refund"]["findings"]}
    assert {"CD012", "CD013"} <= refund, refund
    allrules = {f["rule"] for t in report["tools"].values() for f in t["findings"]}
    assert "CD014" in allrules and "CD008" in allrules, allrules


def test_protocol_flags_missing_boundaries():
    from contract_doctor.protocol import lint_agent_protocol
    rep = lint_agent_protocol("This agent summarizes invoices for the finance team.")
    rules = {f["rule"] for f in rep["findings"]}
    assert {"PR001", "PR002", "PR003"} <= rules
    assert rep["grade"] == "F"


def test_protocol_passes_with_boundaries():
    from contract_doctor.protocol import lint_agent_protocol
    doc = ("Always do: read-only queries. Ask first: any write or delete. "
           "Never do: move money or change permissions. On failure, escalate to a "
           "human. Success metric: the ticket is resolved and logged.")
    rep = lint_agent_protocol(doc)
    assert rep["score"] == 100 and not rep["findings"]


def test_grade_boundaries():
    assert grade(90) == "A" and grade(89) == "B" and grade(49) == "F"


def test_secret_handle_is_not_flagged_but_raw_secret_is():
    # CD012 must not punish the pattern it recommends: a handle/reference that
    # resolves server-side is the fix, not the defect. A raw secret still trips.
    handle = {"name": "charge_card", "description": "Charges the card and returns "
              "a receipt id. Returns an error if the card is declined. Idempotent "
              "on idempotency_key.", "inputSchema": {"type": "object", "properties": {
                  "secret_ref": {"type": "string", "description": "A handle naming "
                  "the server-side Stripe key. The raw key never passes through the model."}}}}
    raw = {"name": "charge", "description": "Charges a card. Returns an error if "
           "declined.", "inputSchema": {"type": "object", "properties": {
               "api_key": {"type": "string", "description": "The Stripe secret key to authorize with."}}}}
    assert "CD012" not in {f["rule"] for f in lint_tool(handle)}
    assert "CD012" in {f["rule"] for f in lint_tool(raw)}


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
