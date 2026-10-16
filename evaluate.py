"""Evaluation script for CustomerSupportAI.

Runs a set of scenarios through the full workflow and checks the system's
*behaviour* rather than exact wording (LLM output varies run to run). It covers:

  * correct routing to a specialist agent
  * RAG-grounded answers
  * handling of questions the knowledge base does not cover (escalation)
  * persistent memory recall across separate conversations
  * human approval being triggered for sensitive actions
  * rejection leading to escalation (and the action NOT running)
  * approval leading to the action actually running

To keep runs independent, the evaluation uses its own throwaway database
(eval_memory.db) and never touches your real memory.db.

Run:
    python evaluate.py
"""
import sys
from pathlib import Path

import memory  # imported first so we can redirect its database before use

# --- Redirect the data layer to a fresh evaluation database ---
EVAL_DB = Path(__file__).parent / "eval_memory.db"
if EVAL_DB.exists():
    EVAL_DB.unlink()
memory.DB_PATH = EVAL_DB

import rag
from graph import build_graph
from langgraph.types import Command

memory.init_db()
memory.seed_sample_data()
rag.build_vectorstore()
GRAPH = build_graph()

PASS, FAIL = 0, 0
_counter = [0]


def _tid() -> str:
    _counter[0] += 1
    return f"eval-{_counter[0]}"


def ask(question, customer_id=None, resume=None, thread=None):
    """Send a question through the graph, optionally resuming an approval."""
    tid = thread or _tid()
    cfg = {"configurable": {"thread_id": tid}}
    result = GRAPH.invoke(
        {"question": question, "customer_id": customer_id, "conversation_id": tid},
        config=cfg,
    )
    interrupted = "__interrupt__" in result
    if interrupted and resume is not None:
        result = GRAPH.invoke(Command(resume=resume), config=cfg)
    return result, interrupted


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def contains(text, *needles):
    t = (text or "").lower()
    return any(n.lower() in t for n in needles)


print("=" * 64)
print("CustomerSupportAI — evaluation")
print("=" * 64)

# 1. Routing: billing
r, _ = ask("Why was I charged $29 this month?", "CUST001")
check("1 routes billing question to billing agent", r.get("category") == "billing",
      f"got {r.get('category')}")

# 2. Routing: technical
r, _ = ask("I keep seeing error ERR_SYNC_409, what does it mean?", "CUST002")
check("2 routes technical question to technical agent", r.get("category") == "technical",
      f"got {r.get('category')}")
check("2b technical answer mentions file conflict",
      contains(r.get("final_response"), "conflict"), "no conflict guidance")

# 3. Routing: general + RAG grounding
r, _ = ask("Which operating systems does CloudNest support?")
check("3 general answer is RAG-grounded (lists OSes)",
      contains(r.get("final_response"), "windows", "macos", "android", "ios"),
      "OS list not found")

# 4. Routing: complaints + approval triggered
r, i = ask("This is terrible! I'm furious and want to speak to a human NOW.",
           "CUST003", resume={"decision": "approve"})
check("4 angry message routes to complaints", r.get("category") == "complaints",
      f"got {r.get('category')}")
check("4b complaint triggered human approval", i is True)

# 5. RAG grounding: refund window is 30 days
r, _ = ask("How long do I have to request a refund?", "CUST007")
check("5 refund window answer mentions 30 days",
      contains(r.get("final_response"), "30"), "30 not mentioned")

# 6. Missing info -> escalation (not in knowledge base)
r, i = ask("Does CloudNest integrate with Salesforce?", resume={"decision": "approve"})
check("6 unknown topic triggers low-confidence approval", i is True,
      "no approval for unknown topic")
check("6b unknown topic escalates", r.get("escalated") is True, "not escalated")

# 7. Large refund -> approval required, approve -> executed
r, i = ask("Please refund my last payment.", "CUST006",  # CUST006 latest order = $990
           resume={"decision": "approve"})
check("7 large refund requires approval", i is True)
check("7b approved refund executes",
      contains(str(r.get("executed_action")), "refund"), f"executed={r.get('executed_action')}")
check("7c order marked refunded in DB",
      memory.get_latest_order("CUST006")["status"] == "refunded")

# 8. Small refund -> no approval, executed
r, i = ask("Can I get a refund on my $9 charge?", "CUST011",
           resume={"decision": "approve"})
check("8 small refund needs NO approval", i is False, "unexpected approval")
check("8b small refund executed",
      memory.get_latest_order("CUST011")["status"] == "refunded")

# 9. Cancellation -> approval, reject -> escalated, subscription untouched
r, i = ask("I want to cancel my subscription.", "CUST010",
           resume={"decision": "reject"})
check("9 cancellation requires approval", i is True)
check("9b rejected cancellation escalates", r.get("escalated") is True)
check("9c rejected cancellation does NOT cancel the plan",
      memory.get_subscription("CUST010")["status"] == "active",
      f"status={memory.get_subscription('CUST010')['status']}")

# 10. Cancellation -> approve -> actually cancelled
r, i = ask("Please cancel my account.", "CUST012", resume={"decision": "approve"})
check("10 approved cancellation cancels the plan",
      memory.get_subscription("CUST012")["status"] == "cancelled",
      f"status={memory.get_subscription('CUST012')['status']}")

# 11. Guest cannot perform account actions -> escalate
r, i = ask("Refund me $50 right now.", None, resume={"decision": "approve"})
check("11 guest refund is blocked and escalated",
      r.get("escalated") is True or i is True, "guest refund not gated")

# 12. Persistent memory across separate conversations
conv_a = "eval-memtest-a"
ask("My files on CUST014 keep failing to sync on my laptop.", "CUST014", thread=conv_a)
history_before_second_conv = memory.get_history("CUST014", exclude_conversation="eval-memtest-b")
check("12 message from first conversation is persisted",
      len(history_before_second_conv) >= 1, "history empty")
check("12b history recalls the earlier sync issue",
      contains(" ".join(m["content"] for m in history_before_second_conv), "sync"),
      "earlier topic not recalled")

print("-" * 64)
total = PASS + FAIL
print(f"RESULT: {PASS}/{total} checks passed, {FAIL} failed.")
print("-" * 64)
sys.exit(1 if FAIL else 0)
