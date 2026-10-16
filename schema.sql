-- CustomerSupportAI database schema (SQLite)
-- This mirrors exactly what memory.py creates at runtime. It is provided as
-- documentation of the persistent-memory design.

-- Customers of CloudNest. Identified by customer_id or email.
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    created_at  TEXT NOT NULL
);

-- One subscription per customer.
CREATE TABLE IF NOT EXISTS subscriptions (
    customer_id   TEXT PRIMARY KEY,
    plan          TEXT NOT NULL,            -- Basic / Pro / Enterprise
    status        TEXT NOT NULL,            -- active / cancelled / paused
    monthly_price REAL NOT NULL,
    started_at    TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- Payments / charges. Refunds flip status from 'paid' to 'refunded'.
CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount      REAL NOT NULL,
    description TEXT,
    status      TEXT NOT NULL,              -- paid / refunded
    created_at  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- One row per chat session.
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    customer_id     TEXT,
    started_at      TEXT NOT NULL
);

-- Every message, customer or assistant, with the agent that produced it.
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    customer_id     TEXT,
    role            TEXT NOT NULL,          -- customer / assistant
    agent           TEXT,                   -- billing / technical / general / complaints
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- A short recap per conversation (persistent memory summary).
CREATE TABLE IF NOT EXISTS summaries (
    conversation_id TEXT PRIMARY KEY,
    customer_id     TEXT,
    summary         TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Support / escalation tickets.
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   TEXT PRIMARY KEY,
    customer_id TEXT,
    category    TEXT,                       -- billing / technical / general / complaints
    reason      TEXT,
    status      TEXT NOT NULL,              -- open / escalated / resolved
    created_at  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);
