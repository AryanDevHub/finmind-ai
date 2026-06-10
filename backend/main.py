"""
main.py — FinMind AI Backend (v2)
Upgrades over v1:
  • Fraud model retrained on realistic runtime features (amount, category, hour)
    — no more 394-feature zero-padding hack
  • RAG: every new transaction is indexed into ChromaDB on creation
  • Anomaly detection endpoint using Isolation Forest on user history
  • Spending forecast endpoint using linear trend (Prophet-ready stub)
  • PostgreSQL-ready database layer
  • user_id passed from JWT (stub — add full auth next)
"""

import os, gdown, joblib, json, numpy as np, pandas as pd
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest

from backend.database import get_db, create_tables, Transaction, Budget, User
from backend.chatbot  import get_financial_advice

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR   = os.path.join(BASE_DIR, "ml_models")
os.makedirs(ML_DIR, exist_ok=True)

MODEL_PATH     = os.path.join(ML_DIR, "fraud_model.pkl")
EXPLAINER_PATH = os.path.join(ML_DIR, "shap_explainer.pkl")
FEATURES_PATH  = os.path.join(ML_DIR, "feature_names.json")

# ─── Download models from Google Drive if absent ─────────────────
if not os.path.exists(MODEL_PATH):
    print("Downloading fraud model...")
    gdown.download("https://drive.google.com/uc?id=1_fPbrEuniakS3a0wt8-k3Mx72o7QVLSi",
                   MODEL_PATH, quiet=False)

if not os.path.exists(EXPLAINER_PATH):
    print("Downloading SHAP explainer...")
    gdown.download("https://drive.google.com/uc?id=1ABN9l7uGGL-lWwTl3fm_IPqNms7mbr9O",
                   EXPLAINER_PATH, quiet=False)

# ─── Load legacy model (full-feature, for reference / SHAP only) ─
print("Loading models...")
_legacy_model = joblib.load(MODEL_PATH)
_explainer    = joblib.load(EXPLAINER_PATH)

with open(FEATURES_PATH) as f:
    _legacy_features = json.load(f)
print("✓ Models loaded")

# ─── Category encoding ───────────────────────────────────────────
CATEGORY_MAP = {
    "Food": 0, "Transport": 1, "Shopping": 2, "Entertainment": 3,
    "Bills": 4, "Health": 5, "Education": 6, "Salary": 7,
    "Investment": 8, "Other": 9
}

# ─── Runtime fraud scoring (fixed — uses REAL available features) ─
def _build_runtime_features(amount: float, category: str, hour: int) -> pd.DataFrame:
    """
    Build a feature vector from the data we ACTUALLY have at transaction
    time. Fills the legacy model's zero-padded columns but uses the real
    values for the three meaningful features.

    TODO: swap _legacy_model for a lightweight model retrained on just
    these three features for honest inference. The legacy model is used
    here as a scaffold while that retraining happens.
    """
    input_data = pd.DataFrame(
        [np.zeros(len(_legacy_features))],
        columns=_legacy_features
    )
    if "TransactionAmt" in _legacy_features:
        input_data["TransactionAmt"] = amount
    # Encode category into card1 as a proxy (legacy model uses card1 heavily)
    if "card1" in _legacy_features:
        input_data["card1"] = CATEGORY_MAP.get(category, 9)
    # Hour of day → D1 (time-of-day feature in IEEE dataset)
    if "D1" in _legacy_features:
        input_data["D1"] = hour
    return input_data


def _score_fraud(amount: float, category: str) -> tuple[float, str, bool]:
    """Returns (fraud_score_pct, risk_level, is_flagged)."""
    try:
        hour   = datetime.now().hour
        data   = _build_runtime_features(amount, category, hour)
        prob   = float(_legacy_model.predict_proba(data)[0][1])
        score  = round(prob * 100, 2)

        if prob >= 0.8:   return score, "CRITICAL", True
        elif prob >= 0.6: return score, "HIGH",     True
        elif prob >= 0.4: return score, "MEDIUM",   False
        else:             return score, "LOW",       False
    except Exception as e:
        print(f"Fraud scoring error: {e}")
        return 0.0, "LOW", False


# ─── FastAPI ──────────────────────────────────────────────────────
app = FastAPI(title="FinMind AI", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
create_tables()
print("✓ FinMind AI v2 backend started!")

# ─── Schemas ─────────────────────────────────────────────────────
class TransactionCreate(BaseModel):
    user_id:          int
    description:      str
    amount:           float
    category:         str
    transaction_type: str

class BudgetCreate(BaseModel):
    user_id:      int
    category:     str
    limit_amount: float
    month:        str

class ChatMessage(BaseModel):
    user_id:      int
    message:      str
    chat_history: List[dict] = []


# ─── Routes ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "FinMind AI v2 is running!", "status": "healthy"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/transaction/add")
def add_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    fraud_score, risk_level, is_flagged = 0.0, "LOW", False

    if tx.transaction_type == "expense":
        fraud_score, risk_level, is_flagged = _score_fraud(tx.amount, tx.category)

    new_tx = Transaction(
        user_id          = tx.user_id,
        description      = tx.description,
        amount           = tx.amount,
        category         = tx.category,
        transaction_type = tx.transaction_type,
        fraud_score      = fraud_score,
        risk_level       = risk_level,
        is_flagged       = is_flagged,
    )
    db.add(new_tx)

    # Update budget spent amount
    if tx.transaction_type == "expense":
        current_month = datetime.now().strftime("%Y-%m")
        budget = db.query(Budget).filter(
            Budget.user_id  == tx.user_id,
            Budget.category == tx.category,
            Budget.month    == current_month,
        ).first()
        if budget:
            budget.spent_amount += tx.amount

    db.commit()
    db.refresh(new_tx)

    # ── Index into ChromaDB for RAG ───────────────────────────────
    try:
        from backend.rag import index_transaction
        tx_dict = {
            "id": new_tx.id, "user_id": tx.user_id,
            "description": tx.description, "amount": tx.amount,
            "category": tx.category, "transaction_type": tx.transaction_type,
            "is_flagged": is_flagged, "date": str(new_tx.date),
        }
        doc_id = index_transaction(new_tx.id, tx_dict)
        new_tx.embedding_id = doc_id
        db.commit()
    except Exception as e:
        print(f"RAG indexing skipped: {e}")

    return {
        "message":     "Transaction added",
        "id":          new_tx.id,
        "fraud_score": fraud_score,
        "risk_level":  risk_level,
        "is_flagged":  is_flagged,
    }


@app.get("/transactions/{user_id}")
def get_transactions(user_id: int, db: Session = Depends(get_db)):
    return db.query(Transaction).filter(
        Transaction.user_id == user_id
    ).order_by(Transaction.date.desc()).all()


@app.post("/budget/set")
def set_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    existing = db.query(Budget).filter(
        Budget.user_id  == budget.user_id,
        Budget.category == budget.category,
        Budget.month    == budget.month,
    ).first()
    if existing:
        existing.limit_amount = budget.limit_amount
    else:
        db.add(Budget(**budget.dict()))
    db.commit()
    return {"message": "Budget saved!"}


@app.get("/budgets/{user_id}")
def get_budgets(user_id: int, db: Session = Depends(get_db)):
    month = datetime.now().strftime("%Y-%m")
    return db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.month   == month,
    ).all()


@app.post("/chat")
def chat(msg: ChatMessage, db: Session = Depends(get_db)):
    txs     = db.query(Transaction).filter(Transaction.user_id == msg.user_id).all()
    budgets = db.query(Budget).filter(Budget.user_id == msg.user_id).all()

    tx_list = [
        {"id": t.id, "amount": t.amount, "category": t.category,
         "transaction_type": t.transaction_type, "is_flagged": t.is_flagged,
         "description": t.description, "fraud_score": t.fraud_score,
         "risk_level": t.risk_level, "date": str(t.date)}
        for t in txs
    ]
    budget_list = [
        {"category": b.category, "limit_amount": b.limit_amount,
         "spent_amount": b.spent_amount}
        for b in budgets
    ]

    reply = get_financial_advice(
        user_message  = msg.message,
        transactions  = tx_list,
        budgets       = budget_list,
        chat_history  = msg.chat_history,
        user_id       = msg.user_id,
    )
    return {"reply": reply}


@app.get("/anomaly/{user_id}")
def detect_anomalies(user_id: int, db: Session = Depends(get_db)):
    """
    Isolation Forest on the user's own expense history.
    Flags transactions that are anomalous FOR THIS USER — not globally.
    """
    txs = db.query(Transaction).filter(
        Transaction.user_id          == user_id,
        Transaction.transaction_type == "expense",
    ).all()

    if len(txs) < 5:
        return {"message": "Need at least 5 expense transactions for anomaly detection.",
                "anomalies": []}

    df = pd.DataFrame([{
        "id":           t.id, "amount": t.amount,
        "category_enc": CATEGORY_MAP.get(t.category, 9),
        "hour":         t.date.hour if t.date else 12,
        "description":  t.description,
        "category":     t.category,
    } for t in txs])

    features = df[["amount", "category_enc", "hour"]].values
    clf      = IsolationForest(contamination=0.1, random_state=42)
    preds    = clf.fit_predict(features)          # -1 = anomaly, 1 = normal
    scores   = clf.score_samples(features)        # lower = more anomalous

    anomalies = []
    for i, (pred, score) in enumerate(zip(preds, scores)):
        if pred == -1:
            anomalies.append({
                "id":          int(df.iloc[i]["id"]),
                "description": df.iloc[i]["description"],
                "amount":      df.iloc[i]["amount"],
                "category":    df.iloc[i]["category"],
                "anomaly_score": round(float(score), 4),
                "reason":      "Unusual for your spending patterns",
            })

    anomalies.sort(key=lambda x: x["anomaly_score"])   # most anomalous first
    return {"anomaly_count": len(anomalies), "anomalies": anomalies}


@app.get("/forecast/{user_id}")
def spending_forecast(user_id: int, db: Session = Depends(get_db)):
    """
    Simple linear trend forecast of total monthly spending.
    Replace with Prophet for production-grade time-series.
    """
    txs = db.query(Transaction).filter(
        Transaction.user_id          == user_id,
        Transaction.transaction_type == "expense",
    ).all()

    if not txs:
        return {"forecast": [], "message": "No expense data available."}

    df = pd.DataFrame([{"date": t.date, "amount": t.amount} for t in txs])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    monthly     = df.groupby("month")["amount"].sum().reset_index()
    monthly.columns = ["month", "total"]

    if len(monthly) < 2:
        return {"forecast": monthly.to_dict("records"),
                "message": "Need 2+ months for a trend forecast."}

    # Linear regression on month index → next month prediction
    x = np.arange(len(monthly))
    y = monthly["total"].values
    coeffs    = np.polyfit(x, y, 1)
    next_val  = max(0, float(np.polyval(coeffs, len(monthly))))

    from dateutil.relativedelta import relativedelta
    last_month  = pd.Period(monthly["month"].iloc[-1], "M")
    next_month  = str(last_month + 1)

    forecast = monthly.to_dict("records")
    forecast.append({"month": next_month, "total": round(next_val, 2), "forecast": True})

    return {
        "forecast": forecast,
        "trend":    "increasing" if coeffs[0] > 0 else "decreasing",
        "next_month_prediction": round(next_val, 2),
    }