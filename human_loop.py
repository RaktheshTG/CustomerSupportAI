"""Human-in-the-loop approval.

When the agent plans something sensitive (a large refund, a cancellation, an
angry complaint, or a low-confidence answer), the workflow must pause and let a
human decide. We use LangGraph's `interrupt()` so the graph genuinely halts and
can be resumed later with the human's decision — this is the canonical
human-in-the-loop pattern, not a fake pause.

The graph node is `approval_node`. The command-line front end collects the
decision with `prompt_for_approval()` and resumes the graph with it.
"""
from typing import Dict, Any

from langgraph.types import interrupt


def approval_node(state: dict) -> dict:
    """Pause the graph and wait for a human decision.

    `interrupt()` suspends execution and surfaces the payload to the caller. When
    the caller resumes with `Command(resume=<decision>)`, that value is returned
    here and becomes the node's output.
    """
    decision: Dict[str, Any] = interrupt(
        {
            "type": "approval_request",
            "reason": state.get("approval_reason", ""),
            "category": state.get("category"),
            "action": state.get("action"),
            "amount": state.get("amount"),
            "draft_response": state.get("draft_response", ""),
        }
    )
    choice = str(decision.get("decision", "reject")).strip().lower()
    if choice not in {"approve", "reject", "edit"}:
        choice = "reject"
    return {
        "approval_decision": choice,
        "edited_response": decision.get("edited"),
    }


def prompt_for_approval(payload: Dict[str, Any]) -> Dict[str, Any]:
    """CLI helper: show the pending action to the human and collect a decision.

    Returns a dict like {"decision": "approve"} or
    {"decision": "edit", "edited": "new text"}.
    """
    print("\n" + "=" * 60)
    print("  HUMAN APPROVAL REQUIRED")
    print("=" * 60)
    print(f"  Reason : {payload.get('reason')}")
    action = payload.get("action")
    if action and action != "none":
        amount = payload.get("amount")
        amount_str = f" (${amount:.2f})" if isinstance(amount, (int, float)) else ""
        print(f"  Action : {action}{amount_str}")
    print("  Proposed reply to customer:")
    print("  " + "-" * 56)
    for line in str(payload.get("draft_response", "")).splitlines() or [""]:
        print(f"  | {line}")
    print("  " + "-" * 56)
    print("  Choose:  [a]pprove   [r]eject   [e]dit")

    while True:
        choice = input("  Decision (a/r/e): ").strip().lower()
        if choice in {"a", "approve"}:
            return {"decision": "approve"}
        if choice in {"r", "reject"}:
            return {"decision": "reject"}
        if choice in {"e", "edit"}:
            print("  Enter the corrected reply, then press Enter:")
            edited = input("  > ").strip()
            return {"decision": "edit", "edited": edited}
        print("  Please type a, r, or e.")
