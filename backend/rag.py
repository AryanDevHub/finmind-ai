"""
rag.py — Retrieval-Augmented Generation for FinMind AI
Stores every transaction as a vector embedding in ChromaDB.
At chat time, retrieves the most semantically relevant past
transactions and injects them into the LLM prompt context.

Install:
    pip install chromadb sentence-transformers
"""

import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "database", "chroma")
os.makedirs(CHROMA_DIR, exist_ok=True)

# ── ChromaDB persistent client ───────────────────────────────────
_chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection    = _chroma_client.get_or_create_collection(
    name="transactions",
    metadata={"hnsw:space": "cosine"}
)

# ── Embedding model (runs locally, no API key needed) ────────────
# Downloads ~90 MB on first run, cached after that
_embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ── Public API ───────────────────────────────────────────────────

def index_transaction(tx_id: int, tx: dict) -> str:
    """
    Convert a transaction dict into a natural-language sentence,
    embed it, and upsert into ChromaDB.
    Returns the doc_id stored (for saving back to the DB row).
    """
    doc_id = f"tx_{tx_id}"
    text   = _tx_to_text(tx)

    embedding = _embedder.encode(text).tolist()

    _collection.upsert(
        ids        = [doc_id],
        embeddings = [embedding],
        documents  = [text],
        metadatas  = [{
            "tx_id":            tx_id,
            "user_id":          tx.get("user_id", 0),
            "amount":           tx.get("amount", 0),
            "category":         tx.get("category", ""),
            "transaction_type": tx.get("transaction_type", ""),
            "is_flagged":       str(tx.get("is_flagged", False)),
            "date":             str(tx.get("date", "")),
        }]
    )
    return doc_id


def retrieve_relevant(user_message: str, user_id: int, n_results: int = 6) -> list[dict]:
    """
    Embed the user's chat message and retrieve the n most similar
    transactions for that user from ChromaDB.
    Returns a list of metadata dicts + the original document text.
    """
    query_embedding = _embedder.encode(user_message).tolist()

    try:
        results = _collection.query(
            query_embeddings = [query_embedding],
            n_results        = n_results,
            where            = {"user_id": user_id},
            include          = ["documents", "metadatas", "distances"]
        )
    except Exception:
        return []

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        hits.append({
            "text":       doc,
            "metadata":   meta,
            "similarity": round(1 - dist, 3),   # cosine distance → similarity
        })
    return hits


def index_all_transactions(transactions: list[dict]) -> int:
    """
    Bulk-index a list of transaction dicts (e.g. on startup).
    Returns the number indexed.
    """
    count = 0
    for tx in transactions:
        if tx.get("transaction_type") == "expense":   # only index expenses for fraud/spend context
            index_transaction(tx["id"], tx)
            count += 1
    return count


def build_rag_context(user_message: str, user_id: int) -> str:
    """
    Retrieve relevant transactions and format them as a compact
    context block to inject into the LLM system prompt.
    """
    hits = retrieve_relevant(user_message, user_id, n_results=5)
    if not hits:
        return ""

    lines = ["RELEVANT PAST TRANSACTIONS (retrieved by semantic similarity):"]
    for h in hits:
        sim_pct = int(h["similarity"] * 100)
        lines.append(f"  • {h['text']}  [match: {sim_pct}%]")

    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────

def _tx_to_text(tx: dict) -> str:
    """Turn a transaction dict into a natural-language sentence for embedding."""
    sign    = "received" if tx.get("transaction_type") == "income" else "spent"
    flagged = " [FLAGGED as suspicious]" if tx.get("is_flagged") else ""
    date    = str(tx.get("date", ""))[:10]
    return (
        f"On {date}, {sign} ₹{tx.get('amount', 0):,.0f} "
        f"on {tx.get('description', 'unknown')} "
        f"in category {tx.get('category', 'Other')}.{flagged}"
    )