"""The shared state that flows through the LangGraph workflow.

Every node reads from and writes to this dictionary. Using a TypedDict keeps the
shape explicit and lets editors catch typos.
"""
from typing import Optional, List, Dict, Any, TypedDict


class SupportState(TypedDict, total=False):
    # --- input / identity ---
    question: str                     # the customer's current message
    customer_id: Optional[str]        # resolved CloudNest customer id, or None (guest)
    customer: Optional[Dict[str, Any]]  # full customer record if known
    conversation_id: str              # id of this chat session
    history: List[Dict[str, Any]]     # prior messages for this customer (memory recall)

    # --- routing ---
    category: str                     # billing / technical / general / complaints

    # --- retrieval (RAG) ---
    retrieved: List[str]              # relevant knowledge-base chunks
    retrieval_scores: List[float]     # distance scores (lower = more similar)

    # --- agent output ---
    draft_response: str               # the agent's proposed reply to the customer
    can_answer: bool                  # False => the KB did not contain the answer
    action: str                       # none / issue_refund / cancel_account / create_ticket
    amount: Optional[float]           # dollar amount for a refund, if any
    action_reason: str                # short reason for the action / escalation

    # --- human-in-the-loop ---
    requires_approval: bool
    approval_reason: str              # why approval is needed (shown to the human)
    approval_decision: Optional[str]  # approve / reject / edit
    edited_response: Optional[str]    # replacement text if the human edited

    # --- result ---
    final_response: str               # what the customer actually sees
    escalated: bool
    ticket_id: Optional[str]
    executed_action: Optional[str]    # description of any tool that actually ran
