"""
train_fraud_model.py — Trains FinMind AI's fraud model on the ACTUAL
features available at inference time (amount, category, hour, day-of-week).

WHY THIS EXISTS
----------------
The original model was trained offline on the 394-column IEEE-CIS Kaggle
dataset (0.9588 AUC), but the running app only ever had three real
features available at transaction time (amount, category, hour) — the
other 391 columns were zero-padded at inference. That meant the
reported 0.9588 AUC described a model that was never actually the one
scoring live transactions.

WHY SYNTHETIC DATA
--------------------
This script does NOT have access to the real IEEE-CIS dataset or any
labeled real-world transaction data. Rather than keep pretending the
offline number applies, it generates a synthetic-but-realistic dataset
with a known, documented fraud rule, and trains + reports an honest AUC
on the exact features the app actually uses. This is a defensible
starting point for a resume project: the pipeline (feature engineering
-> train/test split -> class balancing -> model -> explainability) is
real and interview-ready, and the labels are transparently synthetic.

If you get access to real transaction data later (e.g. your own bank
export, anonymized, or a Kaggle dataset with matching columns), swap
`generate_synthetic_data()` for a real loader — everything downstream
(training, evaluation, saving) stays the same.

Run:
    python ml_models/train_fraud_model.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

CATEGORY_MAP = {
    "Food": 0, "Transport": 1, "Shopping": 2, "Entertainment": 3,
    "Bills": 4, "Health": 5, "Education": 6, "Salary": 7,
    "Investment": 8, "Other": 9,
}

# Categories where large / odd-hour transactions are more suspicious
# in this synthetic world (loosely modeled on real fraud patterns:
# high-value, discretionary-category, late-night activity).
HIGH_RISK_CATEGORIES = {"Shopping", "Other", "Entertainment"}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(OUT_DIR, "fraud_model.pkl")
FEATURES_PATH = os.path.join(OUT_DIR, "feature_names.json")
METRICS_PATH = os.path.join(OUT_DIR, "model_metrics.json")
EXPLAINER_PATH = os.path.join(OUT_DIR, "shap_explainer.pkl")


def generate_synthetic_data(n_samples: int = 60_000) -> pd.DataFrame:
    """
    Builds a synthetic transaction dataset with a documented fraud rule:

    A transaction is more likely fraudulent when it combines:
      - a high amount (relative to its category's typical spend)
      - an unusual hour (late night / early morning)
      - a discretionary / high-risk category
      - some pure random noise, so the boundary isn't perfectly learnable
        (mirrors the fact that real fraud isn't 100% separable either)
    """
    categories = list(CATEGORY_MAP.keys())
    # Roughly realistic per-category typical spend (mean, std) in INR
    category_amount_params = {
        "Food": (500, 400), "Transport": (300, 250), "Shopping": (2500, 3000),
        "Entertainment": (800, 700), "Bills": (1500, 1000), "Health": (1200, 1500),
        "Education": (2000, 2500), "Salary": (40000, 20000),
        "Investment": (10000, 15000), "Other": (1000, 2000),
    }

    rows = []
    for _ in range(n_samples):
        category = np.random.choice(categories)
        mean, std = category_amount_params[category]
        amount = max(1.0, np.random.normal(mean, std))
        hour = np.random.randint(0, 24)
        day_of_week = np.random.randint(0, 7)

        # ── Fraud probability rule (ground truth) ─────────────────
        risk = 0.02  # base rate
        if amount > mean + 2 * std:
            risk += 0.35
        if hour in (0, 1, 2, 3, 4):
            risk += 0.25
        if category in HIGH_RISK_CATEGORIES:
            risk += 0.10
        if amount > mean + 2 * std and hour in (0, 1, 2, 3, 4):
            risk += 0.15  # compounding effect

        risk = min(risk, 0.97)
        is_fraud = np.random.random() < risk

        rows.append({
            "amount": round(amount, 2),
            "category": category,
            "category_enc": CATEGORY_MAP[category],
            "hour": hour,
            "day_of_week": day_of_week,
            "isFraud": int(is_fraud),
        })

    return pd.DataFrame(rows)


def train():
    print("Generating synthetic transaction dataset...")
    df = generate_synthetic_data()
    fraud_rate = df["isFraud"].mean() * 100
    print(f"  {len(df):,} rows generated | fraud rate: {fraud_rate:.2f}%")

    feature_cols = ["amount", "category_enc", "hour", "day_of_week"]
    X = df[feature_cols]
    y = df["isFraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    print("Balancing training set with SMOTE...")
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)
    print(f"  Training set after SMOTE: {len(X_train_bal):,} rows "
          f"({y_train_bal.mean()*100:.1f}% fraud)")

    print("Training LightGBM classifier...")
    model = LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        random_state=RANDOM_STATE,
        verbose=-1,
    )
    model.fit(X_train_bal, y_train_bal)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    report = classification_report(y_test, (y_pred_proba >= 0.5).astype(int), output_dict=True)

    print(f"\n✓ Test AUC-ROC: {auc:.4f}")
    print(f"  (on held-out data, features: {feature_cols})")

    # ── SHAP explainability ──────────────────────────────────────
    print("Building SHAP TreeExplainer...")
    explainer = shap.TreeExplainer(model)
    joblib.dump(explainer, EXPLAINER_PATH)

    # ── Save artifacts ─────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    with open(FEATURES_PATH, "w") as f:
        json.dump(feature_cols, f)
    with open(METRICS_PATH, "w") as f:
        json.dump({
            "auc_roc": round(auc, 4),
            "n_train_samples": int(len(X_train_bal)),
            "n_test_samples": int(len(X_test)),
            "features": feature_cols,
            "data_source": "synthetic (documented rule-based generator, see generate_synthetic_data())",
            "precision_fraud_class": round(report["1"]["precision"], 3),
            "recall_fraud_class": round(report["1"]["recall"], 3),
        }, f, indent=2)

    print(f"\n✓ Saved model to {MODEL_PATH}")
    print(f"✓ Saved feature list to {FEATURES_PATH}")
    print(f"✓ Saved SHAP explainer to {EXPLAINER_PATH}")
    print(f"✓ Saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    train()