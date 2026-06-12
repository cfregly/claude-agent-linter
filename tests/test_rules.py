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


def test_grade_boundaries():
    assert grade(90) == "A" and grade(89) == "B" and grade(49) == "F"


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
