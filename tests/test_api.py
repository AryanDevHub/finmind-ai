"""
tests/test_api.py — FinMind AI test suite
Run with:  python -m pytest tests/ -v
"""

import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# ── Make sure project root is on the path ────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Build mocks BEFORE importing main ────────────────────────────
# We mock three things:
#   1. gdown.download  — so CI doesn't try to hit Google Drive
#   2. joblib.load     — returns a fake sklearn model
#   3. json.load       — returns our fake feature list
#      (do NOT mock builtins.open — it breaks pandas timezone loading)

mock_model = MagicMock()
mock_model.predict_proba.return_value = [[0.85, 0.15]]   # 15% fraud → LOW by default

FAKE_FEATURES = ["TransactionAmt", "card1", "D1"]

with patch("gdown.download", return_value=None), \
     patch("joblib.load", return_value=mock_model), \
     patch("json.load", return_value=FAKE_FEATURES):
    from backend.main import app

from fastapi.testclient import TestClient

client  = TestClient(app)
USER_ID = 1


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _add_tx(
    description: str  = "Test transaction",
    amount:      float = 500.0,
    category:    str  = "Food",
    tx_type:     str  = "expense",
):
    """Helper to POST a transaction and return the response."""
    return client.post("/transaction/add", json={
        "user_id":          USER_ID,
        "description":      description,
        "amount":           amount,
        "category":         category,
        "transaction_type": tx_type,
    })


def _set_budget(category: str = "Food", limit: float = 6000.0):
    """Helper to POST a budget and return the response."""
    return client.post("/budget/set", json={
        "user_id":      USER_ID,
        "category":     category,
        "limit_amount": limit,
        "month":        datetime.now().strftime("%Y-%m"),
    })


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────

def test_health():
    """Backend should return status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root():
    """Root endpoint should return a healthy message."""
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()


def test_add_income_no_fraud_scoring():
    """Income transactions should never be fraud-scored."""
    r = _add_tx(
        description="Monthly Salary",
        amount=55000,
        category="Salary",
        tx_type="income",
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_flagged"]  == False
    assert data["risk_level"]  == "LOW"
    assert data["fraud_score"] == 0.0   # income is never scored


def test_add_expense_low_risk():
    """Expense with low fraud probability → LOW risk, not flagged."""
    mock_model.predict_proba.return_value = [[0.92, 0.08]]   # 8% fraud
    r = _add_tx(description="Swiggy Order", amount=450, category="Food")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "LOW"
    assert data["is_flagged"] == False
    assert data["fraud_score"] == pytest.approx(8.0, abs=1)


def test_add_expense_medium_risk():
    """Expense with medium fraud probability → MEDIUM risk, not flagged."""
    mock_model.predict_proba.return_value = [[0.58, 0.42]]   # 42% fraud
    r = _add_tx(description="Amazon Order", amount=3200, category="Shopping")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "MEDIUM"
    assert data["is_flagged"] == False


def test_add_expense_high_risk():
    """Expense with high fraud probability → HIGH risk, flagged."""
    mock_model.predict_proba.return_value = [[0.32, 0.68]]   # 68% fraud
    r = _add_tx(description="Unknown Transfer", amount=8999, category="Other")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "HIGH"
    assert data["is_flagged"] == True


def test_add_expense_critical_fraud():
    """Expense with critical fraud probability → CRITICAL risk, flagged."""
    mock_model.predict_proba.return_value = [[0.05, 0.95]]   # 95% fraud
    r = _add_tx(
        description="Suspicious International Transfer",
        amount=15000,
        category="Shopping",
    )
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["is_flagged"] == True
    assert data["fraud_score"] > 80


def test_get_transactions_returns_list():
    """GET /transactions/{user_id} should return a list."""
    mock_model.predict_proba.return_value = [[0.9, 0.1]]
    _add_tx(description="Uber Ride", amount=120, category="Transport")
    r = client.get(f"/transactions/{USER_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_transactions_have_required_fields():
    """Each transaction should have the expected fields."""
    r = client.get(f"/transactions/{USER_ID}")
    assert r.status_code == 200
    txs = r.json()
    if txs:
        tx = txs[0]
        for field in ["id", "description", "amount", "category",
                      "transaction_type", "fraud_score", "risk_level", "is_flagged"]:
            assert field in tx, f"Missing field: {field}"


def test_budget_set():
    """POST /budget/set should save a budget successfully."""
    r = _set_budget(category="Food", limit=6000.0)
    assert r.status_code == 200
    assert "saved" in r.json()["message"].lower()


def test_budget_get():
    """GET /budgets/{user_id} should return the budget we just set."""
    _set_budget(category="Transport", limit=2000.0)
    r = client.get(f"/budgets/{USER_ID}")
    assert r.status_code == 200
    budgets = r.json()
    assert isinstance(budgets, list)
    cats = [b["category"] for b in budgets]
    assert "Transport" in cats


def test_budget_limit_amount():
    """Budget limit_amount should match what we set."""
    _set_budget(category="Entertainment", limit=1500.0)
    r = client.get(f"/budgets/{USER_ID}")
    budgets = r.json()
    match = next((b for b in budgets if b["category"] == "Entertainment"), None)
    assert match is not None
    assert match["limit_amount"] == 1500.0


def test_budget_update():
    """Setting a budget twice should update the limit, not duplicate it."""
    _set_budget(category="Health", limit=2000.0)
    _set_budget(category="Health", limit=3000.0)   # update
    r = client.get(f"/budgets/{USER_ID}")
    health_budgets = [b for b in r.json() if b["category"] == "Health"]
    assert len(health_budgets) == 1
    assert health_budgets[0]["limit_amount"] == 3000.0


def test_anomaly_detection_endpoint_exists():
    """GET /anomaly/{user_id} should return 200 with the right shape."""
    mock_model.predict_proba.return_value = [[0.9, 0.1]]
    # Add enough transactions for Isolation Forest (needs >= 5)
    for amt in [200, 300, 250, 180, 220, 210, 15000]:
        _add_tx(amount=amt, category="Food")

    r = client.get(f"/anomaly/{USER_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "anomaly_count" in data
    assert "anomalies"     in data
    assert isinstance(data["anomalies"], list)


def test_anomaly_fields():
    """Each anomaly should have description, amount, category."""
    r = client.get(f"/anomaly/{USER_ID}")
    data = r.json()
    for anomaly in data["anomalies"]:
        assert "description"    in anomaly
        assert "amount"         in anomaly
        assert "category"       in anomaly
        assert "anomaly_score"  in anomaly


def test_forecast_endpoint_exists():
    """GET /forecast/{user_id} should return 200 with forecast list."""
    r = client.get(f"/forecast/{USER_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "forecast" in data


def test_forecast_shape():
    """Each forecast entry should have month and total fields."""
    r = client.get(f"/forecast/{USER_ID}")
    data = r.json()
    if data["forecast"]:
        entry = data["forecast"][0]
        assert "month" in entry
        assert "total" in entry