"""The supervisor: routes each customer message to one specialist agent.

This is a small, deterministic LLM step. We force JSON output so the result is
always one of the four known categories.
"""
import json

from langchain_ollama import ChatOllama

from config import CHAT_MODEL, OLLAMA_BASE_URL, AGENTS

_router_llm = ChatOllama(
    model=CHAT_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    format="json",
)

_ROUTER_PROMPT = """You are the router for {company} customer support.
Read the customer's message and choose the single best category:

- "billing": payments, refunds, invoices, pricing, plan charges, cancelling a paid plan.
- "technical": login issues, setup, file syncing, error codes, the app not working.
- "general": general questions about the product or company, features, how-to, FAQ.
- "complaints": the customer is angry or frustrated, is complaining, or explicitly
  wants to speak to a human.

Reply with ONLY a JSON object of the form: {{"category": "billing"}}

Customer message:
\"\"\"{question}\"\"\"
"""


def classify(question: str) -> str:
    """Return one of the AGENTS categories for the given message."""
    prompt = _ROUTER_PROMPT.format(company="CloudNest", question=question)
    try:
        raw = _router_llm.invoke(prompt).content
        category = json.loads(raw).get("category", "general").strip().lower()
    except Exception:
        category = "general"
    return category if category in AGENTS else "general"


def supervisor_node(state: dict) -> dict:
    """LangGraph node wrapper around classify()."""
    return {"category": classify(state["question"])}
