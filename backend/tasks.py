"""
tasks.py — background work. Every task is IDEMPOTENT (safe under at-least-once delivery).

  finmind.embed_transaction      event: embed one tx -> pgvector
  finmind.refresh_budget_spent   event: recompute one budget's spent_amount from the ledger
  finmind.embed_pending          beat:  reconcile rows still missing an embedding
  finmind.reconcile_budgets      beat:  recompute all current-month budgets
  finmind.nightly_anomalies      beat:  fan out per-user anomaly scoring
  finmind.score_user_anomalies   per user: IsolationForest / MAD (see analytics.py)
  finmind.nightly_forecasts      beat:  fan out per-user forecasts
  finmind.forecast_user          per user: AutoARIMA -> Redis cache
  finmind.purge_refresh_tokens   beat:  delete long-expired refresh tokens
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from decimal import Decimal

import pandas as pd
import redis as redis_sync
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend import analytics, embeddings
from backend.celery_app import celery_app
from backend.database import BankConnection, Budget, RefreshToken, Transaction, create_task_engine, spent_subquery
from backend.settings import get_settings
from backend.timeutil import month_bounds, month_key
from ml_models.scorer import FraudScorer

log = logging.getLogger(__name__)
_RETRY = {"autoretry_for": (Exception,), "retry_backoff": True, "retry_backoff_max": 300, "max_retries": 5}


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncSession]:
    """One NullPool engine per task run: each asyncio.run() has its own loop, so pools can't be shared."""
    engine = create_task_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            try:
                yield s
                await s.commit()
            except BaseException:
                await s.rollback()
                raise
    finally:
        await engine.dispose()


# ───────────────────────────── Embeddings ────────────────────────────────
async def _embed_ids(ids: list[uuid.UUID] | None, limit: int = 200) -> int:
    async with _session() as s:
        q = select(Transaction).where(Transaction.embedding.is_(None))
        if ids is not None:
            q = q.where(Transaction.id.in_(ids))
        else:  # reconciliation: skip rows younger than 10 s, their own event is still in flight
            q = q.where(Transaction.created_at < func.now() - text("interval '10 seconds'"))
        rows = (await s.execute(q.order_by(Transaction.created_at).limit(limit))).scalars().all()
        if not rows:
            return 0
        vecs = embeddings.embed_texts([embeddings.transaction_text(r.description, r.merchant, r.category) for r in rows])
        now = datetime.now(timezone.utc)
        await s.execute(update(Transaction), [{"id": r.id, "embedding": v, "embedded_at": now} for r, v in zip(rows, vecs)])
        return len(rows)


@celery_app.task(name="finmind.embed_transaction", **_RETRY)
def embed_transaction(tx_id: str) -> int:
    return asyncio.run(_embed_ids([uuid.UUID(tx_id)]))


@celery_app.task(name="finmind.embed_pending", **_RETRY)
def embed_pending() -> int:
    n = asyncio.run(_embed_ids(None))
    if n:
        log.info("embedded %d pending transactions", n)
    return n


# ───────────────────────────── Budgets ───────────────────────────────────
async def _refresh_budget(user_id: uuid.UUID, category: str, month: str) -> None:
    start, end = month_bounds(month)
    async with _session() as s:
        await s.execute(
            update(Budget)
            .where(Budget.user_id == user_id, Budget.category == category, Budget.month == month)
            .values(spent_amount=spent_subquery(start, end))
        )


@celery_app.task(name="finmind.refresh_budget_spent", **_RETRY)
def refresh_budget_spent(user_id: str, category: str, month: str) -> None:
    asyncio.run(_refresh_budget(uuid.UUID(user_id), category, month))


async def _reconcile_budgets() -> None:
    month = month_key(datetime.now(timezone.utc))
    start, end = month_bounds(month)
    async with _session() as s:
        await s.execute(update(Budget).where(Budget.month == month).values(spent_amount=spent_subquery(start, end)))


@celery_app.task(name="finmind.reconcile_budgets", **_RETRY)
def reconcile_budgets() -> None:
    asyncio.run(_reconcile_budgets())


# ───────────────────────────── Bank Sync (AA) ────────────────────────────
async def _process_aa_data_session(session_id: str, user_id: uuid.UUID, connection_id: uuid.UUID) -> int:
    """Fetch bank statement data, sanitize, deduplicate, categorize, score, and persist."""
    from backend.aa_client import AAGatewayClient, sanitize_narration, classify_transaction_type, extract_merchant_name, compute_dedup_hash
    from backend.encryption import encrypt_if_present
    from backend.settings import get_settings
    
    settings = get_settings()
    if not settings.aa_api_key:
        log.error("AA API key not configured")
        return 0
    
    client = AAGatewayClient(
        base_url=settings.aa_base_url,
        api_key=settings.aa_api_key,
        api_secret=settings.aa_api_secret or "",
        webhook_secret=settings.aa_webhook_secret or "",
    )
    
    try:
        raw_transactions = await client.fetch_financial_data(session_id)
    finally:
        await client.close()
    
    inserted = 0
    scorer = FraudScorer(settings.model_dir)
    r = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    
    async with _session() as s:
        for raw_tx in raw_transactions:
            # Compute dedup hash
            dedup = compute_dedup_hash(
                user_id,
                raw_tx.get("txnId", ""),
                Decimal(str(raw_tx.get("amount", 0))),
                raw_tx.get("transactionTimestamp", ""),
            )
            
            # Check if already exists
            existing = await s.execute(
                select(Transaction.id).where(Transaction.bank_txn_hash == dedup)
            )
            if existing.scalar_one_or_none():
                continue
            
            # Sanitize and transform
            narration = sanitize_narration(raw_tx.get("narration", ""))
            merchant = extract_merchant_name(raw_tx.get("narration", ""))
            tx_type = classify_transaction_type(raw_tx.get("type", "DEBIT"))
            amount = Decimal(str(raw_tx.get("amount", 0)))
            
            # Simple category heuristic
            category = _categorize_narration(narration)
            
            # Parse timestamp
            occurred = datetime.fromisoformat(raw_tx.get("transactionTimestamp", datetime.now(timezone.utc).isoformat()))
            
            tx_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            
            # Fraud scoring for expenses
            score_pct, level, flagged = 0.0, "LOW", False
            if tx_type == "expense":
                # Use neutral velocity features for batch imports
                from backend.velocity import NEUTRAL
                res = scorer.score(
                    amount=float(amount), category=category,
                    hour=occurred.hour, day_of_week=occurred.weekday(),
                    **NEUTRAL.as_kwargs()
                )
                score_pct, level, flagged = res.score_pct, res.risk_level, res.is_flagged
            
            s.add(Transaction(
                id=tx_id, user_id=user_id, description=narration,
                merchant=merchant, amount=amount, category=category,
                transaction_type=tx_type, occurred_at=occurred,
                fraud_score=score_pct, risk_level=level, is_flagged=flagged,
                bank_txn_hash=dedup, source="bank_sync",
            ))
            inserted += 1
        
        # Update last_synced_at on the connection
        await s.execute(
            update(BankConnection)
            .where(BankConnection.id == connection_id)
            .values(last_synced_at=datetime.now(timezone.utc))
        )
    
    r.close()
    
    # Enqueue embedding tasks for new transactions
    if inserted > 0:
        celery_app.send_task("finmind.embed_pending")
    
    log.info("Bank sync: inserted %d transactions for user %s", inserted, user_id)
    return inserted


def _categorize_narration(narration: str) -> str:
    """Simple keyword-based categorization for bank narrations."""
    n = narration.lower()
    mapping = {
        "Food": ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "burger", "kitchen", "dhaba", "biryani", "bakery"],
        "Transport": ["uber", "ola", "rapido", "metro", "irctc", "railway", "petrol", "diesel", "fuel", "parking", "toll"],
        "Shopping": ["amazon", "flipkart", "myntra", "ajio", "mall", "mart", "store", "shop", "meesho"],
        "Entertainment": ["netflix", "hotstar", "prime", "spotify", "cinema", "movie", "game", "bookmyshow"],
        "Bills": ["electricity", "water", "gas", "internet", "broadband", "mobile", "recharge", "postpaid", "emi", "insurance", "rent"],
        "Health": ["pharmacy", "hospital", "clinic", "doctor", "medical", "medicine", "apollo", "medplus", "1mg"],
        "Education": ["school", "college", "university", "course", "udemy", "coursera", "tuition", "books"],
        "Salary": ["salary", "payroll"],
        "Investment": ["mutual fund", "zerodha", "groww", "sip", "stock", "invest", "fd", "fixed deposit", "ppf", "nps"],
    }
    for cat, keywords in mapping.items():
        if any(kw in n for kw in keywords):
            return cat
    return "Other"


@celery_app.task(name="finmind.process_aa_data_session", **_RETRY)
def process_aa_data_session(session_id: str, user_id: str, connection_id: str) -> int:
    return asyncio.run(_process_aa_data_session(session_id, uuid.UUID(user_id), uuid.UUID(connection_id)))


# ───────────────────────────── Anomalies ─────────────────────────────────
async def _score_user_anomalies(user_id: uuid.UUID) -> int:
    tz = get_settings().tz
    async with _session() as s:
        rows = (
            await s.execute(
                select(Transaction.id, Transaction.amount, Transaction.category, Transaction.occurred_at)
                .where(Transaction.user_id == user_id, Transaction.transaction_type == "expense")
            )
        ).all()
        df = pd.DataFrame(rows, columns=["id", "amount", "category", "occurred_at"])
        if df.empty:
            return 0
        df["amount"] = df["amount"].astype(float)
        df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True).dt.tz_convert(tz)
        results = analytics.score_anomalies(df)
        if results is None:
            return 0
        now = datetime.now(timezone.utc)
        await s.execute(update(Transaction), [
            {"id": r.tx_id, "anomaly_score": r.score, "is_anomaly": r.is_anomaly,
             "anomaly_method": r.method, "anomaly_scored_at": now} for r in results
        ])
        return sum(r.is_anomaly for r in results)


@celery_app.task(name="finmind.score_user_anomalies", **_RETRY)
def score_user_anomalies(user_id: str) -> int:
    return asyncio.run(_score_user_anomalies(uuid.UUID(user_id)))


async def _active_user_ids() -> list[str]:
    async with _session() as s:
        q = select(Transaction.user_id).where(Transaction.transaction_type == "expense").group_by(Transaction.user_id)
        return [str(u) for u in (await s.execute(q)).scalars().all()]


@celery_app.task(name="finmind.nightly_anomalies")
def nightly_anomalies() -> int:
    ids = asyncio.run(_active_user_ids())
    for uid in ids:
        score_user_anomalies.delay(uid)
    return len(ids)


# ───────────────────────────── Forecasts ─────────────────────────────────
async def _forecast_user(user_id: uuid.UUID) -> dict:
    tz_name = get_settings().app_timezone
    async with _session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT date_trunc('week', timezone(:tz, occurred_at))::date AS wk, SUM(amount) AS total "
                    "FROM transactions WHERE user_id = :u AND transaction_type = 'expense' GROUP BY 1 ORDER BY 1"
                ),
                {"tz": tz_name, "u": user_id},
            )
        ).all()
    now_local = datetime.now(timezone.utc).astimezone(get_settings().tz)
    this_week = (now_local - timedelta(days=now_local.weekday())).date()
    weekly = pd.Series({pd.Timestamp(r.wk): float(r.total) for r in rows if r.wk < this_week}, dtype=float)  # complete weeks only
    if weekly.empty or len(weekly) < analytics.MIN_FORECAST_WEEKS:
        return {"status": "insufficient_data", "history_weeks": int(len(weekly)),
                "min_required_weeks": analytics.MIN_FORECAST_WEEKS}
    weekly = weekly.reindex(pd.date_range(weekly.index.min(), weekly.index.max(), freq="W-MON"), fill_value=0.0)
    result = analytics.forecast_weekly(weekly)
    return {"status": "ok", **(result or {})}


@celery_app.task(name="finmind.forecast_user", **_RETRY)
def forecast_user(user_id: str) -> str:
    payload = asyncio.run(_forecast_user(uuid.UUID(user_id)))
    payload["computed_at"] = datetime.now(timezone.utc).isoformat()
    r = redis_sync.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        r.set(f"forecast:{user_id}", json.dumps(payload), ex=36 * 3600)
    finally:
        r.close()
    return payload["status"]


@celery_app.task(name="finmind.nightly_forecasts")
def nightly_forecasts() -> int:
    ids = asyncio.run(_active_user_ids())
    for uid in ids:
        forecast_user.delay(uid)
    return len(ids)


# ───────────────────────────── Housekeeping ──────────────────────────────
async def _purge_tokens() -> int:
    async with _session() as s:
        res = await s.execute(delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(timezone.utc) - timedelta(days=1)))
        return res.rowcount or 0


@celery_app.task(name="finmind.purge_refresh_tokens")
def purge_refresh_tokens() -> int:
    return asyncio.run(_purge_tokens())
