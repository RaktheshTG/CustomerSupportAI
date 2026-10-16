"""Persistent memory and the fake-data layer, both backed by SQLite.

This module owns every database read and write:
  * customers, subscriptions, orders  -> the "fake sample data" the tools act on
  * conversations, messages, summaries -> persistent conversation memory
  * tickets                            -> support / escalation records

The agent tools (issue_refund, cancel_account, create_ticket, lookup_customer,
get_subscription) are the functions near the bottom of this file.
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from config import DB_PATH


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------
# Schema + seed data
# --------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables if they do not exist. Safe to call on every startup."""
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            customer_id   TEXT PRIMARY KEY,
            plan          TEXT NOT NULL,
            status        TEXT NOT NULL,
            monthly_price REAL NOT NULL,
            started_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id    TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount      REAL NOT NULL,
            description TEXT,
            status      TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            customer_id     TEXT,
            started_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            customer_id     TEXT,
            role            TEXT NOT NULL,
            agent           TEXT,
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS summaries (
            conversation_id TEXT PRIMARY KEY,
            customer_id     TEXT,
            summary         TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id   TEXT PRIMARY KEY,
            customer_id TEXT,
            category    TEXT,
            reason      TEXT,
            status      TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


# Fifteen sample customers with plans and one recent order each.
_SEED_CUSTOMERS = [
    # customer_id, name,           email,                      plan,         status,     price, order_amount, order_desc
    ("CUST001", "Alice Johnson",  "alice@example.com",        "Pro",        "active",    29.0,  29.0,  "Pro monthly renewal"),
    ("CUST002", "Bob Smith",      "bob@example.com",          "Basic",      "active",     9.0,   9.0,  "Basic monthly renewal"),
    ("CUST003", "Carol White",    "carol@example.com",        "Enterprise", "active",    99.0,  99.0,  "Enterprise monthly renewal"),
    ("CUST004", "David Brown",    "david@example.com",        "Pro",        "active",    29.0, 290.0,  "Pro annual plan"),
    ("CUST005", "Emma Davis",     "emma@example.com",         "Basic",      "cancelled",  9.0,   9.0,  "Basic monthly (final)"),
    ("CUST006", "Frank Miller",   "frank@example.com",        "Enterprise", "active",    99.0, 990.0,  "Enterprise annual plan"),
    ("CUST007", "Grace Lee",      "grace@example.com",        "Pro",        "active",    29.0,  29.0,  "Pro monthly renewal"),
    ("CUST008", "Henry Wilson",   "henry@example.com",        "Basic",      "paused",     9.0,   9.0,  "Basic monthly renewal"),
    ("CUST009", "Ivy Chen",       "ivy@example.com",          "Pro",        "active",    29.0,  58.0,  "Pro upgrade proration"),
    ("CUST010", "Jack Taylor",    "jack@example.com",         "Enterprise", "active",    99.0,  99.0,  "Enterprise monthly renewal"),
    ("CUST011", "Karen Moore",    "karen@example.com",        "Basic",      "active",     9.0,   9.0,  "Basic monthly renewal"),
    ("CUST012", "Leo Martin",     "leo@example.com",          "Pro",        "active",    29.0,  29.0,  "Pro monthly renewal"),
    ("CUST013", "Mia Anderson",   "mia@example.com",          "Enterprise", "active",    99.0, 150.0,  "Enterprise add-on seats"),
    ("CUST014", "Noah Thomas",    "noah@example.com",         "Basic",      "active",     9.0,   9.0,  "Basic monthly renewal"),
    ("CUST015", "Olivia Harris",  "olivia@example.com",       "Pro",        "active",    29.0,  29.0,  "Pro monthly renewal"),
]


def seed_sample_data() -> None:
    """Insert the sample customers/subscriptions/orders if the table is empty."""
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if count > 0:
        conn.close()
        return

    now = _now()
    for cid, name, email, plan, status, price, amount, desc in _SEED_CUSTOMERS:
        conn.execute(
            "INSERT INTO customers (customer_id, name, email, created_at) VALUES (?,?,?,?)",
            (cid, name, email, now),
        )
        conn.execute(
            "INSERT INTO subscriptions (customer_id, plan, status, monthly_price, started_at) VALUES (?,?,?,?,?)",
            (cid, plan, status, price, now),
        )
        conn.execute(
            "INSERT INTO orders (order_id, customer_id, amount, description, status, created_at) VALUES (?,?,?,?,?,?)",
            (_new_id("ORD"), cid, amount, desc, "paid", now),
        )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Read helpers (no approval needed)
# --------------------------------------------------------------------------
def get_customer(identifier: str) -> Optional[Dict[str, Any]]:
    """Look up a customer by customer_id OR email (case-insensitive)."""
    if not identifier:
        return None
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM customers WHERE customer_id = ? OR LOWER(email) = LOWER(?)",
        (identifier.strip(), identifier.strip()),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_subscription(customer_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_order(customer_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Conversation memory
# --------------------------------------------------------------------------
def start_conversation(customer_id: Optional[str]) -> str:
    conv_id = _new_id("CONV")
    conn = _connect()
    conn.execute(
        "INSERT INTO conversations (conversation_id, customer_id, started_at) VALUES (?,?,?)",
        (conv_id, customer_id, _now()),
    )
    conn.commit()
    conn.close()
    return conv_id


def save_message(conversation_id: str, customer_id: Optional[str], role: str,
                 content: str, agent: Optional[str] = None) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (conversation_id, customer_id, role, agent, content, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (conversation_id, customer_id, role, agent, content, _now()),
    )
    conn.commit()
    conn.close()


def get_history(customer_id: Optional[str], limit: int = 10,
                exclude_conversation: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return a customer's recent messages across ALL past conversations.

    This is what gives the assistant memory of earlier interactions. The current
    conversation can be excluded so only genuinely prior context is recalled.
    """
    if not customer_id:
        return []
    conn = _connect()
    if exclude_conversation:
        rows = conn.execute(
            "SELECT role, agent, content, created_at FROM messages "
            "WHERE customer_id = ? AND conversation_id != ? "
            "ORDER BY id DESC LIMIT ?",
            (customer_id, exclude_conversation, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT role, agent, content, created_at FROM messages "
            "WHERE customer_id = ? ORDER BY id DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]  # oldest first


def save_summary(conversation_id: str, customer_id: Optional[str], summary: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO summaries (conversation_id, customer_id, summary, updated_at) "
        "VALUES (?,?,?,?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET summary=excluded.summary, "
        "updated_at=excluded.updated_at",
        (conversation_id, customer_id, summary, _now()),
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# TOOLS — actions the agents can perform on the sample data
# --------------------------------------------------------------------------
def lookup_customer(identifier: str) -> Optional[Dict[str, Any]]:
    """Tool: find a customer by id or email."""
    return get_customer(identifier)


def issue_refund(customer_id: str, amount: float, reason: str = "") -> Dict[str, Any]:
    """Tool: record a refund against the customer's latest paid order.

    Returns a result dict. This is only ever called AFTER approval logic has run.
    """
    order = get_latest_order(customer_id)
    if not order:
        return {"ok": False, "message": "No order found to refund."}
    conn = _connect()
    conn.execute(
        "UPDATE orders SET status = 'refunded' WHERE order_id = ?", (order["order_id"],)
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "message": f"Refund of ${amount:.2f} processed for order {order['order_id']}.",
        "order_id": order["order_id"],
        "amount": amount,
    }


def cancel_account(customer_id: str, reason: str = "") -> Dict[str, Any]:
    """Tool: cancel a customer's subscription. Only called AFTER approval."""
    sub = get_subscription(customer_id)
    if not sub:
        return {"ok": False, "message": "No subscription found to cancel."}
    conn = _connect()
    conn.execute(
        "UPDATE subscriptions SET status = 'cancelled' WHERE customer_id = ?",
        (customer_id,),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Subscription cancelled. Access continues until "
                                   "the end of the current paid period."}


def create_ticket(customer_id: Optional[str], category: str, reason: str,
                  status: str = "open") -> str:
    """Tool: open a support/escalation ticket. Returns the ticket id."""
    ticket_id = _new_id("TKT")
    conn = _connect()
    conn.execute(
        "INSERT INTO tickets (ticket_id, customer_id, category, reason, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (ticket_id, customer_id, category, reason, status, _now()),
    )
    conn.commit()
    conn.close()
    return ticket_id


def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
