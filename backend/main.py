import os
import gdown
import joblib
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.database import get_db, create_tables, Transaction, Budget, User
from backend.chatbot import get_financial_advice

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR   = os.path.join(BASE_DIR, "ml_models")
os.makedirs(ML_DIR, exist_ok=True)

MODEL_PATH     = os.path.join(ML_DIR, "fraud_model.pkl")
EXPLAINER_PATH = os.path.join(ML_DIR, "shap_explainer.pkl")
FEATURES_PATH  = os.path.join(ML_DIR, "feature_names.json")

# ─── Download models from Google Drive if not present ────────────
if not os.path.exists(MODEL_PATH):
    print("Downloading fraud model from Google Drive...")
    gdown.download(
        "https://drive.google.com/uc?id=1_fPbrEuniakS3a0wt8-k3Mx72o7QVLSi",
        MODEL_PATH,
        quiet=False
    )
    print("✓ Fraud model downloaded!")

if not os.path.exists(EXPLAINER_PATH):
    print("Downloading SHAP explainer from Google Drive...")
    gdown.download(
        "https://drive.google.com/uc?id=1ABN9l7uGGL-lWwTl3fm_IPqNms7mbr9O",
        EXPLAINER_PATH,
        quiet=False
    )
    print("✓ SHAP explainer downloaded!")

# ─── Load models ─────────────────────────────────────────────────
print("Loading models...")
model     = joblib.load(MODEL_PATH)
explainer = joblib.load(EXPLAINER_PATH)

with open(FEATURES_PATH) as f:
    feature_names = json.load(f)

print("✓ All models loaded successfully!")

# ─── FastAPI app ─────────────────────────────────────────────────
app = FastAPI(title="FinMind AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

create_tables()
print("✓ FinMind AI backend started!")

# ─── Pydantic schemas ────────────────────────────────────────────
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
    return {
        "message": "FinMind AI is running!",
        "version": "1.0.0",
        "status":  "healthy"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/transaction/add")
def add_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    fraud_score = 0.0
    risk_level  = "LOW"
    is_flagged  = False

    if tx.transaction_type == "expense":
        try:
            input_data = pd.DataFrame(
                [np.zeros(len(feature_names))],
                columns=feature_names
            )
            if "TransactionAmt" in feature_names:
                input_data["TransactionAmt"] = tx.amount

            fraud_prob  = model.predict_proba(input_data)[0][1]
            fraud_score = round(float(fraud_prob) * 100, 2)

            if fraud_prob >= 0.8:
                risk_level = "CRITICAL"
                is_flagged = True
            elif fraud_prob >= 0.6:
                risk_level = "HIGH"
                is_flagged = True
            elif fraud_prob >= 0.4:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

        except Exception as e:
            print(f"Fraud scoring error: {e}")

    new_tx = Transaction(
        user_id          = tx.user_id,
        description      = tx.description,
        amount           = tx.amount,
        category         = tx.category,
        transaction_type = tx.transaction_type,
        fraud_score      = fraud_score,
        risk_level       = risk_level,
        is_flagged       = is_flagged
    )
    db.add(new_tx)

    if tx.transaction_type == "expense":
        current_month = datetime.now().strftime("%Y-%m")
        budget = db.query(Budget).filter(
            Budget.user_id  == tx.user_id,
            Budget.category == tx.category,
            Budget.month    == current_month
        ).first()
        if budget:
            budget.spent_amount += tx.amount

    db.commit()
    db.refresh(new_tx)

    return {
        "message":     "Transaction added",
        "id":          new_tx.id,
        "fraud_score": fraud_score,
        "risk_level":  risk_level,
        "is_flagged":  is_flagged
    }

@app.get("/transactions/{user_id}")
def get_transactions(user_id: int, db: Session = Depends(get_db)):
    txs = db.query(Transaction).filter(
        Transaction.user_id == user_id
    ).order_by(Transaction.date.desc()).all()
    return txs

@app.post("/budget/set")
def set_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    existing = db.query(Budget).filter(
        Budget.user_id  == budget.user_id,
        Budget.category == budget.category,
        Budget.month    == budget.month
    ).first()

    if existing:
        existing.limit_amount = budget.limit_amount
    else:
        new_budget = Budget(**budget.dict())
        db.add(new_budget)

    db.commit()
    return {"message": "Budget saved!"}

@app.get("/budgets/{user_id}")
def get_budgets(user_id: int, db: Session = Depends(get_db)):
    month   = datetime.now().strftime("%Y-%m")
    budgets = db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.month   == month
    ).all()
    return budgets

@app.post("/chat")
def chat(msg: ChatMessage, db: Session = Depends(get_db)):
    txs = db.query(Transaction).filter(
        Transaction.user_id == msg.user_id
    ).all()
    budgets = db.query(Budget).filter(
        Budget.user_id == msg.user_id
    ).all()

    tx_list = [
        {
            "amount":           t.amount,
            "category":         t.category,
            "transaction_type": t.transaction_type,
            "is_flagged":       t.is_flagged,
            "description":      t.description
        }
        for t in txs
    ]

    budget_list = [
        {
            "category":     b.category,
            "limit_amount": b.limit_amount,
            "spent_amount": b.spent_amount
        }
        for b in budgets
    ]

    reply = get_financial_advice(
        msg.message,
        tx_list,
        budget_list,
        msg.chat_history
    )
    return {"reply": reply}