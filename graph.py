"""The LangGraph workflow that ties every piece together.

Flow:

    START
      -> load_memory   (identify customer, recall past messages)
      -> supervisor    (route to a specialist category)
      -> retrieve      (RAG over the knowledge base)
      -> agent         (specialist drafts a reply + decides on an action)
      -> [approval?]   (human-in-the-loop, only if the plan is sensitive)
      -> finalize      (run the tool or escalate, then save memory)
    END

A MemorySaver checkpointer is attached so the `approval_node` can interrupt the
run and resume later with the human's decision.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

import memory
import rag
from state import SupportState
from supervisor import supervisor_node
from agents import agent_node
from human_loop import approval_node


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------
def load_memory_node(state: dict) -> dict:
    cid = state.get("customer_id")
    customer = memory.get_customer(cid) if cid else None
    resolved = customer["customer_id"] if customer else None
    history = memory.get_history(
        resolved, limit=10, exclude_conversation=state.get("conversation_id")
    )
    return {"customer": customer, "customer_id": resolved, "history": history}


def retrieve_node(state: dict) -> dict:
    texts, scores = rag.retrieve(state["question"])
    return {"retrieved": texts, "retrieval_scores": scores}


def _summarise(state: dict, outcome: str) -> str:
    q = state["question"][:120]
    cat = state.get("category", "general")
    return f"[{cat}] Customer asked: \"{q}\". Outcome: {outcome}."


def finalize_node(state: dict) -> dict:
    """Carry out the plan (or escalate on rejection), then persist memory."""
    decision = state.get("approval_decision")  # None if no approval was needed
    required = state.get("requires_approval", False)
    action = state.get("action", "none")
    customer_id = state.get("customer_id")
    category = state.get("category", "general")

    escalated = False
    ticket_id = None
    executed_action = None

    # Base customer-facing text: an edit replaces the draft.
    if decision == "edit" and state.get("edited_response"):
        base_text = state["edited_response"]
    else:
        base_text = state.get("draft_response", "")

    extra = ""

    if required and decision == "reject":
        # Rejected: do NOT run refund/cancel. Escalate to a human instead.
        ticket_id = memory.create_ticket(
            customer_id, category,
            reason=f"Rejected {action}: {state.get('action_reason', '')}",
            status="escalated",
        )
        escalated = True
        base_text = ("I'm not able to complete that automatically. I've created "
                     f"escalation ticket {ticket_id}, and a human agent will "
                     "follow up with you within 24 hours.")
        outcome = f"rejected, escalated ({ticket_id})"
    else:
        # Approved, edited, or no approval needed -> execute the planned action.
        if action == "issue_refund" and customer_id and state.get("amount") is not None:
            result = memory.issue_refund(customer_id, float(state["amount"]),
                                         state.get("action_reason", ""))
            executed_action = result["message"]
            extra = "\n\n" + result["message"]
        elif action == "cancel_account" and customer_id:
            result = memory.cancel_account(customer_id, state.get("action_reason", ""))
            executed_action = result["message"]
            extra = "\n\n" + result["message"]
        elif action == "create_ticket":
            ticket_id = memory.create_ticket(
                customer_id, category,
                reason=state.get("action_reason", "") or "Escalation",
                status="escalated",
            )
            escalated = True
            executed_action = f"Created ticket {ticket_id}"
            extra = f"\n\n(Reference ticket: {ticket_id})"
        outcome = executed_action or "answered"

    final_response = (base_text + extra).strip()

    # ---- Persist conversation memory ----
    conv_id = state.get("conversation_id")
    if conv_id:
        memory.save_message(conv_id, customer_id, "customer", state["question"])
        memory.save_message(conv_id, customer_id, "assistant", final_response, agent=category)
        memory.save_summary(conv_id, customer_id, _summarise(state, outcome))

    return {
        "final_response": final_response,
        "escalated": escalated,
        "ticket_id": ticket_id,
        "executed_action": executed_action,
    }


def _route_after_agent(state: dict) -> str:
    return "approval" if state.get("requires_approval") else "finalize"


# --------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------
def build_graph():
    g = StateGraph(SupportState)
    g.add_node("load_memory", load_memory_node)
    g.add_node("supervisor", supervisor_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("agent", agent_node)
    g.add_node("approval", approval_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "load_memory")
    g.add_edge("load_memory", "supervisor")
    g.add_edge("supervisor", "retrieve")
    g.add_edge("retrieve", "agent")
    g.add_conditional_edges("agent", _route_after_agent,
                            {"approval": "approval", "finalize": "finalize"})
    g.add_edge("approval", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=MemorySaver())


def generate_workflow_png(path: str = "workflow.png") -> str:
    """Render the workflow to a PNG using local graphviz (no internet needed)."""
    from graphviz import Digraph

    dot = Digraph("CustomerSupportAI", format="png")
    dot.attr(rankdir="TB", fontname="Helvetica")
    dot.attr("node", shape="box", style="rounded,filled", fillcolor="#eef3fb",
             fontname="Helvetica")

    dot.node("START", "START", shape="oval", fillcolor="#d6f5d6")
    dot.node("load_memory", "load_memory\n(recall customer + history)")
    dot.node("supervisor", "supervisor\n(route to specialist)")
    dot.node("retrieve", "retrieve\n(RAG over knowledge base)")
    dot.node("agent", "agent\n(billing / technical / general / complaints)")
    dot.node("approval", "approval\n(human-in-the-loop)", fillcolor="#fdebd0")
    dot.node("finalize", "finalize\n(run tool or escalate, save memory)")
    dot.node("END", "END", shape="oval", fillcolor="#f5d6d6")

    dot.edge("START", "load_memory")
    dot.edge("load_memory", "supervisor")
    dot.edge("supervisor", "retrieve")
    dot.edge("retrieve", "agent")
    dot.edge("agent", "approval", label="sensitive")
    dot.edge("agent", "finalize", label="routine")
    dot.edge("approval", "finalize")
    dot.edge("finalize", "END")

    out = dot.render(filename=path.replace(".png", ""), cleanup=True)
    return out


if __name__ == "__main__":
    print("Workflow diagram written to:", generate_workflow_png())
