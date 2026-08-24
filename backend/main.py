"""
main.py — FinMind AI Backend (v2.1)

Changes in this version:
  • JWT authentication added — /register and /login issue tokens
  • Every data route now requires a valid Bearer token
  • user_id is derived from the authenticated user (never trusted
    from the request body) on write routes
  • Path-based read routes (e.g. /transactions/{user_id}) verify the
    token's user matches the requested user_id, or reject with 403

Everything else (fraud scoring, RAG indexing, anomaly detection,
forecasting) is unchanged from v2.
"""

import os, joblib, json, numpy as np, pandas as pd
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest

from backend.database import get_db, create_tables, Transaction, Budget, User
from backend.chatbot import get_financial_advice
from backend import auth

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(BASE_DIR, "ml_models")
os.makedirs(ML_DIR, exist_ok=True)

MODEL_PATH = os.path.join(ML_DIR, "fraud_model.pkl")
EXPLAINER_PATH = os.path.join(ML_DIR, "shap_explainer.pkl")
FEATURES_PATH = os.path.join(ML_DIR, "feature_names.json")

# ─── Load fraud model ──────────────────────────────────────────────
# v3: trained directly on the features actually available at runtime
# (amount, category, hour, day-of-week) — see ml_models/train_fraud_model.py
# for the training pipeline and ml_models/model_metrics.json for the
# honestly-measured test AUC. No more zero-padding a 394-feature model
# trained on data we don't have at inference time.
#
# If fraud_model.pkl / feature_names.json aren't present yet, run:
#     python ml_models/train_fraud_model.py
print("Loading fraud model...")
_model = joblib.load(MODEL_PATH)
_explainer = joblib.load(EXPLAINER_PATH) if os.path.exists(EXPLAINER_PATH) else None

with open(FEATURES_PATH) as f:
    _feature_names = json.load(f)  # expected: ["amount", "category_enc", "hour", "day_of_week"]
print(f"✓ Fraud model loaded (features: {_feature_names})")

# ─── Category encoding ───────────────────────────────────────────
CATEGORY_MAP = {
    "Food": 0, "Transport": 1, "Shopping": 2, "Entertainment": 3,
    "Bills": 4, "Health": 5, "Education": 6, "Salary": 7,
    "Investment": 8, "Other": 9
}


# ─── Runtime fraud scoring ────────────────────────────────────────
def _build_runtime_features(amount: float, category: str, hour: int, day_of_week: int) -> pd.DataFrame:
    """Builds the exact feature vector the model was trained on — no padding."""
    return pd.DataFrame([{
        "amount": amount,
        "category_enc": CATEGORY_MAP.get(category, 9),
        "hour": hour,
        "day_of_week": day_of_week,
    }])[_feature_names]


def _score_fraud(amount: float, category: str) -> tuple[float, str, bool]:
    """Returns (fraud_score_pct, risk_level, is_flagged)."""
    try:
        now = datetime.now()
        data = _build_runtime_features(amount, category, now.hour, now.weekday())
        prob = float(_model.predict_proba(data)[0][1])
        score = round(prob * 100, 2)

        if prob >= 0.8:
            return score, "CRITICAL", True
        elif prob >= 0.6:
            return score, "HIGH", True
        elif prob >= 0.4:
            return score, "MEDIUM", False
        else:
            return score, "LOW", False
    except Exception as e:
        print(f"Fraud scoring error: {e}")
        return 0.0, "LOW", False


# ─── FastAPI ──────────────────────────────────────────────────────
app = FastAPI(title="FinMind AI", version="2.1.0")

# NOTE: allow_origins=["*"] is fine for local/demo use but should be
# locked down to your actual frontend origin(s) before real deployment,
# especially now that routes are auth-protected with bearer tokens.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                    allow_methods=["*"], allow_headers=["*"])
create_tables()

# ── Pre-load the RAG embedding model now, not on the user's first chat
# message. sentence-transformers can take 10-30s to load/download on
# first use — doing it here means that cost happens once, at server
# startup, instead of surprising the first person to use the AI Advisor.
try:
    from backend import rag as _rag  # noqa: F401  (import triggers model load)
    print("✓ RAG embedding model pre-loaded")
except Exception as e:
    print(f"RAG pre-load skipped (chat will still work without semantic retrieval): {e}")

print("✓ FinMind AI v2.1 backend started!")


# ─── Schemas ─────────────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TransactionCreate(BaseModel):
    # user_id removed — always taken from the authenticated user,
    # never trusted from the client.
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    category: str
    transaction_type: str


class BudgetCreate(BaseModel):
    category: str
    limit_amount: float = Field(gt=0)
    month: str


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    chat_history: List[dict] = []


VALID_CATEGORIES = set(CATEGORY_MAP.keys())
VALID_TX_TYPES = {"income", "expense"}


# ─── Auth routes ──────────────────────────────────────────────────
@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already registered")
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm expects "username" and "password" fields
    # (standard OAuth2 password-flow field names) — we treat "username"
    # as either the username or email for convenience.
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()

    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(auth.get_current_user)):
    return current_user


# ─── Health routes (unprotected) ──────────────────────────────────
@app.get("/")
def root():
    return {"message": "FinMind AI v2.1 is running!", "status": "healthy"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}


# ─── Transaction routes (protected) ───────────────────────────────
@app.post("/transaction/add")
def add_transaction(
    tx: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    if tx.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Invalid category. Must be one of {sorted(VALID_CATEGORIES)}")
    if tx.transaction_type not in VALID_TX_TYPES:
        raise HTTPException(status_code=422, detail="transaction_type must be 'income' or 'expense'")

    fraud_score, risk_level, is_flagged = 0.0, "LOW", False

    if tx.transaction_type == "expense":
        fraud_score, risk_level, is_flagged = _score_fraud(tx.amount, tx.category)

    new_tx = Transaction(
        user_id=current_user.id,
        description=tx.description,
        amount=tx.amount,
        category=tx.category,
        transaction_type=tx.transaction_type,
        fraud_score=fraud_score,
        risk_level=risk_level,
        is_flagged=is_flagged,
    )
    db.add(new_tx)

    if tx.transaction_type == "expense":
        current_month = datetime.now().strftime("%Y-%m")
        budget = db.query(Budget).filter(
            Budget.user_id == current_user.id,
            Budget.category == tx.category,
            Budget.month == current_month,
        ).first()
        if budget:
            budget.spent_amount += tx.amount

    db.commit()
    db.refresh(new_tx)

    # ── Index into ChromaDB for RAG ───────────────────────────────
    try:
        from backend.rag import index_transaction
        tx_dict = {
            "id": new_tx.id, "user_id": current_user.id,
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
        "message": "Transaction added",
        "id": new_tx.id,
        "fraud_score": fraud_score,
        "risk_level": risk_level,
        "is_flagged": is_flagged,
    }


@app.get("/transactions/{user_id}")
def get_transactions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.require_same_user(user_id, current_user)
    return db.query(Transaction).filter(
        Transaction.user_id == user_id
    ).order_by(Transaction.date.desc()).all()


@app.delete("/transaction/{tx_id}")
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    auth.require_same_user(tx.user_id, current_user)

    if tx.transaction_type == "expense":
        current_month = datetime.now().strftime("%Y-%m")
        budget = db.query(Budget).filter(
            Budget.user_id == current_user.id,
            Budget.category == tx.category,
            Budget.month == current_month,
        ).first()
        if budget:
            budget.spent_amount = max(budget.spent_amount - tx.amount, 0)

    db.delete(tx)
    db.commit()
    return {"message": "Transaction deleted"}


# ─── Budget routes (protected) ────────────────────────────────────
@app.post("/budget/set")
def set_budget(
    budget: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    if budget.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Invalid category. Must be one of {sorted(VALID_CATEGORIES)}")

    existing = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category == budget.category,
        Budget.month == budget.month,
    ).first()
    if existing:
        existing.limit_amount = budget.limit_amount
    else:
        db.add(Budget(
            user_id=current_user.id,
            category=budget.category,
            limit_amount=budget.limit_amount,
            month=budget.month,
        ))
    db.commit()
    return {"message": "Budget saved!"}


@app.get("/budgets/{user_id}")
def get_budgets(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.require_same_user(user_id, current_user)
    month = datetime.now().strftime("%Y-%m")
    return db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.month == month,
    ).all()


# ─── Chat route (protected) ───────────────────────────────────────
@app.post("/chat")
def chat(
    msg: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    txs = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

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
        user_message=msg.message,
        transactions=tx_list,
        budgets=budget_list,
        chat_history=msg.chat_history,
        user_id=current_user.id,
    )
    return {"reply": reply}


# ─── Anomaly detection (protected) ────────────────────────────────
@app.get("/anomaly/{user_id}")
def detect_anomalies(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    Isolation Forest on the user's own expense history.
    Flags transactions that are anomalous FOR THIS USER — not globally.
    """
    auth.require_same_user(user_id, current_user)

    txs = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == "expense",
    ).all()

    if len(txs) < 5:
        return {"message": "Need at least 5 expense transactions for anomaly detection.",
                "anomalies": []}

    df = pd.DataFrame([{
        "id": t.id, "amount": t.amount,
        "category_enc": CATEGORY_MAP.get(t.category, 9),
        "hour": t.date.hour if t.date else 12,
        "description": t.description,
        "category": t.category,
    } for t in txs])

    features = df[["amount", "category_enc", "hour"]].values
    clf = IsolationForest(contamination=0.1, random_state=42)
    preds = clf.fit_predict(features)
    scores = clf.score_samples(features)

    anomalies = []
    for i, (pred, score) in enumerate(zip(preds, scores)):
        if pred == -1:
            anomalies.append({
                "id": int(df.iloc[i]["id"]),
                "description": df.iloc[i]["description"],
                "amount": df.iloc[i]["amount"],
                "category": df.iloc[i]["category"],
                "anomaly_score": round(float(score), 4),
                "reason": "Unusual for your spending patterns",
            })

    anomalies.sort(key=lambda x: x["anomaly_score"])
    return {"anomaly_count": len(anomalies), "anomalies": anomalies}


# ─── Forecast (protected) ─────────────────────────────────────────
@app.get("/forecast/{user_id}")
def spending_forecast(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    Simple linear trend forecast of total monthly spending.
    Replace with Prophet for production-grade time-series.
    """
    auth.require_same_user(user_id, current_user)

    txs = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == "expense",
    ).all()

    if not txs:
        return {"forecast": [], "message": "No expense data available."}

    df = pd.DataFrame([{"date": t.date, "amount": t.amount} for t in txs])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    monthly = df.groupby("month")["amount"].sum().reset_index()
    monthly.columns = ["month", "total"]

    if len(monthly) < 2:
        return {"forecast": monthly.to_dict("records"),
                "message": "Need 2+ months for a trend forecast."}

    x = np.arange(len(monthly))
    y = monthly["total"].values
    coeffs = np.polyfit(x, y, 1)
    next_val = max(0, float(np.polyval(coeffs, len(monthly))))

    last_month = pd.Period(monthly["month"].iloc[-1], "M")
    next_month = str(last_month + 1)

    forecast = monthly.to_dict("records")
    forecast.append({"month": next_month, "total": round(next_val, 2), "forecast": True})

    return {
        "forecast": forecast,
        "trend": "increasing" if coeffs[0] > 0 else "decreasing",
        "next_month_prediction": round(next_val, 2),
    }


# ─── Account reset (protected) ────────────────────────────────────
@app.delete("/account/reset")
def reset_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """Deletes all of the current user's transactions and zeroes budget spend."""
    db.query(Transaction).filter(Transaction.user_id == current_user.id).delete()
    db.query(Budget).filter(Budget.user_id == current_user.id).update({"spent_amount": 0})
    db.commit()
    return {"message": "All data cleared"}