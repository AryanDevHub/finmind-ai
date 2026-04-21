# FinMind AI — Personal Finance Assistant

> AI-powered financial platform with real-time fraud detection, 
> budget tracking, transaction management, and an LLM-powered 
> financial advisor chatbot.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100-green)
![LightGBM](https://img.shields.io/badge/LightGBM-0.94_AUC-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Live Demo
🔗 [Live App](https://finmind-ai.streamlit.app/) 

---

## What is FinMind AI?

FinMind AI is a full-stack AI product that acts as your personal 
CFO. It detects fraud in real time, tracks your spending, manages 
budgets, analyzes credit health, and answers any financial question 
through an AI chatbot that knows your actual data.

---

## Features

### 🔍 Fraud Detection Engine
- Trained on 590,540 real transactions from IEEE-CIS Kaggle dataset
- LightGBM classifier achieving **0.9588 AUC-ROC**
- SHAP explainability — shows exactly WHY a transaction was flagged
- Real-time scoring on every expense transaction
- Risk levels: LOW / MEDIUM / HIGH / CRITICAL

### 🤖 AI Financial Advisor Chatbot
- Powered by **Llama 3.3 70B** via Groq API (free)
- Reads your actual income, expenses, and budget data
- Gives personalized advice, not generic tips
- Multi-turn conversation with memory

### 💰 Budget Manager
- Set monthly budgets by category
- Real-time progress tracking
- Alerts when approaching limits
- Automatically updates when transactions are added

### 📊 Financial Dashboard
- Income vs expense charts
- Spending by category (pie chart)
- Monthly trends
- Complete transaction history

### 🔐 Transaction Tracker
- Add income and expenses manually
- Auto fraud scoring on every transaction
- Category-wise breakdown
- Fraud alert highlighting

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| ML Model | LightGBM + SMOTE + SHAP |
| LLM Chatbot | Groq API (Llama 3.3 70B) |
| Backend | FastAPI + Python |
| Frontend | Streamlit + Plotly |
| Database | SQLite + SQLAlchemy |
| Deployment | Render.com |
| Training | Google Colab (T4 GPU) |

---

## Architecture
User → Streamlit Frontend
↓
FastAPI Backend
├── /transaction/add → LightGBM fraud scoring → SQLite
├── /chat           → Groq AI (with user data context)
├── /budgets        → Budget CRUD
└── /transactions   → Transaction history

---

## Model Performance

| Metric | Score |
|--------|-------|
| AUC-ROC | 0.9588 |
| Training samples | 590,540 |
| Features used | 394 |
| Class imbalance handling | SMOTE |
| Explainability | SHAP values |

---

## Installation
```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/finmind-ai.git
cd finmind-ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Initialize database
python setup_db.py

# Start backend
uvicorn backend.main:app --reload

# Start frontend (new terminal)
streamlit run frontend/app.py
```

---

## Dataset

- **IEEE-CIS Fraud Detection** dataset from Kaggle
- 590,540 transactions with 394 features
- 3.5% fraud rate (severe class imbalance)
- Solved using SMOTE oversampling

---

## CV Bullet Point

> Built FinMind AI — production-grade personal finance platform 
> with real-time fraud detection (LightGBM, 0.9588 AUC on 590k 
> transactions), Llama 3.3 70B financial advisor chatbot via Groq 
> API, budget tracking, and SHAP explainability. Deployed via 
> FastAPI + Streamlit with SQLite persistence.

---

## Author

**Aryan** — [GitHub](https://github.com/YOUR_USERNAME)
