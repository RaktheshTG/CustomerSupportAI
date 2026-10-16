"""Central configuration for CustomerSupportAI.

Every tunable value lives here so the rest of the code never hard-codes paths,
model names, or business rules.
"""
from pathlib import Path

# ---- Paths ----
BASE_DIR = Path(__file__).parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
DB_PATH = BASE_DIR / "memory.db"

# ---- Ollama / models ----
OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"

# ---- RAG ----
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
RETRIEVAL_K = 4
COLLECTION_NAME = "cloudnest_kb"

# ---- Business rules (human-in-the-loop) ----
# Refunds strictly greater than this dollar amount need human approval.
REFUND_APPROVAL_THRESHOLD = 100.0

# Low-confidence detection for informational answers. ChromaDB returns a cosine
# distance where LOWER = more similar. In testing, on-topic questions scored
# <= ~0.9 and off-topic questions >= ~1.3, so a best match worse than this is
# treated as "the knowledge base does not cover it" -> escalate to a human.
# This is an engineering safeguard: we do NOT trust the model's own
# self-reported confidence alone, because small local models over-claim.
LOW_CONFIDENCE_DISTANCE = 1.1

# The four specialist agents the supervisor can route to.
AGENTS = ["billing", "technical", "general", "complaints"]

# Company facts (used in prompts so the model stays consistent).
COMPANY_NAME = "CloudNest"
