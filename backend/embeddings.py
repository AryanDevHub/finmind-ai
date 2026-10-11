"""embeddings.py — shared embedding helpers (used by the Celery worker now, by rag.py next turn)."""
from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from backend.settings import get_settings


@lru_cache(maxsize=1)
def _model() -> Any:
    from sentence_transformers import SentenceTransformer  # heavy import: keep it lazy

    return SentenceTransformer(get_settings().embedding_model)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """L2-normalised 384-d vectors (cosine distance == dot-product ordering)."""
    return _model().encode(list(texts), normalize_embeddings=True, batch_size=64).tolist()


def transaction_text(description: str, merchant: str | None, category: str) -> str:
    """Semantic text only. Amounts and dates are NOT embedded: exact filters belong to SQL."""
    parts = [description]
    if merchant:
        parts.append(f"merchant: {merchant}")
    parts.append(f"category: {category}")
    return " | ".join(parts)
