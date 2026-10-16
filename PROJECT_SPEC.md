# CustomerSupportAI — Project Specification

This file records every decision we made before building, so the project is
easy to understand and nothing was left to guesswork. It is the single source
of truth for what the system does and why.

---

## 1. What this project is

CustomerSupportAI is a customer-support assistant for a fictional software
company called **CloudNest**. It answers customer questions, looks things up in
company documents, remembers past conversations, performs real actions on sample
data (like issuing refunds), and pauses for human approval before doing anything
sensitive.

It runs fully **locally** — the language model runs on your own Mac through
Ollama, so there are no API keys and no cloud costs.

---

## 2. Technology

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Required version; stable with ChromaDB |
| Workflow engine | LangGraph | Builds the multi-step agent workflow |
| LLM glue | LangChain | Connects the model, prompts, and tools |
| Local model runtime | Ollama | Runs the model locally, no API keys |
| Chat model | `llama3.1:8b` | Fits in 16 GB RAM, good enough for support replies |
| Embedding model | `nomic-embed-text` | Turns documents into vectors for search |
| Vector database | ChromaDB | Stores document vectors for RAG |
| Memory database | SQLite | Stores customers, conversations, tickets |
| Interface | Command-line chat | No extra UI dependencies |

---

## 3. The four specialist agents

Every customer message is routed to exactly one agent by a **supervisor**.

1. **Billing Agent** — payments, refunds, invoices, plan pricing questions.
2. **Technical Agent** — login problems, setup, sync issues, error codes.
3. **General / FAQ Agent** — general product and company questions.
4. **Complaints / Escalation Agent** — complaints and anything needing a human.

The supervisor is a routing step, not a required architecture; it exists only to
pick the right agent. The reasoning happens inside each agent.

---

## 4. CloudNest — the fictional company

A SaaS company selling a file-sync and collaboration app. Three plans:

| Plan | Price (per month) | Who it's for |
|---|---|---|
| Basic | $9 | Individuals |
| Pro | $29 | Small teams |
| Enterprise | $99 | Large organisations |

### Confirmed policies
- **Refund window:** 30 days from purchase.
- **Support response time:** within 24 hours.

### Policies we defined for consistency (so the model never invents them)
- **Cancellation:** any time; access continues until the end of the paid period.
- **Support hours:** email/chat 24/7 (AI first), human agents Mon–Fri 9am–6pm.
- **Refund eligibility:** full refund within 30 days; after 30 days, no refund
  except documented service outages.
- **Plan changes:** upgrade takes effect immediately (prorated); downgrade takes
  effect at the next billing cycle.

---

## 5. Knowledge base (4 documents, written by us)

Stored in `knowledge_base/`. These are what RAG searches.

1. `company_policy.txt` — refunds, cancellations, support hours, privacy.
2. `pricing_guide.txt` — the three plans, features, billing rules.
3. `technical_manual.txt` — login, setup, sync, error codes.
4. `faq.txt` — common short questions and answers.

---

## 6. Tools (actions on fake data)

Agents don't just talk — they perform real operations against a sample SQLite
database of **~15 customers** and their orders/subscriptions.

| Tool | What it does | Needs approval? |
|---|---|---|
| `lookup_customer` | Find a customer by ID or email | No |
| `get_subscription` | Show a customer's current plan and status | No |
| `issue_refund` | Record a refund on an order | **If amount > $100** |
| `cancel_account` | Cancel a customer's subscription | **Always** |
| `create_ticket` | Open a support/escalation ticket | No |

---

## 7. Human-in-the-loop approval

The workflow **pauses** and asks a human before these actions. The human can
**Approve**, **Reject**, or **Edit** the proposed response/action.

Approval is required for:
- Refunds **over $100**.
- **Account cancellations** (any amount).
- **Angry complaints** (detected by the Complaints agent).
- **Low-confidence answers** (RAG found nothing relevant).

### On rejection
1. The sensitive action (refund/cancellation) is **not executed**.
2. An **escalation ticket** is created.
3. The customer is told a human will follow up.

---

## 8. Memory

A customer is identified by **Customer ID or email**. The system stores:
- **Full conversations** (every message, with its agent and timestamp).
- **Conversation summaries** (a short recap per session).
- **Ticket status** (open / escalated / resolved).

Schema is designed by us and documented in `schema.sql`. Tables:
`customers`, `subscriptions`, `orders`, `conversations`, `messages`,
`summaries`, `tickets`.

---

## 9. When the system can't answer

If routing is unclear or RAG returns nothing relevant, the agent must:
- Say politely that it can't answer reliably.
- **Not invent** information.
- Offer escalation to a human (and this counts as a low-confidence case, so it
  goes through approval).

---

## 10. Evaluation

A script (`evaluate.py`) runs **10–15 test questions** and checks *behaviour*,
not exact wording (LLM output varies). It covers:
- Correct agent routing.
- RAG-grounded answers.
- Missing-information handling.
- Memory recall across turns.
- Approval being triggered for sensitive actions.
- Rejection → escalation.

---

## 11. Deliverables

- Python source code (all modules).
- `README.md` — setup + run instructions for **Windows and macOS**.
- `schema.sql` — database schema.
- `memory.db` — created automatically when the app runs.
- `workflow.png` — the LangGraph workflow diagram.
- `evaluate.py` — the evaluation script.

(No screenshots and no professor submission — the goal is a clean, working,
end-to-end system.)

---

## 12. Open items (not specified, using sensible defaults)

- Deadline: not set.
- Git remote / pushing: none configured; we commit locally only when asked.
- Report or demo video: not required.
