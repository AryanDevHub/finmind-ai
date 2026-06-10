"""
tests/test_api.py — FinMind AI test suite
Run with:  pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Mock heavy dependencies before importing main ─────────────────
import joblib, json
from unittest.mock import MagicMock

# Mock the model download + load so tests don't need Google Drive
mock_model = MagicMock()
mock_model.predict_proba.return_value = [[0.85, 0.15]]   # LOW fraud by default

mock_explainer = MagicMock()

with patch("gdown.download"), \
     patch("joblib.load", return_value=mock_model), \
     patch("builtins.open", side_effect=lambda f, *a, **k:
           __import__("io").StringIO(
               json.dumps(["TransactionAmt","card1","D1"])
           ) if "feature_names" in str(f) else open(f, *a, **k)):
    from backend.main import app

client = TestClient(app)
USER_ID = 1


# ── Helpers ───────────────────────────────────────────────────────
def _add_tx(description="Test", amount=500.0, category="Food",
             tx_type="expense"):
    return client.post("/transaction/add", json={
        "user_id":          USER_ID,
        "description":      description,
        "amount":           amount,
        "category":         category,
        "transaction_type": tx_type,
    })


# ── 1. Health check ───────────────────────────────────────────────
def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── 2. Add income transaction (no fraud scoring) ──────────────────
def test_add_income():
    r = _add_tx(description="Salary", amount=55000, category="Salary",
                tx_type="income")
    assert r.status_code == 200
    data = r.json()
    assert data["is_flagged"]  == False
    assert data["risk_level"]  == "LOW"
    assert data["fraud_score"] == 0.0


# ── 3. Low-risk expense ───────────────────────────────────────────
def test_add_expense_low_risk():
    mock_model.predict_proba.return_value = [[0.92, 0.08]]   # 8% → LOW
    r = _add_tx(amount=450, category="Food")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"]  == "LOW"
    assert data["is_flagged"]  == False
    assert data["fraud_score"] == pytest.approx(8.0, abs=1)


# ── 4. Critical fraud transaction ────────────────────────────────
def test_add_expense_critical_fraud():
    mock_model.predict_proba.return_value = [[0.05, 0.95]]   # 95% → CRITICAL
    r = _add_tx(description="Suspicious Transfer", amount=15000,
                category="Shopping")
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["is_flagged"] == True
    assert data["fraud_score"] > 60


# ── 5. Get transactions ───────────────────────────────────────────
def test_get_transactions():
    _add_tx(amount=100, category="Transport")
    r = client.get(f"/transactions/{USER_ID}")
    assert r.status_code == 200
    txs = r.json()
    assert isinstance(txs, list)
    assert len(txs) >= 1


# ── 6. Set and get budget ─────────────────────────────────────────
def test_budget_crud():
    from datetime import datetime
    month = datetime.now().strftime("%Y-%m")

    # Set budget
    r = client.post("/budget/set", json={
        "user_id":      USER_ID,
        "category":     "Food",
        "limit_amount": 6000.0,
        "month":        month,
    })
    assert r.status_code == 200
    assert "saved" in r.json()["message"].lower()

    # Get budget
    r2 = client.get(f"/budgets/{USER_ID}")
    assert r2.status_code == 200
    budgets = r2.json()
    food_budget = next((b for b in budgets if b["category"] == "Food"), None)
    assert food_budget is not None
    assert food_budget["limit_amount"] == 6000.0


# ── 7. Anomaly detection endpoint ────────────────────────────────
def test_anomaly_detection():
    # Add diverse transactions so Isolation Forest has enough data
    amounts = [200, 250, 300, 180, 15000]   # 15k is the outlier
    for amt in amounts:
        mock_model.predict_proba.return_value = [[0.9, 0.1]]
        _add_tx(amount=amt, category="Food")

    r = client.get(f"/anomaly/{USER_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "anomaly_count" in data
    assert "anomalies" in data


# ── 8. Forecast endpoint returns expected shape ───────────────────
def test_spending_forecast():
    r = client.get(f"/forecast/{USER_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "forecast" in data
    if data["forecast"]:
        assert "month" in data["forecast"][0]
        assert "total" in data["forecast"][0]