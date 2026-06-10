# FinMind AI

> Personal finance platform with real-time fraud detection, RAG-powered AI advisor, budget tracking, anomaly detection, and spending forecasts.

![CI](https://github.com/YOUR_USERNAME/finmind-ai/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![LightGBM](https://img.shields.io/badge/LightGBM-0.9588_AUC-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

🔗 [Live App](https://finmind-ai.streamlit.app) &nbsp;|&nbsp; 📖 [API Docs](YOUR_RENDER_URL/docs) &nbsp;|&nbsp; 🎬 [Demo Video](#demo)

---

![FinMind AI Dashboard](./assets/finmind-demo.gif)

---

## What it does

FinMind AI acts as a personal CFO — it scores every transaction for fraud in real time, tracks budgets, flags anomalies in your spending patterns, and answers financial questions through an AI agent that reads your actual data.

Built end-to-end: data → model training → REST API → deployed frontend.

---

## Features

### Fraud Detection
- LightGBM trained on 590,540 transactions from the IEEE-CIS Kaggle dataset
- **0.9588 AUC-ROC** with SMOTE oversampling for 3.5% class imbalance
- SHAP explainability — shows exactly which features drove each flag
- Risk levels: `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` on every expense

### RAG-Powered AI Advisor
- Llama 3.3 70B via Groq API with **tool-calling** (agentic, not just a prompt wrapper)
- ChromaDB vector store + `all-MiniLM-L6-v2` embeddings for semantic retrieval
- Retrieves relevant past transactions before answering — personalised to your data
- Tools the agent can call: `get_financial_summary`, `get_fraud_alerts`, `get_category_breakdown`, `get_budget_status`

### Anomaly Detection
- Isolation Forest on each user's own expense history
- Flags "unusual for you" — not just globally suspicious
- Separate from the supervised fraud model — catches drift in personal patterns

### Spending Forecast
- Linear trend model per user (Prophet-ready stub)
- Predicts next month's spend per category from transaction history

### Budget Manager
- Set monthly limits per category
- Real-time utilisation bars, sorted by highest risk first
- Auto-deducts spend as transactions are added

### Dashboard
- Donut chart by category, grouped bar income vs expenses, cumulative savings sparkline
- Every transaction row shows fraud score + risk badge inline

---

## Tech Stack

| Layer | Technology |
|---|---|
| Fraud model | LightGBM + SMOTE + SHAP (IEEE-CIS, 590k rows) |
| Anomaly detection | Isolation Forest (scikit-learn) |
| LLM + agent | Groq API — Llama 3.3 70B with tool-calling |
| RAG | ChromaDB + sentence-transformers (all-MiniLM-L6-v2) |
| Backend | FastAPI + SQLAlchemy |
| Database | PostgreSQL (Render) / SQLite (local dev) |
| Frontend | Streamlit + Plotly |
| Testing | pytest + GitHub Actions CI |
| Deployment | Render.com |
| Training | Google Colab (T4 GPU) |

---

## Architecture

```
User → Streamlit Frontend
           ↓
     FastAPI Backend
     ├── POST /transaction/add
     │     ├── LightGBM fraud score (amount + category + hour)
     │     ├── ChromaDB RAG index (sentence-transformers embedding)
     │     └── PostgreSQL persist
     ├── POST /chat
     │     ├── ChromaDB semantic retrieval (top-5 relevant transactions)
     │     ├── Groq Llama 3.3 70B — tool-calling agent
     │     └── Tool execution: summary / fraud / categories / budgets
     ├── GET  /anomaly/{user_id}   → Isolation Forest on user history
     ├── GET  /forecast/{user_id}  → Linear trend / Prophet forecast
     ├── GET  /transactions/{user_id}
     └── CRUD /budget/*
```

---

## Model Performance

| Metric | Value |
|---|---|
| AUC-ROC | 0.9588 |
| Training samples | 590,540 |
| Class imbalance | SMOTE oversampling |
| Explainability | SHAP values |
| Anomaly detection | Isolation Forest (contamination = 0.10) |

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/finmind-ai.git
cd finmind-ai

python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt

cp .env.example .env
# Add GROQ_API_KEY to .env

python setup_db.py

uvicorn backend.main:app --reload       # terminal 1
streamlit run frontend/app.py           # terminal 2
```

---

## Running Tests

```bash
pytest tests/ -v
```

8 tests covering fraud scoring, budget CRUD, anomaly detection, and the forecast endpoint. CI runs on every push via GitHub Actions.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | From [console.groq.com](https://console.groq.com) — free tier available |
| `DATABASE_URL` | No | Postgres connection string. Defaults to local SQLite if unset. |
| `SECRET_KEY` | No | JWT secret. Auto-generated on Render. |

---

## Deployment (Render)

The `render.yaml` in this repo provisions everything automatically:
- Python web service running `uvicorn`
- Free-tier PostgreSQL database linked via `DATABASE_URL`
- `GROQ_API_KEY` set manually in the Render dashboard

Push to `main` → Render redeploys automatically.

---

## Dataset

IEEE-CIS Fraud Detection ([Kaggle](https://www.kaggle.com/c/ieee-fraud-detection)) — 590,540 transactions, 394 features, 3.5% fraud rate.

---

## Resume Bullet

> Built FinMind AI — end-to-end AI finance platform with LightGBM fraud detection (0.9588 AUC, 590k transactions), RAG-powered Llama 3.3 70B agent (ChromaDB + tool-calling), Isolation Forest anomaly detection, and spending forecasts. FastAPI + PostgreSQL backend, Streamlit frontend, deployed on Render with CI via GitHub Actions.

---

## Author

**Aryan** — [GitHub](https://github.com/AryanDevHub)