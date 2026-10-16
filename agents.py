"""The four specialist agents.

Each agent receives the customer's question, the knowledge-base chunks retrieved
by RAG, the customer's record, and recent conversation history. It produces a
single structured JSON object describing:

  * response   - the customer-facing reply
  * can_answer - False when the knowledge base does not contain the answer
  * action     - none | issue_refund | cancel_account | create_ticket
  * amount     - dollar amount for a refund (or null)
  * reason     - a short internal reason for the action / escalation

Code (not the model) then decides whether human approval is required, using the
rules in config.py. Keeping that decision in code makes it reliable and auditable
rather than leaving it to the model.
"""
import json
from typing import Dict, Any

from langchain_ollama import ChatOllama

import memory
from config import (
    CHAT_MODEL, OLLAMA_BASE_URL, COMPANY_NAME,
    REFUND_APPROVAL_THRESHOLD, LOW_CONFIDENCE_DISTANCE,
)

_llm = ChatOllama(
    model=CHAT_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
    format="json",
)

# A separate, deterministic classifier used only for billing messages. Extracting
# the requested action in a focused step is far more reliable than asking the
# response-writing model to also get it right, so refund/cancel requests are not
# missed.
_intent_llm = ChatOllama(
    model=CHAT_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    format="json",
)

_INTENT_PROMPT = """You analyse a CloudNest customer's billing message and decide
what action they are REQUESTING to be performed on their account:

- "issue_refund": they want money back / a refund actually processed.
- "cancel_account": they want to cancel, close, or end their subscription/account.
- "none": they are only ASKING a question (about the refund policy, pricing, or
  why they were charged) and are NOT requesting the action be performed.

Examples:
"Please refund my last payment" -> {{"intent":"issue_refund","amount":null}}
"I want a refund of $50" -> {{"intent":"issue_refund","amount":50}}
"Can I get a refund on my $9 charge?" -> {{"intent":"issue_refund","amount":9}}
"Refund me right now" -> {{"intent":"issue_refund","amount":null}}
"How long is the refund window?" -> {{"intent":"none","amount":null}}
"Why was I charged $29 this month?" -> {{"intent":"none","amount":null}}
"Please cancel my subscription" -> {{"intent":"cancel_account","amount":null}}
"I'd like to close my account" -> {{"intent":"cancel_account","amount":null}}

Customer message:
\"\"\"{question}\"\"\"
Return ONLY JSON: {{"intent":"issue_refund|cancel_account|none","amount":<number or null>}}
"""


def _extract_billing_intent(question: str):
    """Return (intent, amount) for a billing message. Deterministic, focused."""
    try:
        raw = _intent_llm.invoke(_INTENT_PROMPT.format(question=question)).content
        data = json.loads(raw)
        intent = str(data.get("intent", "none")).strip()
        if intent not in {"issue_refund", "cancel_account", "none"}:
            intent = "none"
        amount = data.get("amount")
        try:
            amount = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount = None
        return intent, amount
    except Exception:
        return "none", None

# Guidance tailored to each specialist agent.
_ROLE_GUIDANCE = {
    "billing": (
        "You handle billing, payments, refunds, invoices, pricing and paid-plan "
        "cancellations. If the customer clearly asks for a refund, set action to "
        "\"issue_refund\" and put the dollar amount in \"amount\" (use the amount "
        "they state, otherwise leave it null to refund their latest order). If the "
        "customer clearly asks to cancel their subscription, set action to "
        "\"cancel_account\"."
    ),
    "technical": (
        "You handle login problems, setup, file syncing and error codes. Give clear "
        "step-by-step troubleshooting from the context. If the issue cannot be "
        "resolved from the context, set action to \"create_ticket\"."
    ),
    "general": (
        "You answer general questions about the product and company using the "
        "context. Do not invent facts that are not in the context."
    ),
    "complaints": (
        "The customer is upset or wants a human. Respond with empathy, acknowledge "
        "the problem, and set action to \"create_ticket\" so a human follows up. "
        "Do not promise anything not supported by the context."
    ),
}

_SYSTEM_TEMPLATE = """You are a {company} customer-support specialist.
{role_guidance}

Use ONLY the information in the context and customer record below. If the answer
is not contained there, set "can_answer" to false and politely say you cannot
answer reliably and will escalate to a human. Never invent prices, policies, or
account details.

=== KNOWLEDGE BASE CONTEXT ===
{context}

=== CUSTOMER RECORD ===
{customer}

=== RECENT HISTORY WITH THIS CUSTOMER ===
{history}

=== CUSTOMER MESSAGE ===
{question}

Reply with ONLY a JSON object of this exact shape:
{{
  "response": "<your reply to the customer>",
  "can_answer": true,
  "action": "none",
  "amount": null,
  "reason": "<short internal note>"
}}
"action" must be one of: "none", "issue_refund", "cancel_account", "create_ticket".
"""


def _format_customer(customer: Dict[str, Any] | None) -> str:
    if not customer:
        return "No customer is identified (guest). Account actions are not possible."
    sub = memory.get_subscription(customer["customer_id"])
    order = memory.get_latest_order(customer["customer_id"])
    lines = [
        f"Name: {customer['name']}",
        f"Customer ID: {customer['customer_id']}",
        f"Email: {customer['email']}",
    ]
    if sub:
        lines.append(f"Plan: {sub['plan']} (${sub['monthly_price']:.0f}/mo), status: {sub['status']}")
    if order:
        lines.append(f"Latest order: {order['order_id']} ${order['amount']:.2f} "
                     f"({order['description']}), status: {order['status']}")
    return "\n".join(lines)


def _format_history(history) -> str:
    if not history:
        return "No earlier interactions on record."
    out = []
    for m in history[-6:]:
        who = "Customer" if m["role"] == "customer" else "Assistant"
        out.append(f"{who}: {m['content'][:200]}")
    return "\n".join(out)


def _safe_json(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except Exception:
        # Last-resort: wrap the raw text as a plain answer.
        return {"response": raw.strip() or "Sorry, I had trouble answering.",
                "can_answer": False, "action": "none", "amount": None,
                "reason": "model did not return valid JSON"}


def agent_node(state: dict) -> dict:
    """Run the specialist agent chosen by the supervisor and decide on approval."""
    category = state.get("category", "general")
    guidance = _ROLE_GUIDANCE.get(category, _ROLE_GUIDANCE["general"])
    context = "\n\n---\n\n".join(state.get("retrieved", [])) or "(no context retrieved)"

    prompt = _SYSTEM_TEMPLATE.format(
        company=COMPANY_NAME,
        role_guidance=guidance,
        context=context,
        customer=_format_customer(state.get("customer")),
        history=_format_history(state.get("history", [])),
        question=state["question"],
    )

    data = _safe_json(_llm.invoke(prompt).content)

    response = str(data.get("response", "")).strip() or "Sorry, I couldn't generate a reply."
    can_answer = bool(data.get("can_answer", True))
    action = str(data.get("action", "none")).strip()
    if action not in {"none", "issue_refund", "cancel_account", "create_ticket"}:
        action = "none"
    amount = data.get("amount")

    customer = state.get("customer")

    # For billing messages, override the action with the focused intent
    # classifier — this reliably catches refund/cancel requests the main model
    # may phrase away in its prose.
    if category == "billing":
        intent, intent_amount = _extract_billing_intent(state["question"])
        if intent in {"issue_refund", "cancel_account"}:
            action = intent
            if intent_amount is not None:
                amount = intent_amount

    # Resolve refund amount from the latest order if the model left it null.
    if action == "issue_refund" and customer:
        if amount is None:
            order = memory.get_latest_order(customer["customer_id"])
            amount = order["amount"] if order else None
        try:
            amount = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount = None

    # Low-confidence safeguard for informational answers: if RAG found nothing
    # that closely matches, don't trust the model's self-report — treat it as a
    # knowledge gap and escalate, rather than risk a made-up answer.
    if action == "none":
        scores = state.get("retrieval_scores", [])
        best = min(scores) if scores else None
        if best is None or best > LOW_CONFIDENCE_DISTANCE:
            can_answer = False
    if not can_answer and action == "none":
        action = "create_ticket"

    # Account actions are impossible for an unidentified guest -> escalate.
    if action in {"issue_refund", "cancel_account"} and not customer:
        action = "create_ticket"
        can_answer = False
        response = ("I can't make account changes without verifying your identity. "
                    "I'll escalate this to a human agent who can confirm your "
                    "account and help.")

    # For a concrete account action, use a clean templated reply so the
    # customer-facing text is always accurate, regardless of the model's prose.
    if action == "issue_refund" and customer and amount is not None:
        response = (f"I've requested a refund of ${amount:.2f} to your original "
                    "payment method. It typically arrives within 5 to 10 business days.")
        can_answer = True
    elif action == "cancel_account" and customer:
        response = ("I've submitted your cancellation request. Your access will "
                    "continue until the end of your current paid period, and no "
                    "further charges will be made.")
        can_answer = True

    # ---- Decide whether human approval is required (rules in code) ----
    requires_approval = False
    approval_reason = ""

    if action == "issue_refund" and amount is not None and amount > REFUND_APPROVAL_THRESHOLD:
        requires_approval = True
        approval_reason = f"Refund of ${amount:.2f} exceeds the ${REFUND_APPROVAL_THRESHOLD:.0f} limit."
    elif action == "cancel_account":
        requires_approval = True
        approval_reason = "Account cancellation always needs human approval."
    elif category == "complaints":
        requires_approval = True
        approval_reason = "Complaint / angry customer — review before replying."
    elif not can_answer:
        requires_approval = True
        approval_reason = "Low confidence — the knowledge base did not clearly answer this."

    return {
        "draft_response": response,
        "can_answer": can_answer,
        "action": action,
        "amount": amount,
        "action_reason": str(data.get("reason", "")),
        "requires_approval": requires_approval,
        "approval_reason": approval_reason,
    }
