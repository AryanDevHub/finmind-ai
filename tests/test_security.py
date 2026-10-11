"""Tests for security hardening: token rotation, replay detection, BOLA, encryption."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest
import pytest_asyncio

from backend.auth import decode_access_token
from backend.database import BankConnection
from backend.encryption import decrypt, encrypt
from backend.settings import Settings, get_settings
from tests.conftest import Account

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# 1. Refresh Token Rotation
# ─────────────────────────────────────────────────────────────────────────────
async def test_refresh_token_rotation(make_account, app):
    """Login, get refresh cookie, call /auth/refresh, verify new token issued and old cookie invalidated."""
    account = await make_account("sec_rotation")
    initial_cookie = account.client.cookies.get("refresh_token")
    assert initial_cookie is not None

    # Call /auth/refresh
    refresh_res = await account.client.post("/auth/refresh")
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["access_token"]
    assert new_access_token is not None

    # Verify a new refresh cookie was issued
    rotated_cookie = account.client.cookies.get("refresh_token")
    assert rotated_cookie is not None
    assert rotated_cookie != initial_cookie

    # Verify the old cookie is invalidated immediately
    stale_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"refresh_token": initial_cookie},
    )
    stale_res = await stale_client.post("/auth/refresh")
    assert stale_res.status_code == 401
    await stale_client.aclose()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Refresh Token Replay Revokes Family
# ─────────────────────────────────────────────────────────────────────────────
async def test_refresh_token_replay_revokes_family(make_account, app):
    """Use the same refresh token twice -> second use should return 401 AND revoke the entire family."""
    account = await make_account("sec_family_replay")
    token_1 = account.client.cookies.get("refresh_token")
    assert token_1 is not None

    # First legitimate rotation: token_1 is replaced with token_2
    r_rot = await account.client.post("/auth/refresh")
    assert r_rot.status_code == 200
    token_2 = account.client.cookies.get("refresh_token")
    assert token_2 != token_1

    # Attacker or replayed request presents already-used token_1
    attacker_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"refresh_token": token_1},
    )
    r_replay = await attacker_client.post("/auth/refresh")
    assert r_replay.status_code == 401
    assert "reuse detected" in r_replay.json()["detail"].lower()
    await attacker_client.aclose()

    # Theft defense: legitimate user presenting token_2 is now ALSO revoked (entire family killed)
    r_legit_after_theft = await account.client.post("/auth/refresh")
    assert r_legit_after_theft.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 3. Access Token Blacklist on Logout
# ─────────────────────────────────────────────────────────────────────────────
async def test_access_token_blacklist_on_logout(make_account, app):
    """After logout, the access token jti should be blacklisted in Redis."""
    account = await make_account("sec_blacklist")

    # Ensure authenticated endpoint works before logout
    me_before = await account.client.get("/auth/me", headers=account.h)
    assert me_before.status_code == 200

    # Extract token jti
    current_user = decode_access_token(account.token)
    redis = app.state.redis
    blacklist_key = f"bl:{current_user.jti}"

    # Before logout, jti is not in blacklist
    assert not await redis.exists(blacklist_key)

    # Perform logout
    logout_res = await account.client.post("/auth/logout", headers=account.h)
    assert logout_res.status_code == 204

    # JTI is now recorded in Redis blacklist
    assert await redis.exists(blacklist_key)

    # Subsequent request using the blacklisted access token is rejected
    me_after = await account.client.get("/auth/me", headers=account.h)
    assert me_after.status_code == 401
    assert "revoked" in me_after.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Expired Access Token Rejected
# ─────────────────────────────────────────────────────────────────────────────
async def test_expired_access_token_rejected(client, alice):
    """A token beyond 15 minutes is rejected."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(alice.id),
        "jti": uuid.uuid4().hex,
        "typ": "access",
        "iat": now - timedelta(minutes=20),
        "exp": now - timedelta(minutes=5),  # Expired 5 minutes ago
    }
    expired_token = jwt.encode(expired_payload, s.secret_key, algorithm=s.jwt_algorithm)

    r = await client.get("/transactions/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401
    assert "Could not validate credentials" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. BOLA: Transactions
# ─────────────────────────────────────────────────────────────────────────────
async def test_bola_transactions(alice, bob):
    """User A cannot access User B's transactions."""
    expense = {
        "description": "Alice Confidential Dinner",
        "amount": "1250.00",
        "category": "Food",
        "transaction_type": "expense",
    }
    create_res = await alice.client.post("/transaction/add", headers=alice.h, json=expense)
    assert create_res.status_code == 200
    alice_tx_id = create_res.json()["id"]

    # Bob lists transactions: cannot see Alice's transaction
    bob_txs = (await bob.client.get("/transactions/me", headers=bob.h)).json()
    assert all(tx["id"] != alice_tx_id for tx in bob_txs)

    # Directly requesting transactions by user ID parameter is rejected / not enumerable
    bola_url_attempt = await bob.client.get(f"/transactions/{alice.id}", headers=bob.h)
    assert bola_url_attempt.status_code in (404, 405)


# ─────────────────────────────────────────────────────────────────────────────
# 6. BOLA: Budgets
# ─────────────────────────────────────────────────────────────────────────────
async def test_bola_budgets(alice, bob):
    """User A cannot see User B's budgets."""
    budget_payload = {"category": "Entertainment", "limit_amount": "5000.00"}
    res = await alice.client.post("/budget/set", headers=alice.h, json=budget_payload)
    assert res.status_code == 200

    bob_budgets = (await bob.client.get("/budgets/me", headers=bob.h)).json()
    # Bob should not see Alice's Entertainment budget
    matching_budgets = [
        b for b in bob_budgets
        if b.get("category") == "Entertainment" and float(b.get("limit_amount", 0)) == 5000.00
    ]
    assert len(matching_budgets) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. BOLA: Delete Transaction
# ─────────────────────────────────────────────────────────────────────────────
async def test_bola_delete_transaction(alice, bob):
    """User A cannot delete User B's transactions."""
    expense = {
        "description": "Alice Flight Ticket",
        "amount": "4500.00",
        "category": "Transport",
        "transaction_type": "expense",
    }
    tx_id = (await alice.client.post("/transaction/add", headers=alice.h, json=expense)).json()["id"]

    # Bob attempts to delete Alice's transaction
    bob_delete_res = await bob.client.delete(f"/transaction/{tx_id}", headers=bob.h)
    assert bob_delete_res.status_code == 404

    # Alice verifies transaction is still intact
    alice_txs = (await alice.client.get("/transactions/me", headers=alice.h)).json()
    assert any(t["id"] == tx_id for t in alice_txs)


# ─────────────────────────────────────────────────────────────────────────────
# 8. BOLA: Bank Connections
# ─────────────────────────────────────────────────────────────────────────────
async def test_bola_bank_connections(alice, bob):
    """User A cannot see/sync/revoke User B's bank connections."""
    consent_id = f"consent-alice-bola-{uuid.uuid4().hex}"
    with patch(
        "backend.main.AAGatewayClient.create_consent_request",
        new_callable=AsyncMock,
        return_value={
            "consent_id": consent_id,
            "redirect_url": "https://sandbox.setu.co/consent/ui",
            "consent_handle": "handle-alice-bola",
        },
    ):
        connect_res = await alice.client.post(
            "/api/bank/connect",
            headers=alice.h,
            json={"phone": "9876543210"},
        )
        assert connect_res.status_code == 200

    # Alice gets her connection id
    alice_conns = (await alice.client.get("/api/bank/connections", headers=alice.h)).json()
    assert len(alice_conns) > 0
    alice_conn = next(c for c in alice_conns if c["consent_id"] == consent_id)
    alice_conn_id = alice_conn["id"]

    # Bob cannot see Alice's bank connection
    bob_conns = (await bob.client.get("/api/bank/connections", headers=bob.h)).json()
    assert all(c["id"] != alice_conn_id for c in bob_conns)

    # Bob cannot trigger sync on Alice's bank connection -> 404
    bob_sync_res = await bob.client.post(f"/api/bank/sync/{alice_conn_id}", headers=bob.h)
    assert bob_sync_res.status_code == 404

    # Bob cannot revoke Alice's bank connection -> 404
    bob_revoke_res = await bob.client.delete(f"/api/bank/connections/{alice_conn_id}", headers=bob.h)
    assert bob_revoke_res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 9. CORS No Wildcard
# ─────────────────────────────────────────────────────────────────────────────
async def test_cors_no_wildcard(client):
    """Verify CORS does not allow '*' origin."""
    # 1. Pydantic settings validator enforces explicit origins and forbids '*'
    with pytest.raises(ValueError, match=r"CORS_ORIGINS must list explicit origins; '\*' is not allowed"):
        Settings(secret_key="0123456789abcdef0123456789abcdef", cors_origins="*")

    with pytest.raises(ValueError, match=r"CORS_ORIGINS must list explicit origins; '\*' is not allowed"):
        Settings(secret_key="0123456789abcdef0123456789abcdef", cors_origins="https://app.finmind.ai,*")

    # 2. CORS preflight check: wildcards or arbitrary origins are rejected
    preflight = await client.options(
        "/auth/login",
        headers={"Origin": "*", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.headers.get("access-control-allow-origin") != "*"

    evil_preflight = await client.options(
        "/auth/login",
        headers={"Origin": "https://malicious-attacker.com", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil_preflight.headers


# ─────────────────────────────────────────────────────────────────────────────
# 10. Encryption Roundtrip
# ─────────────────────────────────────────────────────────────────────────────
def test_encryption_roundtrip():
    """Test encrypt/decrypt produces original plaintext."""
    test_cases = [
        "Sensitive consent token 12345",
        "BANK_A/C_NO:98765432109876",
        "Special chars: !@#$%^&*()_+{}[]:;\"'<>?,./~`",
        "Unicode: ₹ 50,000 / 銀行 / éàüö",
        "Long payload " * 128,
        "",
    ]
    for plaintext in test_cases:
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        decrypted = decrypt(ciphertext)
        assert decrypted == plaintext


# ─────────────────────────────────────────────────────────────────────────────
# 11. Encryption Tamper Detection
# ─────────────────────────────────────────────────────────────────────────────
def test_encryption_tamper_detection():
    """Modifying encrypted data raises ValueError."""
    original_text = "Highly Confidential Bank Financial Data"
    token = encrypt(original_text)

    # 1. Invalid base64
    with pytest.raises(ValueError, match=r"Invalid base64 encoding"):
        decrypt("not-valid-base64%%%")

    # 2. Payload too short (less than 28 bytes: 12-byte nonce + 16-byte tag)
    short_token = base64.b64encode(b"short").decode("ascii")
    with pytest.raises(ValueError, match=r"payload too short"):
        decrypt(short_token)

    # 3. Bit flip in ciphertext/tag
    raw_payload = bytearray(base64.b64decode(token))
    raw_payload[-1] ^= 0x01  # Alter authentication tag
    tampered_token = base64.b64encode(raw_payload).decode("ascii")
    with pytest.raises(ValueError, match=r"corrupted or tampered ciphertext"):
        decrypt(tampered_token)

    # 4. Bit flip in nonce
    raw_nonce = bytearray(base64.b64decode(token))
    raw_nonce[0] ^= 0x01  # Alter nonce
    tampered_nonce_token = base64.b64encode(raw_nonce).decode("ascii")
    with pytest.raises(ValueError, match=r"corrupted or tampered ciphertext"):
        decrypt(tampered_nonce_token)


# ─────────────────────────────────────────────────────────────────────────────
# 12. Login Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────
async def test_login_rate_limiting(client, alice):
    """After N failed logins, subsequent attempts return 429."""
    # Test harness configures LOGIN_MAX_ATTEMPTS=5
    max_attempts = 5

    for _ in range(max_attempts):
        failed_res = await client.post(
            "/auth/login",
            data={"username": alice.username, "password": "wrong-password-test"},
        )
        assert failed_res.status_code == 401

    # Next attempt must be rate-limited
    throttled_res = await client.post(
        "/auth/login",
        data={"username": alice.username, "password": "wrong-password-test"},
    )
    assert throttled_res.status_code == 429
    assert "Too many failed attempts" in throttled_res.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 13. User ID From Token Only
# ─────────────────────────────────────────────────────────────────────────────
async def test_user_id_from_token_only(alice, app):
    """Verify no endpoint accepts user_id from body/params."""
    fake_user_id = str(uuid.uuid4())

    # 1. POST /transaction/add rejects request bodies containing user_id
    tampered_body = {
        "description": "Bypass Attempt",
        "amount": "100.00",
        "category": "Food",
        "transaction_type": "expense",
        "user_id": fake_user_id,
    }
    r_add = await alice.client.post("/transaction/add", headers=alice.h, json=tampered_body)
    assert r_add.status_code == 422  # extra fields forbidden in TransactionCreate

    # 2. Query param injection: /transactions/me?user_id=... is ignored; only token identity is used
    r_list = await alice.client.get(f"/transactions/me?user_id={fake_user_id}", headers=alice.h)
    assert r_list.status_code == 200

    # 3. Router inspection: verify authenticated data routes do not accept user_id in path
    sensitive_prefixes = ("/transactions/", "/budgets/", "/forecast/", "/anomalies/", "/api/bank/")
    for route in app.routes:
        path = getattr(route, "path", "")
        for prefix in sensitive_prefixes:
            if path.startswith(prefix):
                assert "{user_id}" not in path
                assert "{userId}" not in path
