"""Tests for the Account Aggregator bank sync pipeline."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from backend.aa_client import (
    AAGatewayClient,
    classify_transaction_type,
    compute_dedup_hash,
    extract_merchant_name,
    sanitize_narration,
    verify_webhook_signature,
)
from backend.database import BankConnection
from backend.settings import get_settings
from tests.conftest import Account

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# 1. AA Client Consent Request
# ─────────────────────────────────────────────────────────────────────────────
async def test_aa_client_consent_request():
    """Test AAGatewayClient.create_consent_request returns expected structure (mock httpx)."""
    client = AAGatewayClient(
        base_url="https://sandbox.setu.co/api",
        api_key="test-api-key",
        api_secret="test-api-secret",
        webhook_secret="test-webhook-secret",
    )
    mock_payload = {
        "ConsentHandle": "handle-12345",
        "consentId": "consent-uuid-67890",
        "redirectUrl": "https://sandbox.setu.co/consent/ui?handle=handle-12345",
    }
    mock_response = httpx.Response(
        200,
        json=mock_payload,
        request=httpx.Request("POST", "https://sandbox.setu.co/api/Consent"),
    )

    with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_response):
        user_id = uuid.uuid4()
        res = await client.create_consent_request(user_id=user_id, phone="9876543210")
        assert res["consent_id"] == "consent-uuid-67890"
        assert res["consent_handle"] == "handle-12345"
        assert res["redirect_url"] == "https://sandbox.setu.co/consent/ui?handle=handle-12345"

    await client.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2, 3, 4. Webhook HMAC Signature Tests
# ─────────────────────────────────────────────────────────────────────────────
async def test_webhook_hmac_valid(client, monkeypatch):
    """Test that a properly HMAC-signed webhook payload is accepted (200)."""
    secret = "test-webhook-secret-bank-sync-key"
    monkeypatch.setattr(get_settings(), "aa_webhook_secret", secret)

    payload = json.dumps({
        "type": "CONSENT_STATUS_UPDATE",
        "consentId": "consent-valid-123",
        "status": "ACTIVE",
    }).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    r = await client.post(
        "/api/webhooks/account-aggregator",
        content=payload,
        headers={"X-Webhook-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_webhook_hmac_invalid(client, monkeypatch):
    """Test that an invalid HMAC signature returns 401."""
    secret = "test-webhook-secret-bank-sync-key"
    monkeypatch.setattr(get_settings(), "aa_webhook_secret", secret)

    payload = json.dumps({
        "type": "CONSENT_STATUS_UPDATE",
        "consentId": "consent-valid-123",
        "status": "ACTIVE",
    }).encode("utf-8")

    r = await client.post(
        "/api/webhooks/account-aggregator",
        content=payload,
        headers={"X-Webhook-Signature": "invalid-hmac-digest-00000", "Content-Type": "application/json"},
    )
    assert r.status_code == 401
    assert "Invalid or missing webhook signature" in r.json()["detail"]


async def test_webhook_missing_signature(client, monkeypatch):
    """Test that a missing signature returns 401."""
    secret = "test-webhook-secret-bank-sync-key"
    monkeypatch.setattr(get_settings(), "aa_webhook_secret", secret)

    payload = json.dumps({
        "type": "CONSENT_STATUS_UPDATE",
        "consentId": "consent-valid-123",
        "status": "ACTIVE",
    }).encode("utf-8")

    r = await client.post(
        "/api/webhooks/account-aggregator",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401
    assert "Invalid or missing webhook signature" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 5, 6. Connect Bank Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────
async def test_connect_bank_endpoint(alice):
    """Test POST /api/bank/connect returns consent_id and redirect_url (mock AA client)."""
    with patch(
        "backend.main.AAGatewayClient.create_consent_request",
        new_callable=AsyncMock,
        return_value={
            "consent_id": "consent-connect-test-123",
            "redirect_url": "https://sandbox.setu.co/consent/ui?handle=handle-123",
            "consent_handle": "handle-123",
        },
    ):
        r = await alice.client.post(
            "/api/bank/connect",
            headers=alice.h,
            json={"phone": "9876543210"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["consent_id"] == "consent-connect-test-123"
        assert data["redirect_url"] == "https://sandbox.setu.co/consent/ui?handle=handle-123"
        assert data["status"] == "PENDING"


async def test_connect_bank_invalid_phone(alice):
    """Test POST /api/bank/connect with invalid phone returns 422."""
    bad_phones = [
        "12345",              # Too short
        "abcdefghij",         # Non-digits
        "5987654321",         # Indian numbers start with 6-9
        "987654321000",       # Too long
        "+14155552671",       # International non-Indian
    ]
    for bad_phone in bad_phones:
        r = await alice.client.post(
            "/api/bank/connect",
            headers=alice.h,
            json={"phone": bad_phone},
        )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 7, 8. List & Isolation (BOLA) Tests
# ─────────────────────────────────────────────────────────────────────────────
async def test_list_bank_connections(alice):
    """Test GET /api/bank/connections returns user's connections."""
    unique_consent = f"consent-{uuid.uuid4().hex}"
    with patch(
        "backend.main.AAGatewayClient.create_consent_request",
        new_callable=AsyncMock,
        return_value={
            "consent_id": unique_consent,
            "redirect_url": "https://sandbox.setu.co/consent/ui",
            "consent_handle": "handle-list",
        },
    ):
        connect_res = await alice.client.post(
            "/api/bank/connect",
            headers=alice.h,
            json={"phone": "9876543210"},
        )
        assert connect_res.status_code == 200

    r = await alice.client.get("/api/bank/connections", headers=alice.h)
    assert r.status_code == 200
    connections = r.json()
    assert isinstance(connections, list)
    matching = [c for c in connections if c["consent_id"] == unique_consent]
    assert len(matching) == 1
    assert matching[0]["fip_id"] == "SETU-FIP-MOCK"
    assert matching[0]["status"] == "PENDING"


async def test_bank_connection_isolation(alice, bob):
    """Test that user A cannot see user B's bank connections (BOLA test)."""
    alice_consent = f"consent-alice-{uuid.uuid4().hex}"
    with patch(
        "backend.main.AAGatewayClient.create_consent_request",
        new_callable=AsyncMock,
        return_value={
            "consent_id": alice_consent,
            "redirect_url": "https://sandbox.setu.co/consent/alice",
            "consent_handle": "handle-alice",
        },
    ):
        r = await alice.client.post(
            "/api/bank/connect",
            headers=alice.h,
            json={"phone": "9876543210"},
        )
        assert r.status_code == 200

    # Bob fetches bank connections; Alice's consent must not be present
    bob_conns = (await bob.client.get("/api/bank/connections", headers=bob.h)).json()
    assert all(c["consent_id"] != alice_consent for c in bob_conns)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Narration Sanitization
# ─────────────────────────────────────────────────────────────────────────────
def test_narration_sanitization():
    """Test that sanitize_narration strips PII: Aadhaar, PAN, Account numbers, Card numbers."""
    # Aadhaar numbers
    narration_aadhaar = "Transfer via Aadhaar 1234 5678 9012 auth confirmed"
    sanitized_aadhaar = sanitize_narration(narration_aadhaar)
    assert "1234 5678 9012" not in sanitized_aadhaar
    assert "XXXX-XXXX-XXXX" in sanitized_aadhaar

    # PAN
    narration_pan = "Interest credit subject to TDS under PAN ABCDE1234F"
    sanitized_pan = sanitize_narration(narration_pan)
    assert "ABCDE1234F" not in sanitized_pan
    assert "[PAN_MASKED]" in sanitized_pan

    # Full account numbers
    narration_acc = "NEFT transfer credited to A/C 98765432109876 ref 101"
    sanitized_acc = sanitize_narration(narration_acc)
    assert "98765432109876" not in sanitized_acc

    # Card numbers: show last 4 only
    narration_card = "POS purchase swipe with card 4111 2222 3333 4444 approved"
    sanitized_card = sanitize_narration(narration_card)
    assert "4111 2222 3333" not in sanitized_card
    assert "XXXX-XXXX-XXXX-4444" in sanitized_card


# ─────────────────────────────────────────────────────────────────────────────
# 10, 11. Deduplication Hash Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_dedup_hash_consistency():
    """Test that compute_dedup_hash produces consistent hashes."""
    uid = uuid.uuid4()
    ref = "BANK-TXN-REF-1001"
    amount = Decimal("850.50")
    timestamp = "2026-10-11T12:30:00Z"

    hash_a = compute_dedup_hash(uid, ref, amount, timestamp)
    hash_b = compute_dedup_hash(uid, ref, amount, timestamp)
    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256 hex length


def test_dedup_hash_uniqueness():
    """Test that different inputs produce different hashes."""
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    ref = "BANK-TXN-REF-1001"
    amount = Decimal("850.50")
    timestamp = "2026-10-11T12:30:00Z"

    base_hash = compute_dedup_hash(uid1, ref, amount, timestamp)

    # Different user
    assert compute_dedup_hash(uid2, ref, amount, timestamp) != base_hash
    # Different bank reference
    assert compute_dedup_hash(uid1, "BANK-TXN-REF-1002", amount, timestamp) != base_hash
    # Different amount
    assert compute_dedup_hash(uid1, ref, Decimal("850.51"), timestamp) != base_hash
    # Different timestamp
    assert compute_dedup_hash(uid1, ref, amount, "2026-10-11T12:30:01Z") != base_hash


# ─────────────────────────────────────────────────────────────────────────────
# 12. Transaction Classification
# ─────────────────────────────────────────────────────────────────────────────
def test_transaction_classification():
    """Test classify_transaction_type: DEBIT->expense, CREDIT->income."""
    # Debits map to expense
    assert classify_transaction_type("DEBIT") == "expense"
    assert classify_transaction_type("debit") == "expense"
    assert classify_transaction_type("DR") == "expense"
    assert classify_transaction_type("dr") == "expense"
    assert classify_transaction_type("EXPENSE") == "expense"
    assert classify_transaction_type("DEBITED") == "expense"

    # Credits map to income
    assert classify_transaction_type("CREDIT") == "income"
    assert classify_transaction_type("credit") == "income"
    assert classify_transaction_type("CR") == "income"
    assert classify_transaction_type("cr") == "income"
    assert classify_transaction_type("INCOME") == "income"
    assert classify_transaction_type("CREDITED") == "income"


# ─────────────────────────────────────────────────────────────────────────────
# 13. Merchant Extraction
# ─────────────────────────────────────────────────────────────────────────────
def test_merchant_extraction():
    """Test extract_merchant_name with UPI, NEFT, IMPS patterns."""
    # UPI pattern with slash-delimited merchant
    upi_sample = "UPI/DR/123456789012/SWIGGY/HDFC/order-payment"
    assert extract_merchant_name(upi_sample) == "Swiggy"

    # UPI pattern with VPA format
    upi_vpa = "UPI/UBER INDIA/uber@icici/0123456789"
    assert extract_merchant_name(upi_vpa) == "Uber India"

    # NEFT pattern
    neft_sample = "NEFT-CR-HDFC0001234-AMAZON PAY-N12345678901"
    merchant_neft = extract_merchant_name(neft_sample)
    assert merchant_neft is not None
    assert "Amazon" in merchant_neft

    # IMPS pattern
    imps_sample = "IMPS/123456789012/FLIPKART/ORDER987"
    assert extract_merchant_name(imps_sample) == "Flipkart"
