"""
rag.py — semantic retrieval over transactions, in the SAME Postgres (pgvector).

Replaces the embedded ChromaDB client (SQLite file locks that corrupt under
multiple Uvicorn workers). Embeddings are written by the Celery worker onto the
`transactions.embedding` column and indexed with HNSW (cosine).

This module answers FUZZY questions only ("gym or fitness clubs", "things like
Netflix"). The embedded text contains description / merchant / category and never
amounts or dates, so dense similarity is never asked to do arithmetic: every
number in a hit comes from the ledger columns, and totals are computed in SQL.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from backend import embeddings
from backend.database import Transaction

EmbedFn = Callable[[Sequence[str]], list[list[float]]]
DEFAULT_MIN_SIMILARITY = 0.25  # MiniLM cosine: below this a hit is noise


@dataclass(frozen=True, slots=True)
class SemanticHit:
    id: uuid.UUID
    description: str
    merchant: str | None
    category: str
    amount: float
    transaction_type: str
    occurred_at: datetime
    similarity: float


async def _tune_ann(session: AsyncSession) -> None:
    """Best effort: widen the HNSW candidate pool so the per-user filter still yields k rows."""
    await session.execute(text("SET LOCAL hnsw.ef_search = 100"))
    try:  # pgvector >= 0.8 only; an unknown GUC must not poison the transaction, hence the savepoint
        async with session.begin_nested():
            await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    except DBAPIError:
        pass


async def semantic_search(
    session: AsyncSession, user_id: uuid.UUID, query: str, *, k: int = 6,
    min_similarity: float = DEFAULT_MIN_SIMILARITY, embed: EmbedFn | None = None,
) -> list[SemanticHit]:
    """Top-k transactions of THIS user by cosine similarity to `query`."""
    embed = embed or embeddings.embed_texts
    vector = (await asyncio.to_thread(embed, [query]))[0]  # CPU-bound: keep it off the event loop
    await _tune_ann(session)
    dist = Transaction.embedding.cosine_distance(vector).label("dist")
    rows = (
        await session.execute(
            select(
                Transaction.id, Transaction.description, Transaction.merchant, Transaction.category,
                Transaction.amount, Transaction.transaction_type, Transaction.occurred_at, dist,
            )
            .where(Transaction.user_id == user_id, Transaction.embedding.is_not(None))
            .order_by(dist)
            .limit(k)
        )
    ).all()
    hits = [
        SemanticHit(r.id, r.description, r.merchant, r.category, float(r.amount), r.transaction_type,
                    r.occurred_at, round(1.0 - float(r.dist), 3))
        for r in rows
    ]
    return [h for h in hits if h.similarity >= min_similarity]
