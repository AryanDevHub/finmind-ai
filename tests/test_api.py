"""API integration tests: async routes against real Postgres + Redis, with the ONNX model mocked."""
from __future__ import annotations

import uuid

import httpx
import pytest
from redis.exceptions import RedisError

pytestmark = pytest.mark.asyncio

EXPENSE = {"description": "Swiggy", "amount": "450.50", "category": "Food", "transaction_type": "expense"}


# ───────────────────────────── health / validation ───────────────────────
async def test_health_and_ready(client):
    assert (await client.get("/health")).json()["status"] == "ok"
    r = await client.get("/ready")
    assert r.status_code == 200 and r.json()["postgres"] and r.json()["redis"]


async def test_register_validation(client):
    bad = [{"username": "ab", "email": "x@y.com", "password": "longenough1"},
           {"username": "valid_user", "email": "not-an-email", "password": "longenough1"},
           {"username": "valid_user", "email": "x@y.com", "password": "short"},
           {"username": "bad name!", "email": "x@y.com", "password": "longenough1"}]
    for payload in bad:
        assert (await client.post("/auth/register", json=payload)).status_code == 422


async def test_duplicate_registration_conflicts(client, alice):
    r = await client.post("/auth/register", json={"username": alice.username, "email": "other@example.com", "password": "correct-horse-1"})
    assert r.status_code == 409


# ───────────────────────────── auth & sessions ───────────────────────────
async def test_login_sets_hardened_refresh_cookie(client, alice):
    r = await client.post("/auth/login", data={"username": alice.username, "password": alice.password})
    assert r.status_code == 200 and r.json()["expires_in"] == 900
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie


async def test_login_by_email_and_generic_failure(client, alice):
    assert (await client.post("/auth/login", data={"username": f"{alice.username}@example.com".upper(), "password": alice.password})).status_code == 200
    wrong = await client.post("/auth/login", data={"username": alice.username, "password": "nope-nope-nope"})
    ghost = await client.post("/auth/login", data={"username": "nobody-here", "password": "nope-nope-nope"})
    assert wrong.status_code == ghost.status_code == 401 and wrong.json() == ghost.json()  # no user enumeration


async def test_protected_routes_need_a_valid_token(client):
    assert (await client.get("/transactions/me")).status_code == 401
    assert (await client.get("/transactions/me", headers={"Authorization": "Bearer garbage"})).status_code == 401


async def test_refresh_rotates_and_replay_kills_the_family(make_account, app):
    a = await make_account()
    first = a.client.cookies.get("refresh_token")
    r = await a.client.post("/auth/refresh")
    assert r.status_code == 200 and a.client.cookies.get("refresh_token") != first
    thief = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies={"refresh_token": first})
    assert (await thief.post("/auth/refresh")).status_code == 401           # replayed old token
    assert (await a.client.post("/auth/refresh")).status_code == 401        # whole family revoked, legit holder too
    await thief.aclose()


async def test_logout_revokes_access_token_immediately(make_account):
    a = await make_account()
    assert (await a.client.get("/auth/me", headers=a.h)).status_code == 200
    assert (await a.client.post("/auth/logout", headers=a.h)).status_code == 204
    r = await a.client.get("/auth/me", headers=a.h)
    assert r.status_code == 401 and "revoked" in r.json()["detail"]
    assert (await a.client.post("/auth/refresh")).status_code == 401


async def test_brute_force_is_throttled(client, alice):
    codes = [(await client.post("/auth/login", data={"username": alice.username, "password": "wrong-wrong"})).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429                       # LOGIN_MAX_ATTEMPTS=5 in tests


async def test_cors_whitelist(client):
    ok = await client.options("/auth/login", headers={"Origin": "http://localhost:8501", "Access-Control-Request-Method": "POST"})
    evil = await client.options("/auth/login", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-origin" not in evil.headers


# ───────────────────────────── transactions ──────────────────────────────
async def test_expense_is_scored_with_top3_factors_and_persisted(alice, scorer):
    scorer.level, scorer.probability = "HIGH", 0.7
    r = await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)
    body = r.json()
    assert r.status_code == 200 and body["risk_level"] == "HIGH" and body["is_flagged"] and body["fraud_score"] == 70.0
    assert len(body["risk_factors"]) == 3 and body["risk_factors"][0]["label"] == "Transactions in last 5 minutes"
    assert body["model_version"] == "test-model" and uuid.UUID(body["id"]) and body["degraded"] is False
    rows = (await alice.client.get("/transactions/me", headers=alice.h)).json()
    assert rows[0]["id"] == body["id"] and rows[0]["is_flagged"] and rows[0]["fraud_factors"][0]["feature"] == "tx_count_5m"
    assert rows[0]["amount"] == 450.5


async def test_income_is_never_scored(alice, scorer):
    r = await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "category": "Salary", "transaction_type": "income"})
    assert r.status_code == 200 and r.json()["risk_factors"] == [] and r.json()["risk_level"] == "LOW"
    assert scorer.calls == []


async def test_velocity_features_flow_through_redis_into_the_model(alice, scorer):
    for _ in range(3):
        assert (await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "amount": "100"})).status_code == 200
    assert [c["tx_count_5m"] for c in scorer.calls] == [0.0, 1.0, 2.0]       # prior txs in the 5-minute window
    assert [c["tx_sum_24h"] for c in scorer.calls] == [0.0, 100.0, 200.0]
    assert scorer.calls[0]["amount_to_avg_ratio"] == 1.0                       # cold start
    assert scorer.calls[0]["hour"] in range(24) and scorer.calls[0]["day_of_week"] in range(7)


async def test_scoring_degrades_gracefully_when_redis_velocity_fails(alice, scorer, app, monkeypatch):
    async def boom(*a, **k):
        raise RedisError("down")
    monkeypatch.setattr(app.state.velocity, "observe", boom)
    r = await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)
    assert r.status_code == 200 and r.json()["degraded"] is True
    assert scorer.calls[0]["tx_count_5m"] == 0.0 and scorer.calls[0]["amount_to_avg_ratio"] == 1.0


@pytest.mark.parametrize("patch", [
    {"amount": "-5"}, {"amount": "0"}, {"category": "Nope"}, {"transaction_type": "transfer"}, {"description": "   "},
    {"occurred_at": "2020-01-01T00:00:00Z"},                                   # clients cannot choose the timestamp
])
async def test_invalid_transactions_are_rejected(alice, patch):
    assert (await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, **patch})).status_code == 422


async def test_events_are_published_after_the_response(alice, sent_tasks):
    tx_id = (await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)).json()["id"]
    names = [t[0] for t in sent_tasks]
    assert ("finmind.embed_transaction", tx_id) in sent_tasks and "finmind.refresh_budget_spent" in names


async def test_users_are_isolated_and_ids_are_not_enumerable(alice, bob):
    tx = (await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)).json()["id"]
    assert (await bob.client.get("/transactions/me", headers=bob.h)).json() == []
    assert (await bob.client.delete(f"/transaction/{tx}", headers=bob.h)).status_code == 404
    assert (await alice.client.get(f"/transactions/{alice.id}", headers=alice.h)).status_code in (404, 405)
    assert (await alice.client.delete(f"/transaction/{tx}", headers=alice.h)).status_code == 204
    assert (await alice.client.delete("/transaction/not-a-uuid", headers=alice.h)).status_code == 422


async def test_pagination_and_filters(alice, scorer):
    scorer.level = "HIGH"
    for i in range(5):
        await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "description": f"t{i}"})
    scorer.level = "LOW"
    await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "category": "Transport", "description": "bus"})
    assert len((await alice.client.get("/transactions/me?limit=2", headers=alice.h)).json()) == 2
    assert len((await alice.client.get("/transactions/me?flagged_only=true", headers=alice.h)).json()) == 5
    assert [t["description"] for t in (await alice.client.get("/transactions/me?category=Transport", headers=alice.h)).json()] == ["bus"]


# ───────────────────────────── budgets ───────────────────────────────────
async def test_budget_upsert_and_live_spend(alice):
    for amt in ("400", "250.50"):
        await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "amount": amt})
    await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "category": "Salary", "transaction_type": "income", "amount": "9999"})
    assert (await alice.client.post("/budget/set", headers=alice.h, json={"category": "Food", "limit_amount": "1000"})).status_code == 200
    assert (await alice.client.post("/budget/set", headers=alice.h, json={"category": "Food", "limit_amount": "600"})).status_code == 200
    b = (await alice.client.get("/budgets/me", headers=alice.h)).json()
    assert len(b) == 1 and b[0]["limit_amount"] == 600 and b[0]["spent_amount"] == 650.5
    assert b[0]["over_budget"] is True and b[0]["percent_used"] == 108.4       # income is excluded from spend


async def test_budget_validation(alice):
    assert (await alice.client.post("/budget/set", headers=alice.h, json={"category": "Food", "limit_amount": "0"})).status_code == 422
    assert (await alice.client.post("/budget/set", headers=alice.h, json={"category": "Food", "limit_amount": "5", "month": "2026-13"})).status_code == 422


# ───────────────────────────── analytics endpoints ───────────────────────
async def test_anomalies_report_states(alice, sent_tasks):
    r = (await alice.client.get("/anomalies/me", headers=alice.h)).json()
    assert r["status"] == "insufficient_data" and r["min_required"] == 10
    for i in range(10):
        await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "description": f"e{i}"})
    assert (await alice.client.get("/anomalies/me", headers=alice.h)).json()["status"] == "pending"   # nothing is fitted in the request path


async def test_forecast_is_async_and_cached(alice, sent_tasks, app):
    r = await alice.client.get("/forecast/me", headers=alice.h)
    assert r.status_code == 202 and r.json()["status"] == "pending"
    await alice.client.get("/forecast/me", headers=alice.h)
    assert [t for t in sent_tasks if t[0] == "finmind.forecast_user"] == [("finmind.forecast_user", alice.id)]  # enqueued once
    await app.state.redis.set(f"forecast:{alice.id}", '{"status": "ok", "total_next_4_weeks": 1}')
    assert (await alice.client.get("/forecast/me", headers=alice.h)).json()["total_next_4_weeks"] == 1


async def test_account_reset_clears_ledger_and_velocity(alice, scorer):
    await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)
    assert (await alice.client.delete("/account/reset", headers=alice.h)).status_code == 204
    assert (await alice.client.get("/transactions/me", headers=alice.h)).json() == []
    await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)
    assert scorer.calls[-1]["tx_count_5m"] == 0.0                              # window was cleared


# ───────────────────────────── live risk preview ─────────────────────────
async def test_preview_scores_without_side_effects(alice, scorer):
    scorer.level, scorer.probability = "MEDIUM", 0.45
    for _ in range(3):                                                         # previews must not advance velocity or persist
        r = await alice.client.post("/transaction/preview", headers=alice.h, json=EXPENSE)
        assert r.status_code == 200 and r.json()["risk_level"] == "MEDIUM" and r.json()["fraud_score"] == 45.0
        assert len(r.json()["risk_factors"]) == 3 and "id" not in r.json()
    assert (await alice.client.get("/transactions/me", headers=alice.h)).json() == []
    await alice.client.post("/transaction/add", headers=alice.h, json=EXPENSE)
    assert scorer.calls[-1]["tx_count_5m"] == 0.0 and scorer.calls[-1]["tx_sum_24h"] == 0.0   # the 3 previews left no trace


async def test_preview_sees_real_velocity_and_handles_income(alice, scorer):
    for _ in range(2):
        await alice.client.post("/transaction/add", headers=alice.h, json={**EXPENSE, "amount": "100"})
    await alice.client.post("/transaction/preview", headers=alice.h, json={**EXPENSE, "amount": "100"})
    assert scorer.calls[-1]["tx_count_5m"] == 2.0 and scorer.calls[-1]["tx_sum_24h"] == 200.0
    n = len(scorer.calls)
    r = await alice.client.post("/transaction/preview", headers=alice.h, json={**EXPENSE, "category": "Salary", "transaction_type": "income"})
    assert r.json() == {"fraud_score": 0.0, "risk_level": "LOW", "is_flagged": False, "risk_factors": [], "degraded": False}
    assert len(scorer.calls) == n                                              # income never reaches the model


async def test_preview_requires_auth_validates_and_degrades(client, alice, scorer, app, monkeypatch):
    assert (await client.post("/transaction/preview", json=EXPENSE)).status_code == 401
    assert (await alice.client.post("/transaction/preview", headers=alice.h, json={**EXPENSE, "amount": "-1"})).status_code == 422

    async def boom(*a, **k):
        raise RedisError("down")
    monkeypatch.setattr(app.state.velocity, "peek", boom)
    r = await alice.client.post("/transaction/preview", headers=alice.h, json=EXPENSE)
    assert r.status_code == 200 and r.json()["degraded"] is True


def test_one_hot_category_labels_say_what_the_model_saw():
    from backend.main import _factor_label
    assert _factor_label("cat_Food", 1.0) == "Category is Food"
    assert _factor_label("cat_Food", 0.0) == "Category is not Food"      # never "Category: Food" for a non-Food purchase
    assert _factor_label("tx_count_5m", 9.0) == "Transactions in last 5 minutes"
