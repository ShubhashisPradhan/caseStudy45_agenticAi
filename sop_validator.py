import json
import re
from pathlib import Path

def has_objective_guidelines_tools(system_msg: str) -> bool:
    return all(k in system_msg for k in ["**Objective**", "**Guidelines**", "**Available Tools**"])

def count_tools(tools) -> int:
    return len([t for t in tools if t.get("type") == "function"])

def user_has_unique_id(messages) -> bool:
    # naive: check user message contains "Case Study ID:" or "case_id"
    for m in messages:
        if m["role"] == "user" and ("Case Study ID:" in m["content"] or "case_id" in m["content"]):
            return True
    return False

def no_placeholders(text: str) -> bool:
    return ("YOUR_" not in text) and (re.search(r"\b[A-Z_]{6,}\b", text) is None)

def cot_placement_ok(messages) -> bool:
    # Must have at least one cot after user, and cot after each function response
    saw_user = False
    need_cot_after_fn = False
    for m in messages:
        if m["role"] == "user":
            saw_user = True
            need_cot_after_fn = False
        elif m["role"] == "cot" and saw_user and not need_cot_after_fn:
            # CoT directly after user ok
            pass
        elif m["role"] == "function":
            need_cot_after_fn = True
        elif m["role"] == "cot" and need_cot_after_fn:
            need_cot_after_fn = False
    return not need_cot_after_fn and saw_user

def main(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    system_msg = next(m["content"] for m in data["messages"] if m["role"] == "system")

    checks = {
        "System has Objective/Guidelines/Available Tools": has_objective_guidelines_tools(system_msg),
        "≥5 tools declared": count_tools(data.get("tools", [])) >= 5,
        "User input contains unique identifier": user_has_unique_id(data["messages"]),
        "No placeholders": all(no_placeholders(json.dumps(m)) for m in data["messages"]),
        "CoT placement correct": cot_placement_ok(data["messages"]),
    }
    print("SOP Validation Report")
    for k, v in checks.items():
        print(f"- {k}: {'PASS' if v else 'FAIL'}")
    overall = all(checks.values())
    print(f"\nOverall: {'PASS' if overall else 'FAIL'}")
    return overall

if __name__ == "__main__":
    main(Path("out/Case_Study_045_workflow.json"))
