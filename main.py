"""CustomerSupportAI — command-line chat interface.

Run:
    python main.py

On start it identifies you (optional), then you chat with the assistant. When
the assistant plans something sensitive, the run pauses and asks you (acting as
the human support manager) to approve, reject, or edit before it proceeds.
"""
import sys

from langgraph.types import Command

import memory
import rag
from graph import build_graph
from human_loop import prompt_for_approval


def _print_reply(state: dict) -> None:
    print("\nAssistant:")
    for line in state.get("final_response", "(no response)").splitlines():
        print(f"  {line}")
    if state.get("escalated"):
        print(f"  [escalated — ticket {state.get('ticket_id')}]")
    print()


def run_once(graph, question: str, customer_id, conversation_id) -> dict:
    """Send one question through the graph, handling any approval interrupt."""
    config = {"configurable": {"thread_id": conversation_id}}
    inputs = {
        "question": question,
        "customer_id": customer_id,
        "conversation_id": conversation_id,
    }
    result = graph.invoke(inputs, config=config)

    # If the graph interrupted for human approval, collect the decision and resume.
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        decision = prompt_for_approval(payload)
        result = graph.invoke(Command(resume=decision), config=config)

    return result


def main() -> None:
    print("Setting up CustomerSupportAI (CloudNest)...")
    memory.init_db()
    memory.seed_sample_data()
    rag.build_vectorstore()  # embeds the knowledge base on first run, reused after
    graph = build_graph()

    print("\nWelcome to CloudNest Support.")
    print("Identify yourself with a customer ID or email for account help,")
    print("or press Enter to continue as a guest.")
    identifier = input("Customer ID or email: ").strip()

    customer = memory.get_customer(identifier) if identifier else None
    customer_id = customer["customer_id"] if customer else None
    if customer:
        print(f"Hello, {customer['name']} ({customer_id}).")
    elif identifier:
        print("No account found for that identifier — continuing as a guest.")
    else:
        print("Continuing as a guest.")

    conversation_id = memory.start_conversation(customer_id)

    print("\nType your question. Type 'quit' or 'exit' to leave.\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not question:
            continue
        if question.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break

        result = run_once(graph, question, customer_id, conversation_id)
        _print_reply(result)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"\nFatal error: {exc}", file=sys.stderr)
        raise
