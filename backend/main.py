"""
main.py — FinMind AI API (v3, async).

Critical path  POST /transaction/add:
    validate -> Redis velocity (1 Lua round trip) -> ONNX score + TreeSHAP (~1.3 ms, inline)
    -> INSERT + COMMIT (asyncpg) -> respond -> [after response] publish Celery events.
Nothing slow runs on that path. Embeddings, budget roll-ups, anomaly scoring and
forecasting are Celery jobs; lost events are healed by beat reconciliation tasks.

Identity is derived from the access token only (`/transactions/me`, never `/{user_id}`).
Chat (/chat) runs the hybrid Text-to-SQL + pgvector agent in chatbot.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, AsyncIterator

# Ensure immediate line-buffered logging for cloud environments (Render)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend import analytics, auth
from backend.aa_client import AAGatewayClient, verify_webhook_signature
from backend.auth import CurrentUser, get_current_user, get_redis
from backend.celery_app import celery_app
from backend.chatbot import GroqLLM, run_agent
from backend.database import Budget, Transaction, User, BankConnection, dispose_engine, get_session, ping, spent_subquery
from backend.schemas import (
    AnomalyOut, AnomalyReport, BudgetOut, BudgetSet, Category, ChatRequest, ChatResponse, RiskFactorOut, RiskPreview,
    Token, ToolTraceOut, TransactionAddResponse, TransactionCreate, TransactionOut, UserOut, UserRegister,
)
from backend.settings import get_settings
from backend.timeutil import month_bounds, month_key
from backend.velocity import NEUTRAL, VelocityStore
from ml_models.scorer import FraudScorer

log = logging.getLogger("finmind.api")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]
MonthQuery = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


# ───────────────────────────── App / lifespan ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        settings = get_settings()
        redis = Redis.from_url(settings.redis_url, decode_responses=True, health_check_interval=30)
        app.state.redis = redis
        app.state.velocity = VelocityStore(redis)
        app.state.scorer = FraudScorer(settings.model_dir)
        app.state.tz = settings.tz
        app.state.llm = GroqLLM(settings.groq_api_key, settings.llm_model) if settings.groq_api_key else None
        if app.state.llm is None:
            log.warning("GROQ_API_KEY not set: /chat will return 503")
        scorer_ver = getattr(app.state.scorer, "model_version", "unknown")
        log.info("FinMind API startup complete (model %s)", scorer_ver)
        print(f"FinMind API startup complete (model {scorer_ver})", flush=True)
    except Exception as e:
        import traceback
        print(f"FATAL ERROR DURING APP LIFESPAN: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    try:
        yield
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass
        try:
            await dispose_engine()
        except Exception:
            pass


_settings = get_settings()
app = FastAPI(
    title="FinMind AI", version="3.0.0", lifespan=lifespan,
    docs_url=None if _settings.environment == "prod" else "/docs",
    redoc_url=None, openapi_url=None if _settings.environment == "prod" else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,       # explicit whitelist; empty => no cross-origin access
    allow_credentials=True,                          # required for the refresh cookie
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ───────────────────────────── Helpers ───────────────────────────────────
_FACTOR_LABELS = {
    "amount": "Transaction amount", "hour": "Hour of day", "day_of_week": "Day of week",
    "tx_count_5m": "Transactions in last 5 minutes", "tx_sum_24h": "Spend in last 24 hours",
    "amount_to_avg_ratio": "Amount vs your usual spend",
}


def _factor_label(feature: str, value: float = 1.0) -> str:
    """One-hot category features are 1 when the tx IS that category and 0 when it is not; the label must say which."""
    if feature.startswith("cat_"):
        return f"Category is {feature[4:]}" if value >= 0.5 else f"Category is not {feature[4:]}"
    return _FACTOR_LABELS.get(feature, feature)


def _score_expense(st: Any, amount: float, category: str, feats: Any, now: datetime) -> tuple[Any, list[RiskFactorOut]]:
    """ONNX (~10 us) + TreeSHAP (~1.2 ms): cheaper inline than a thread hop. Shared by /add and /preview."""
    local = now.astimezone(st.tz)
    res = st.scorer.score(amount=amount, category=category, hour=local.hour, day_of_week=local.weekday(), **feats.as_kwargs())
    factors = [
        RiskFactorOut(feature=f.feature, label=_factor_label(f.feature, f.value), value=f.value,
                      contribution=f.contribution, direction=f.direction)
        for f in res.factors
    ]
    return res, factors


def _send(task: str, *args: Any) -> None:
    celery_app.send_task(task, args=list(args))


def _publish_transaction_events(tx_id: uuid.UUID, user_id: uuid.UUID, category: str, month: str, is_expense: bool) -> None:
    """Runs AFTER the response (BackgroundTasks, threadpool). Failure is safe: beat reconciliation heals it."""
    try:
        _send("finmind.embed_transaction", str(tx_id))
        if is_expense:
            _send("finmind.refresh_budget_spent", str(user_id), category, month)
    except Exception:
        log.exception("could not publish events for tx %s; reconciliation will pick it up", tx_id)


async def _enqueue(task: str, *args: Any) -> None:
    await asyncio.to_thread(_send, task, *args)  # kombu publish is blocking


async def _login_blocked(redis: Redis, key: str) -> bool:
    try:
        n = await redis.get(key)
        return n is not None and int(n) >= get_settings().login_max_attempts
    except RedisError:
        return False  # limiter fails open; token auth itself fails closed


async def _record_login_failure(redis: Redis, key: str) -> None:
    try:
        async with redis.pipeline(transaction=False) as p:
            p.incr(key)
            p.expire(key, get_settings().login_window_seconds)
            await p.execute()
    except RedisError:
        pass


# ───────────────────────────── Health ────────────────────────────────────
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, bool] = {}
    try:
        checks["postgres"] = await ping()
    except Exception:
        checks["postgres"] = False
    try:
        checks["redis"] = bool(await request.app.state.redis.ping())
    except Exception:
        checks["redis"] = False
    ok = all(checks.values())
    return JSONResponse({"status": "ready" if ok else "degraded", **checks}, status_code=200 if ok else 503)


# ───────────────────────────── Auth ──────────────────────────────────────
@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, session: SessionDep) -> User:
    user = User(
        username=payload.username, email=payload.email.lower(),
        hashed_password=await auth.hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email already registered") from None
    return user


@app.post("/auth/login", response_model=Token)
async def login(
    request: Request, response: Response, form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep, redis: RedisDep,
) -> Token:
    ident = form.username.strip()
    limiter_key = f"login_fail:{request.client.host if request.client else 'unknown'}:{ident.lower()}"
    if await _login_blocked(redis, limiter_key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again later.")

    user = (
        await session.execute(select(User).where(or_(User.username == ident, User.email == ident.lower())))
    ).scalar_one_or_none()
    ok = await auth.verify_password(form.password, user.hashed_password if user else None)
    if user is None or not ok or not user.is_active:
        await _record_login_failure(redis, limiter_key)
        raise auth.credentials_error("Incorrect username or password")

    try:
        await redis.delete(limiter_key)
    except RedisError:
        pass
    access, ttl = auth.create_access_token(user.id)
    raw_refresh = await auth.issue_refresh_token(session, user.id)
    await session.commit()
    auth.set_refresh_cookie(response, raw_refresh)
    return Token(access_token=access, expires_in=ttl)


@app.post("/auth/refresh", response_model=Token)
async def refresh(
    response: Response, session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Token:
    if not refresh_token:
        raise auth.credentials_error("Missing refresh token")
    user_id, new_raw = await auth.rotate_refresh_token(session, refresh_token)
    access, ttl = auth.create_access_token(user_id)
    auth.set_refresh_cookie(response, new_raw)
    return Token(access_token=access, expires_in=ttl)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, session: SessionDep, redis: RedisDep,
    token: Annotated[str | None, Depends(auth.oauth2_optional)] = None,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    """Works even with an expired access token: the refresh family is always revoked."""
    if token:
        try:
            await auth.revoke_access_token(redis, auth.decode_access_token(token))
        except HTTPException:
            pass  # expired or malformed: nothing left to revoke
        except RedisError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Session store unavailable") from None
    await auth.revoke_refresh_by_raw(session, refresh_token)
    await session.commit()
    auth.clear_refresh_cookie(response)


@app.get("/auth/me", response_model=UserOut)
async def me(session: SessionDep, user: UserDep) -> User:
    row = await session.get(User, user.id)
    if row is None or not row.is_active:
        raise auth.credentials_error()
    return row


# ───────────────────────────── Transactions ──────────────────────────────
@app.post("/transaction/add", response_model=TransactionAddResponse)
async def add_transaction(
    tx: TransactionCreate, request: Request, background: BackgroundTasks, session: SessionDep, user: UserDep,
) -> TransactionAddResponse:
    st = request.app.state
    now = datetime.now(timezone.utc)
    tx_id = uuid.uuid4()
    is_expense = tx.transaction_type == "expense"

    score_pct, level, flagged = 0.0, "LOW", False
    factors: list[RiskFactorOut] = []
    version: str | None = None
    degraded = False

    if is_expense:
        amount = float(tx.amount)
        try:
            feats = await st.velocity.observe(user.id, tx_id, amount, now.timestamp())
        except RedisError:
            log.warning("velocity store unavailable; scoring with neutral features")
            feats, degraded = NEUTRAL, True
        res, factors = _score_expense(st, amount, tx.category, feats, now)
        score_pct, level, flagged, version = res.score_pct, res.risk_level, res.is_flagged, res.model_version

    session.add(Transaction(
        id=tx_id, user_id=user.id, description=tx.description, merchant=tx.merchant,
        amount=tx.amount, category=tx.category, transaction_type=tx.transaction_type, occurred_at=now,
        fraud_score=score_pct, risk_level=level, is_flagged=flagged, model_version=version,
        fraud_factors=[f.model_dump() for f in factors] or None,
    ))
    await session.commit()
    background.add_task(_publish_transaction_events, tx_id, user.id, tx.category, month_key(now), is_expense)

    return TransactionAddResponse(
        id=tx_id, fraud_score=score_pct, risk_level=level, is_flagged=flagged,  # type: ignore[arg-type]
        risk_factors=factors, model_version=version, degraded=degraded,
    )


@app.post("/transaction/preview", response_model=RiskPreview)
async def preview_transaction(tx: TransactionCreate, request: Request, redis: RedisDep, user: UserDep) -> RiskPreview:
    """Live risk estimate while the user types. Pure read: nothing is persisted and the velocity windows are NOT advanced."""
    key = f"preview_rl:{user.id}"
    try:
        async with redis.pipeline(transaction=False) as p:
            p.incr(key)
            p.expire(key, 60, nx=True)
            used, _ = await p.execute()
        if used > 120:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many preview requests.")
    except RedisError:
        pass
    if tx.transaction_type != "expense":
        return RiskPreview(fraud_score=0.0, risk_level="LOW", is_flagged=False, risk_factors=[])
    st, now, amount, degraded = request.app.state, datetime.now(timezone.utc), float(tx.amount), False
    try:
        feats = await st.velocity.peek(user.id, amount, now.timestamp())
    except RedisError:
        feats, degraded = NEUTRAL, True
    res, factors = _score_expense(st, amount, tx.category, feats, now)
    return RiskPreview(fraud_score=res.score_pct, risk_level=res.risk_level, is_flagged=res.is_flagged,  # type: ignore[arg-type]
                       risk_factors=factors, degraded=degraded)


@app.get("/transactions/me", response_model=list[TransactionOut])
async def list_my_transactions(
    session: SessionDep, user: UserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0,
    category: Category | None = None, flagged_only: bool = False,
) -> list[Transaction]:
    q = select(Transaction).where(Transaction.user_id == user.id)
    if category:
        q = q.where(Transaction.category == category)
    if flagged_only:
        q = q.where(Transaction.is_flagged.is_(True))
    q = q.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(q)).scalars().all())


@app.delete("/transaction/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(tx_id: uuid.UUID, background: BackgroundTasks, session: SessionDep, user: UserDep) -> None:
    # Ownership is part of the WHERE clause: someone else's id is simply "not found".
    row = (
        await session.execute(
            delete(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id)
            .returning(Transaction.category, Transaction.occurred_at, Transaction.transaction_type)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    await session.commit()
    if row.transaction_type == "expense":
        background.add_task(_publish_budget_refresh, user.id, row.category, month_key(row.occurred_at))


def _publish_budget_refresh(user_id: uuid.UUID, category: str, month: str) -> None:
    try:
        _send("finmind.refresh_budget_spent", str(user_id), category, month)
    except Exception:
        log.exception("budget refresh publish failed; reconcile_budgets will fix it")


# ───────────────────────────── Budgets ───────────────────────────────────
@app.post("/budget/set")
async def set_budget(b: BudgetSet, background: BackgroundTasks, session: SessionDep, user: UserDep) -> dict[str, str]:
    month = b.month or month_key(datetime.now(timezone.utc))
    stmt = (
        pg_insert(Budget)
        .values(id=uuid.uuid4(), user_id=user.id, category=b.category, limit_amount=b.limit_amount, month=month)
        .on_conflict_do_update(constraint="uq_budgets_user_category_month", set_={"limit_amount": b.limit_amount})
    )
    await session.execute(stmt)
    await session.commit()
    background.add_task(_publish_budget_refresh, user.id, b.category, month)
    return {"message": "Budget saved", "month": month}


@app.get("/budgets/me", response_model=list[BudgetOut])
async def my_budgets(session: SessionDep, user: UserDep, month: MonthQuery = None) -> list[BudgetOut]:
    """`spent` is computed live from the ledger, so it is always exact (the stored column feeds the SQL agent)."""
    month = month or month_key(datetime.now(timezone.utc))
    start, end = month_bounds(month)
    rows = (
        await session.execute(
            select(Budget.category, Budget.month, Budget.limit_amount, spent_subquery(start, end).label("spent"))
            .where(Budget.user_id == user.id, Budget.month == month)
        )
    ).all()
    out = [
        BudgetOut(
            category=r.category, month=r.month, limit_amount=float(r.limit_amount), spent_amount=float(r.spent),
            percent_used=round(float(r.spent) / float(r.limit_amount) * 100, 1), over_budget=r.spent > r.limit_amount,
        )
        for r in rows
    ]
    return sorted(out, key=lambda x: x.percent_used, reverse=True)


# ───────────────────────────── Analytics (read precomputed results) ──────
@app.get("/anomalies/me", response_model=AnomalyReport)
async def my_anomalies(session: SessionDep, user: UserDep, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> AnomalyReport:
    """No model is fitted here. Scores are produced by the nightly batch (see tasks.py)."""
    n, scored_at, method = (
        await session.execute(
            select(
                func.count().filter(Transaction.transaction_type == "expense"),
                func.max(Transaction.anomaly_scored_at), func.max(Transaction.anomaly_method),
            ).where(Transaction.user_id == user.id)
        )
    ).one()
    base = dict(expense_count=n, min_required=analytics.MIN_MAD)
    if n < analytics.MIN_MAD:
        return AnomalyReport(status="insufficient_data", message=f"Need at least {analytics.MIN_MAD} expenses.", **base)
    if scored_at is None:
        return AnomalyReport(status="pending", message="Next nightly run will score your history.", **base)

    rows = (
        await session.execute(
            select(Transaction).where(Transaction.user_id == user.id, Transaction.is_anomaly.is_(True))
            .order_by(Transaction.anomaly_score.desc()).limit(limit)
        )
    ).scalars().all()
    reason = {"isolation_forest": "Unusual combination of amount, time and category for your history",
              "mad": "Amount is far above your typical spend"}
    return AnomalyReport(
        status="ok", method=method, scored_at=scored_at,
        anomalies=[
            AnomalyOut(id=t.id, description=t.description, amount=float(t.amount), category=t.category,
                       occurred_at=t.occurred_at, anomaly_score=round(t.anomaly_score or 0.0, 4),
                       method=t.anomaly_method or "", reason=reason.get(t.anomaly_method or "", "Unusual for you"))
            for t in rows
        ],
        **base,
    )


@app.get("/forecast/me")
async def my_forecast(redis: RedisDep, user: UserDep) -> JSONResponse:
    """Served from a nightly-refreshed Redis cache. A miss enqueues a job and returns 202."""
    cached = await redis.get(f"forecast:{user.id}")
    if cached:
        return JSONResponse(json.loads(cached))
    if await redis.set(f"forecast_pending:{user.id}", "1", nx=True, ex=60):
        await _enqueue("finmind.forecast_user", str(user.id))
    return JSONResponse({"status": "pending", "message": "Forecast is being computed; retry shortly."}, status_code=202)


@app.post("/analytics/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_analytics(redis: RedisDep, user: UserDep) -> dict[str, str]:
    """On-demand recompute of anomalies + forecast for the caller (throttled to once a minute)."""
    if not await redis.set(f"analytics_refresh:{user.id}", "1", nx=True, ex=60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Refresh already requested recently")
    await redis.delete(f"forecast:{user.id}")
    await _enqueue("finmind.score_user_anomalies", str(user.id))
    await _enqueue("finmind.forecast_user", str(user.id))
    return {"status": "queued"}


# ───────────────────────────── Bank Connection (AA) ──────────────────────
import hashlib
import re
from pydantic import BaseModel, Field


class BankConnectRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian mobile number")


class BankConnectionOut(BaseModel):
    id: uuid.UUID
    fip_id: str
    fip_name: str
    status: str
    consent_id: str
    consent_start: datetime
    consent_expiry: datetime
    last_synced_at: datetime | None = None
    created_at: datetime


@app.post("/api/bank/connect")
async def connect_bank(
    req: BankConnectRequest,
    session: SessionDep,
    redis: RedisDep,
    user: UserDep,
) -> dict[str, Any]:
    """Initiate Account Aggregator bank connection."""
    # Validate phone format: 10 digits starting with 6-9
    clean_phone = req.phone.strip()
    if clean_phone.startswith("+91"):
        clean_phone = clean_phone[3:].strip()
    elif clean_phone.startswith("91") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:].strip()

    if not re.fullmatch(r"^[6-9]\d{9}$", clean_phone):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid 10-digit Indian mobile number")

    # Rate limited: max 3 per user per hour
    rl_key = f"bank_connect_rl:{user.id}"
    attempts = await redis.incr(rl_key)
    if attempts == 1:
        await redis.expire(rl_key, 3600)
    if attempts > 3:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many connection attempts. Max 3 per hour.")

    settings = get_settings()
    client = AAGatewayClient(
        base_url=settings.aa_base_url,
        api_key=settings.aa_api_key or "sandbox-mock-key",
        api_secret=settings.aa_api_secret or "",
        webhook_secret=settings.aa_webhook_secret or "",
    )
    try:
        consent_data = await client.create_consent_request(user.id, clean_phone)
    except Exception as exc:
        log.error("Failed to create consent request: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Account Aggregator error: {exc}")
    finally:
        await client.close()

    phone_hash = hashlib.sha256(clean_phone.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=180)

    connection = BankConnection(
        id=uuid.uuid4(),
        user_id=user.id,
        consent_id=consent_data["consent_id"],
        consent_handle=consent_data.get("consent_handle"),
        fip_id="SETU-FIP-MOCK",
        fip_name="Sandbox Mock Bank",
        phone_hash=phone_hash,
        status="PENDING",
        consent_start=now,
        consent_expiry=expiry,
    )
    session.add(connection)
    await session.commit()

    return {
        "consent_id": consent_data["consent_id"],
        "redirect_url": consent_data["redirect_url"],
        "status": "PENDING",
    }


@app.get("/api/bank/connections", response_model=list[BankConnectionOut])
async def list_bank_connections(session: SessionDep, user: UserDep) -> list[BankConnectionOut]:
    """List bank connections for current user."""
    rows = (
        await session.execute(
            select(BankConnection).where(BankConnection.user_id == user.id).order_by(BankConnection.created_at.desc())
        )
    ).scalars().all()
    return [
        BankConnectionOut(
            id=r.id,
            fip_id=r.fip_id,
            fip_name=r.fip_name,
            status=r.status,
            consent_id=r.consent_id,
            consent_start=r.consent_start,
            consent_expiry=r.consent_expiry,
            last_synced_at=r.last_synced_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@app.post("/api/bank/sync/{connection_id}", status_code=status.HTTP_202_ACCEPTED)
async def sync_bank_connection(
    connection_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
) -> dict[str, str]:
    """Manual sync trigger for active bank connection."""
    conn = (
        await session.execute(
            select(BankConnection).where(BankConnection.id == connection_id, BankConnection.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank connection not found")
    if conn.status != "ACTIVE":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot sync connection with status '{conn.status}'")

    settings = get_settings()
    client = AAGatewayClient(
        base_url=settings.aa_base_url,
        api_key=settings.aa_api_key or "sandbox-mock-key",
        api_secret=settings.aa_api_secret or "",
        webhook_secret=settings.aa_webhook_secret or "",
    )
    try:
        session_info = await client.create_data_session(conn.consent_id)
        session_id = session_info["session_id"]
    except Exception as exc:
        log.error("Failed to create AA data session: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Failed to initiate bank sync: {exc}")
    finally:
        await client.close()

    await _enqueue("finmind.process_aa_data_session", session_id, str(user.id), str(conn.id))
    return {"status": "sync_queued", "session_id": session_id}


@app.delete("/api/bank/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_bank_connection(
    connection_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
) -> None:
    """Revoke consent for bank connection."""
    conn = (
        await session.execute(
            select(BankConnection).where(BankConnection.id == connection_id, BankConnection.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank connection not found")

    settings = get_settings()
    client = AAGatewayClient(
        base_url=settings.aa_base_url,
        api_key=settings.aa_api_key or "sandbox-mock-key",
        api_secret=settings.aa_api_secret or "",
        webhook_secret=settings.aa_webhook_secret or "",
    )
    try:
        await client.revoke_consent(conn.consent_id)
    except Exception as exc:
        log.warning("Revoke AA consent upstream warning: %s", exc)
    finally:
        await client.close()

    conn.status = "REVOKED"
    await session.commit()


@app.post("/api/webhooks/account-aggregator", status_code=status.HTTP_200_OK)
async def handle_aa_webhook(
    request: Request,
    session: SessionDep,
) -> dict[str, str]:
    """Webhook handler for AA gateway events."""
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature") or ""

    settings = get_settings()
    secret = settings.aa_webhook_secret or ""

    if not signature or not secret or not verify_webhook_signature(raw_body, signature, secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing webhook signature")

    try:
        event = json.loads(raw_body)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON body")

    event_type = event.get("type") or event.get("eventType") or ""
    consent_id = event.get("consentId") or event.get("ConsentStatusNotification", {}).get("consentId")

    if event_type == "CONSENT_STATUS_UPDATE" or "ConsentStatusNotification" in event:
        status_val = (
            event.get("status")
            or event.get("ConsentStatusNotification", {}).get("consentStatus")
            or ""
        ).upper()
        if consent_id:
            conn = (
                await session.execute(
                    select(BankConnection).where(BankConnection.consent_id == consent_id)
                )
            ).scalar_one_or_none()
            if conn:
                if status_val in ("ACTIVE", "READY", "SUCCEEDED", "APPROVED"):
                    conn.status = "ACTIVE"
                    await session.commit()
                    # Trigger initial sync
                    try:
                        client = AAGatewayClient(
                            base_url=settings.aa_base_url,
                            api_key=settings.aa_api_key or "sandbox-mock-key",
                            api_secret=settings.aa_api_secret or "",
                            webhook_secret=settings.aa_webhook_secret or "",
                        )
                        session_info = await client.create_data_session(conn.consent_id)
                        await client.close()
                        await _enqueue("finmind.process_aa_data_session", session_info["session_id"], str(conn.user_id), str(conn.id))
                    except Exception as exc:
                        log.error("Failed to trigger initial sync after consent approval: %s", exc)
                elif status_val in ("REVOKED", "EXPIRED", "REJECTED", "FAILED"):
                    conn.status = "REVOKED" if status_val == "REVOKED" else ("EXPIRED" if status_val == "EXPIRED" else "REVOKED")
                    await session.commit()

    elif event_type == "SESSION_STATUS_UPDATE" or "FIStatusNotification" in event:
        session_id = event.get("sessionId") or event.get("FIStatusNotification", {}).get("sessionId")
        session_status = (
            event.get("sessionStatus")
            or event.get("FIStatusNotification", {}).get("sessionStatus")
            or ""
        ).upper()
        if session_id and (session_status in ("COMPLETED", "READY", "SUCCESS") or not session_status):
            # Find bank connection by consent_id if available or session lookup
            if consent_id:
                conn = (
                    await session.execute(
                        select(BankConnection).where(BankConnection.consent_id == consent_id)
                    )
                ).scalar_one_or_none()
                if conn:
                    await _enqueue("finmind.process_aa_data_session", session_id, str(conn.user_id), str(conn.id))

    return {"status": "ok"}


# ───────────────────────────── Chat (hybrid agent) ───────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, redis: RedisDep, user: UserDep) -> ChatResponse:
    """User id comes from the verified token; the agent can only ever see this user's rows."""
    llm = request.app.state.llm
    if llm is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Chat is not configured (GROQ_API_KEY missing).")
    key = f"chat_rl:{user.id}"
    try:  # LLM calls cost money: throttle per user
        async with redis.pipeline(transaction=False) as p:
            p.incr(key)
            p.expire(key, 60, nx=True)
            used, _ = await p.execute()
        if used > get_settings().chat_rate_per_minute:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many chat messages. Slow down a little.")
    except RedisError:
        pass  # limiter fails open
    result = await run_agent(
        llm=llm, question=req.message, history=[t.model_dump() for t in req.chat_history],
        user_id=user.id, tz_name=get_settings().app_timezone,
    )
    return ChatResponse(reply=result.reply, tool_trace=[ToolTraceOut(**e) for e in result.trace])


# ───────────────────────────── Account ───────────────────────────────────
@app.delete("/account/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_account(request: Request, session: SessionDep, user: UserDep) -> None:
    await session.execute(delete(Transaction).where(Transaction.user_id == user.id))
    await session.execute(update(Budget).where(Budget.user_id == user.id).values(spent_amount=0))
    await session.commit()
    try:
        await request.app.state.velocity.clear(user.id)
    except RedisError:
        log.warning("could not clear velocity windows for %s", user.id)
