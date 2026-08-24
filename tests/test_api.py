

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

# ── Make sure project root is on the path ────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Build mocks BEFORE importing main ────────────────────────────
mock_model = MagicMock()
mock_model.predict_proba.return_value = [[0.85, 0.15]]   # 15% fraud → LOW by default

FAKE_FEATURES = ["amount", "category_enc", "hour", "day_of_week"]

with patch("joblib.load", return_value=mock_model), \
     patch("json.load", return_value=FAKE_FEATURES):
    from backend.main import app

from fastapi.testclient import TestClient

client = TestClient(app)

TEST_USERNAME = "testuser"
TEST_EMAIL = "testuser@example.com"
TEST_PASSWORD = "supersecret123"


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_headers():
    """
    Registers (or reuses, if already registered) a test user, logs in,
    and returns the Authorization header dict to attach to every
    protected request in this suite.
    """
    client.post("/register", json={
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    # Registration may 400 on repeated test runs against a persisted
    # DB — that's fine, we just need a valid login either way.
    r = client.post("/login", data={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, f"Login failed in fixture: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def user_id(auth_headers):
    r = client.get("/me", headers=auth_headers)
    assert r.status_code == 200
    return r.json()["id"]


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _add_tx(
    headers: dict,
    description: str = "Test transaction",
    amount: float = 500.0,
    category: str = "Food",
    tx_type: str = "expense",
):
    return client.post("/transaction/add", json={
        "description": description,
        "amount": amount,
        "category": category,
        "transaction_type": tx_type,
    }, headers=headers)


def _set_budget(headers: dict, category: str = "Food", limit: float = 6000.0):
    return client.post("/budget/set", json={
        "category": category,
        "limit_amount": limit,
        "month": datetime.now().strftime("%Y-%m"),
    }, headers=headers)


# ─────────────────────────────────────────────────────────────────
# Health / unprotected routes
# ─────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()


# ─────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────

def test_register_new_user():
    r = client.post("/register", json={
        "username": "brandnewuser",
        "email": "brandnewuser@example.com",
        "password": "anothersecret123",
    })
    assert r.status_code in (200, 201, 400)  # 400 if re-run against persisted DB
    if r.status_code in (200, 201):
        data = r.json()
        assert data["username"] == "brandnewuser"
        assert "id" in data
        assert "hashed_password" not in data  # never leak the hash


def test_register_duplicate_username_rejected():
    client.post("/register", json={
        "username": "dupeuser", "email": "dupe1@example.com", "password": "password123",
    })
    r = client.post("/register", json={
        "username": "dupeuser", "email": "dupe2@example.com", "password": "password123",
    })
    assert r.status_code == 400


def test_login_success(auth_headers):
    # If the fixture built headers without raising, login succeeded.
    assert "Authorization" in auth_headers


def test_login_wrong_password():
    r = client.post("/login", data={"username": TEST_USERNAME, "password": "wrongpassword"})
    assert r.status_code == 401


def test_login_nonexistent_user():
    r = client.post("/login", data={"username": "nobody_here", "password": "whatever"})
    assert r.status_code == 401


def test_protected_route_requires_token():
    """Hitting a protected route with no Authorization header should 401."""
    r = client.post("/transaction/add", json={
        "description": "No auth", "amount": 100, "category": "Food", "transaction_type": "expense",
    })
    assert r.status_code == 401


def test_me_returns_current_user(auth_headers):
    r = client.get("/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == TEST_USERNAME


# ─────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────

def test_add_income_no_fraud_scoring(auth_headers):
    r = _add_tx(auth_headers, description="Monthly Salary", amount=55000,
                category="Salary", tx_type="income")
    assert r.status_code == 200
    data = r.json()
    assert data["is_flagged"] == False
    assert data["risk_level"] == "LOW"
    assert data["fraud_score"] == 0.0


def test_add_expense_low_risk(auth_headers):
    mock_model.predict_proba.return_value = [[0.92, 0.08]]
    r = _add_tx(auth_headers, description="Swiggy Order", amount=450, category="Food")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "LOW"
    assert data["is_flagged"] == False
    assert data["fraud_score"] == pytest.approx(8.0, abs=1)


def test_add_expense_medium_risk(auth_headers):
    mock_model.predict_proba.return_value = [[0.58, 0.42]]
    r = _add_tx(auth_headers, description="Amazon Order", amount=3200, category="Shopping")
    assert r.status_code == 200
    assert r.json()["risk_level"] == "MEDIUM"


def test_add_expense_high_risk(auth_headers):
    mock_model.predict_proba.return_value = [[0.32, 0.68]]
    r = _add_tx(auth_headers, description="Unknown Transfer", amount=8999, category="Other")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "HIGH"
    assert data["is_flagged"] == True


def test_add_expense_critical_fraud(auth_headers):
    mock_model.predict_proba.return_value = [[0.05, 0.95]]
    r = _add_tx(auth_headers, description="Suspicious International Transfer",
                amount=15000, category="Shopping")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["is_flagged"] == True
    assert data["fraud_score"] > 80


def test_add_expense_invalid_category_rejected(auth_headers):
    r = _add_tx(auth_headers, description="Bad category", amount=100, category="NotACategory")
    assert r.status_code == 422


def test_add_expense_negative_amount_rejected(auth_headers):
    r = _add_tx(auth_headers, description="Negative", amount=-50, category="Food")
    assert r.status_code == 422


def test_get_transactions_returns_list(auth_headers, user_id):
    mock_model.predict_proba.return_value = [[0.9, 0.1]]
    _add_tx(auth_headers, description="Uber Ride", amount=120, category="Transport")
    r = client.get(f"/transactions/{user_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_transactions_have_required_fields(auth_headers, user_id):
    r = client.get(f"/transactions/{user_id}", headers=auth_headers)
    txs = r.json()
    if txs:
        tx = txs[0]
        for field in ["id", "description", "amount", "category",
                      "transaction_type", "fraud_score", "risk_level", "is_flagged"]:
            assert field in tx, f"Missing field: {field}"


def test_get_transactions_requires_auth(user_id):
    r = client.get(f"/transactions/{user_id}")
    assert r.status_code == 401


def test_cannot_read_another_users_transactions(auth_headers, user_id):
    """A valid token for user A must not be able to read user B's data."""
    other_id = user_id + 999
    r = client.get(f"/transactions/{other_id}", headers=auth_headers)
    assert r.status_code == 403


def test_delete_transaction(auth_headers):
    add_r = _add_tx(auth_headers, description="To be deleted", amount=99, category="Food")
    tx_id = add_r.json()["id"]
    del_r = client.delete(f"/transaction/{tx_id}", headers=auth_headers)
    assert del_r.status_code == 200


# ─────────────────────────────────────────────────────────────────
# Budgets
# ─────────────────────────────────────────────────────────────────

def test_budget_set(auth_headers):
    r = _set_budget(auth_headers, category="Food", limit=6000.0)
    assert r.status_code == 200
    assert "saved" in r.json()["message"].lower()


def test_budget_get(auth_headers, user_id):
    _set_budget(auth_headers, category="Transport", limit=2000.0)
    r = client.get(f"/budgets/{user_id}", headers=auth_headers)
    assert r.status_code == 200
    budgets = r.json()
    cats = [b["category"] for b in budgets]
    assert "Transport" in cats


def test_budget_limit_amount(auth_headers, user_id):
    _set_budget(auth_headers, category="Entertainment", limit=1500.0)
    r = client.get(f"/budgets/{user_id}", headers=auth_headers)
    match = next((b for b in r.json() if b["category"] == "Entertainment"), None)
    assert match is not None
    assert match["limit_amount"] == 1500.0


def test_budget_update(auth_headers, user_id):
    _set_budget(auth_headers, category="Health", limit=2000.0)
    _set_budget(auth_headers, category="Health", limit=3000.0)
    r = client.get(f"/budgets/{user_id}", headers=auth_headers)
    health_budgets = [b for b in r.json() if b["category"] == "Health"]
    assert len(health_budgets) == 1
    assert health_budgets[0]["limit_amount"] == 3000.0


def test_budget_invalid_category_rejected(auth_headers):
    r = _set_budget(auth_headers, category="NotACategory", limit=1000.0)
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────
# Anomaly detection
# ─────────────────────────────────────────────────────────────────

def test_anomaly_detection_endpoint_exists(auth_headers, user_id):
    mock_model.predict_proba.return_value = [[0.9, 0.1]]
    for amt in [200, 300, 250, 180, 220, 210, 15000]:
        _add_tx(auth_headers, amount=amt, category="Food")

    r = client.get(f"/anomaly/{user_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "anomaly_count" in data
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


def test_anomaly_fields(auth_headers, user_id):
    r = client.get(f"/anomaly/{user_id}", headers=auth_headers)
    data = r.json()
    for anomaly in data["anomalies"]:
        assert "description" in anomaly
        assert "amount" in anomaly
        assert "category" in anomaly
        assert "anomaly_score" in anomaly


def test_anomaly_requires_ownership(auth_headers, user_id):
    r = client.get(f"/anomaly/{user_id + 999}", headers=auth_headers)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────
# Forecast
# ─────────────────────────────────────────────────────────────────

def test_forecast_endpoint_exists(auth_headers, user_id):
    r = client.get(f"/forecast/{user_id}", headers=auth_headers)
    assert r.status_code == 200
    assert "forecast" in r.json()


def test_forecast_shape(auth_headers, user_id):
    r = client.get(f"/forecast/{user_id}", headers=auth_headers)
    data = r.json()
    if data["forecast"]:
        entry = data["forecast"][0]
        assert "month" in entry
        assert "total" in entry


def test_forecast_requires_ownership(auth_headers, user_id):
    r = client.get(f"/forecast/{user_id + 999}", headers=auth_headers)
    assert r.status_code == 403