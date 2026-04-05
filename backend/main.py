from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import joblib, json, numpy as np, pandas as pd
import os
from dotenv import load_dotenv

from backend.database import get_db, create_tables, Transaction, Budget, User
from backend.chatbot import get_financial_advice

load_dotenv()

app = FastAPI(title="FinMind AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Load ML model on startup
# NEW - uses absolute path so it works from anywhere
import os
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR    = os.path.join(BASE_DIR, "ml_models")

model     = joblib.load(os.path.join(ML_DIR, "fraud_model.pkl"))
explainer = joblib.load(os.path.join(ML_DIR, "shap_explainer.pkl"))
with open(os.path.join(ML_DIR, "feature_names.json")) as f:
    feature_names = json.load(f)

create_tables()
print("✓ FinMind AI backend started!")

# ─── Pydantic schemas ────────────────────────────────────────────
class TransactionCreate(BaseModel):
    user_id:          int
    description:      str
    amount:           float
    category:         str
    transaction_type: str   # income / expense

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
    return {"message": "FinMind AI is running!", "version": "1.0.0"}

@app.post("/transaction/add")
def add_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    # Run fraud detection on every expense
    fraud_score = 0.0
    risk_level  = "LOW"
    is_flagged  = False

    if tx.transaction_type == "expense":
        try:
            # Build feature vector (zeros for missing ML features)
            input_data = pd.DataFrame(
                [np.zeros(len(feature_names))],
                columns=feature_names
            )
            # Set the amount if it's a feature
            if 'TransactionAmt' in feature_names:
                input_data['TransactionAmt'] = tx.amount

            fraud_prob = model.predict_proba(input_data)[0][1]
            fraud_score = round(float(fraud_prob) * 100, 2)

            if fraud_prob >= 0.8:
                risk_level = "CRITICAL"; is_flagged = True
            elif fraud_prob >= 0.6:
                risk_level = "HIGH";     is_flagged = True
            elif fraud_prob >= 0.4:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
        except Exception as e:
            print(f"Fraud scoring error: {e}")

    # Save to database
    new_tx = Transaction(
        user_id=tx.user_id,
        description=tx.description,
        amount=tx.amount,
        category=tx.category,
        transaction_type=tx.transaction_type,
        fraud_score=fraud_score,
        risk_level=risk_level,
        is_flagged=is_flagged
    )
    db.add(new_tx)

    # Update budget spent amount
    if tx.transaction_type == "expense":
        current_month = datetime.now().strftime("%Y-%m")
        budget = db.query(Budget).filter(
            Budget.user_id == tx.user_id,
            Budget.category == tx.category,
            Budget.month == current_month
        ).first()
        if budget:
            budget.spent_amount += tx.amount

    db.commit()
    db.refresh(new_tx)

    return {
        "message":    "Transaction added",
        "id":         new_tx.id,
        "fraud_score": fraud_score,
        "risk_level": risk_level,
        "is_flagged": is_flagged
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
    # Fetch user's real data to give to chatbot
    txs = db.query(Transaction).filter(
        Transaction.user_id == msg.user_id
    ).all()
    budgets = db.query(Budget).filter(
        Budget.user_id == msg.user_id
    ).all()

    tx_list     = [{"amount": t.amount, "category": t.category,
                    "transaction_type": t.transaction_type,
                    "is_flagged": t.is_flagged} for t in txs]
    budget_list = [{"category": b.category, "limit_amount": b.limit_amount,
                    "spent_amount": b.spent_amount} for b in budgets]

    reply = get_financial_advice(
        msg.message, tx_list, budget_list, msg.chat_history
    )
    return {"reply": reply}