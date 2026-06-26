import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import json
import joblib
import gdown
from sqlalchemy import create_engine, text
from groq import Groq

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="FinMind AI",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none; }
.stApp { background: #080C14; }
section[data-testid="stSidebar"] { background: #0C1220 !important; border-right: 1px solid rgba(99,179,237,0.08) !important; }
div[data-testid="metric-container"] { background: #0F1825; border: 1px solid rgba(99,179,237,0.1); border-radius: 16px; padding: 20px 24px !important; transition: transform 0.2s ease; }
div[data-testid="metric-container"]:hover { transform: translateY(-2px); border-color: rgba(99,179,237,0.25); }
div[data-testid="metric-container"] label { color: #5A7090 !important; font-size: 12px !important; font-weight: 500 !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #E2ECF8 !important; font-family: 'Space Grotesk', sans-serif !important; font-size: 28px !important; font-weight: 600 !important; }
div[data-testid="stButton"] > button { background: linear-gradient(135deg, #1E40AF 0%, #1D4ED8 100%); color: white; border: none; border-radius: 10px; padding: 10px 24px; font-weight: 600; font-size: 14px; transition: all 0.2s ease; box-shadow: 0 4px 15px rgba(29,78,216,0.3); }
div[data-testid="stButton"] > button:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(29,78,216,0.45); }
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input { background: #0F1825 !important; border: 1px solid rgba(99,179,237,0.15) !important; border-radius: 10px !important; color: #C8D8F0 !important; }
div[data-testid="stSelectbox"] > div { background: #0F1825 !important; border: 1px solid rgba(99,179,237,0.15) !important; border-radius: 10px !important; color: #C8D8F0 !important; }
div[data-testid="stChatInput"] textarea { background: #0F1825 !important; border: 1px solid rgba(99,179,237,0.2) !important; border-radius: 14px !important; color: #C8D8F0 !important; }
div[data-testid="stExpander"] { background: #0F1825; border: 1px solid rgba(99,179,237,0.1) !important; border-radius: 12px !important; }
hr { border-color: rgba(99,179,237,0.08) !important; margin: 1.5rem 0 !important; }
::-webkit-scrollbar { width: 5px; } ::-webkit-scrollbar-track { background: #080C14; } ::-webkit-scrollbar-thumb { background: #1E2D45; border-radius: 3px; }
.fm-page-title { font-family: 'Space Grotesk', sans-serif; font-size: 26px; font-weight: 700; color: #E2ECF8; letter-spacing: -0.02em; margin-bottom: 4px; }
.fm-page-sub { font-size: 13px; color: #4A6080; margin-bottom: 1.5rem; }
.fm-card { background: #0F1825; border: 1px solid rgba(99,179,237,0.1); border-radius: 16px; padding: 20px 22px; margin-bottom: 12px; transition: all 0.25s ease; }
.fm-card:hover { border-color: rgba(99,179,237,0.22); transform: translateY(-1px); }
.fm-badge { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; padding: 3px 10px; border-radius: 20px; text-transform: uppercase; }
.fm-badge-critical { background: rgba(239,68,68,0.15); color: #F87171; border: 1px solid rgba(239,68,68,0.25); }
.fm-badge-high { background: rgba(245,158,11,0.15); color: #FCD34D; border: 1px solid rgba(245,158,11,0.25); }
.fm-badge-medium { background: rgba(251,191,36,0.1); color: #FDE68A; border: 1px solid rgba(251,191,36,0.2); }
.fm-badge-low { background: rgba(16,185,129,0.12); color: #34D399; border: 1px solid rgba(16,185,129,0.22); }
.fm-chat-user { background: linear-gradient(135deg, #1E3A5F, #1E40AF); border-radius: 18px 18px 4px 18px; padding: 12px 16px; margin: 8px 0 8px 40px; font-size: 14px; color: #DBEAFE; line-height: 1.6; }
.fm-chat-bot { background: #0F1825; border: 1px solid rgba(99,179,237,0.12); border-radius: 18px 18px 18px 4px; padding: 12px 16px; margin: 8px 40px 8px 0; font-size: 14px; color: #B0C8E8; line-height: 1.6; }
.fm-section-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #2A4060; margin: 1.5rem 0 0.75rem; padding-bottom: 8px; border-bottom: 1px solid rgba(99,179,237,0.06); }
.fm-tx-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; background: #0F1825; border: 1px solid rgba(99,179,237,0.07); margin-bottom: 8px; transition: all 0.2s ease; }
.fm-tx-row:hover { border-color: rgba(99,179,237,0.18); transform: translateX(3px); }
.fm-tx-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
.fm-sidebar-brand { padding: 20px 0 16px; text-align: center; }
.fm-budget-track { background: #1A2535; border-radius: 6px; height: 7px; margin: 10px 0 6px; overflow: hidden; }
.fm-budget-fill { height: 100%; border-radius: 6px; }
div[data-testid="stExpander"] summary { color: #F87171 !important; font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

# ─── Session State ───────────────────────────────────────────────
if "user_id"      not in st.session_state: st.session_state.user_id = 1
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "messages"     not in st.session_state: st.session_state.messages = []

# ─── Config from Streamlit secrets or env ───────────────────────
DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", ""))
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))

# ─── Database connection ─────────────────────────────────────────
@st.cache_resource
def get_engine():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)

engine = get_engine()

# ─── ML Model ────────────────────────────────────────────────────
ML_DIR        = "ml_models"
MODEL_PATH    = os.path.join(ML_DIR, "fraud_model.pkl")
FEATURES_PATH = os.path.join(ML_DIR, "feature_names.json")

@st.cache_resource
def load_model():
    os.makedirs(ML_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        with st.spinner("Downloading fraud model..."):
            gdown.download(
                "https://drive.google.com/uc?id=1_fPbrEuniakS3a0wt8-k3Mx72o7QVLSi",
                MODEL_PATH, quiet=True
            )
    model = joblib.load(MODEL_PATH)
    with open(FEATURES_PATH) as f:
        features = json.load(f)
    return model, features

try:
    model, feature_names = load_model()
    MODEL_LOADED = True
except Exception as e:
    MODEL_LOADED = False
    st.warning(f"Fraud model unavailable: {e}")

CATEGORY_MAP = {
    "Food":0,"Transport":1,"Shopping":2,"Entertainment":3,
    "Bills":4,"Health":5,"Education":6,"Salary":7,"Investment":8,"Other":9
}
CAT_ICONS = {
    "Food":"🍜","Transport":"🚗","Shopping":"🛍️","Entertainment":"🎬",
    "Bills":"⚡","Health":"💊","Education":"📚","Salary":"💼",
    "Investment":"📈","Other":"📦"
}

# ─── Plotly theme ────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#7A9ABF", size=12),
    xaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    yaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(bgcolor="#0F1825", bordercolor="rgba(99,179,237,0.3)", font=dict(color="#C8D8F0", size=13)),
)

# ─── DB helpers ──────────────────────────────────────────────────
def get_transactions(user_id=1):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM transactions WHERE user_id=:uid ORDER BY date DESC"
            ), {"uid": user_id})
            rows = result.fetchall()
            cols = result.keys()
            return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        st.error(f"DB error: {e}")
        return []

def get_budgets(user_id=1):
    try:
        month = datetime.now().strftime("%Y-%m")
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM budgets WHERE user_id=:uid AND month=:month"
            ), {"uid": user_id, "month": month})
            rows = result.fetchall()
            cols = result.keys()
            return [dict(zip(cols, row)) for row in rows]
    except:
        return []

def add_transaction_db(user_id, description, amount, category, tx_type,
                       fraud_score, risk_level, is_flagged):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO transactions
            (user_id, description, amount, category, transaction_type,
             fraud_score, risk_level, is_flagged, date)
            VALUES (:uid,:desc,:amt,:cat,:ttype,:fs,:rl,:flag,:date)
        """), {
            "uid": user_id, "desc": description, "amt": amount,
            "cat": category, "ttype": tx_type, "fs": fraud_score,
            "rl": risk_level, "flag": is_flagged, "date": datetime.utcnow()
        })
        if tx_type == "expense":
            month = datetime.now().strftime("%Y-%m")
            conn.execute(text("""
                UPDATE budgets SET spent_amount = spent_amount + :amt
                WHERE user_id=:uid AND category=:cat AND month=:month
            """), {"amt": amount, "uid": user_id, "cat": category, "month": month})
        conn.commit()

def delete_transaction_db(tx_id: int):
    """Delete a single transaction and roll back its effect on the budget."""
    with engine.connect() as conn:
        tx = conn.execute(text(
            "SELECT amount, category, transaction_type FROM transactions WHERE id=:id"
        ), {"id": tx_id}).fetchone()

        conn.execute(text("DELETE FROM transactions WHERE id=:id"), {"id": tx_id})

        if tx and tx[2] == "expense":
            month = datetime.now().strftime("%Y-%m")
            conn.execute(text("""
                UPDATE budgets SET spent_amount = GREATEST(spent_amount - :amt, 0)
                WHERE user_id=:uid AND category=:cat AND month=:month
            """), {"amt": tx[0], "uid": st.session_state.user_id, "cat": tx[1], "month": month})
        conn.commit()

def reset_all_data(user_id: int = 1):
    """Delete all transactions and zero out all budget spend for this user."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM transactions WHERE user_id=:uid"), {"uid": user_id})
        conn.execute(text("UPDATE budgets SET spent_amount=0 WHERE user_id=:uid"), {"uid": user_id})
        conn.commit()

def set_budget_db(user_id, category, limit_amount):
    month = datetime.now().strftime("%Y-%m")
    with engine.connect() as conn:
        existing = conn.execute(text(
            "SELECT id FROM budgets WHERE user_id=:uid AND category=:cat AND month=:month"
        ), {"uid": user_id, "cat": category, "month": month}).fetchone()
        if existing:
            conn.execute(text(
                "UPDATE budgets SET limit_amount=:lim WHERE user_id=:uid AND category=:cat AND month=:month"
            ), {"lim": limit_amount, "uid": user_id, "cat": category, "month": month})
        else:
            conn.execute(text("""
                INSERT INTO budgets (user_id, category, limit_amount, spent_amount, month)
                VALUES (:uid,:cat,:lim,0,:month)
            """), {"uid": user_id, "cat": category, "lim": limit_amount, "month": month})
        conn.commit()

# ─── Fraud scoring ───────────────────────────────────────────────
def score_fraud(amount, category):
    if not MODEL_LOADED:
        return 0.0, "LOW", False
    try:
        data = pd.DataFrame([np.zeros(len(feature_names))], columns=feature_names)
        if "TransactionAmt" in feature_names: data["TransactionAmt"] = amount
        if "card1" in feature_names: data["card1"] = CATEGORY_MAP.get(category, 9)
        if "D1" in feature_names: data["D1"] = datetime.now().hour
        prob  = float(model.predict_proba(data)[0][1])
        score = round(prob * 100, 2)
        if prob >= 0.8:   return score, "CRITICAL", True
        elif prob >= 0.6: return score, "HIGH",     True
        elif prob >= 0.4: return score, "MEDIUM",   False
        else:             return score, "LOW",       False
    except:
        return 0.0, "LOW", False

# ─── Chatbot ─────────────────────────────────────────────────────
def get_advice(user_message, transactions, budgets, chat_history):
    if not GROQ_API_KEY:
        return "Please add your GROQ_API_KEY to Streamlit secrets."
    client = Groq(api_key=GROQ_API_KEY)
    income  = sum(t['amount'] for t in transactions if t['transaction_type']=='income')
    expense = sum(t['amount'] for t in transactions if t['transaction_type']=='expense')
    savings_rate = ((income-expense)/income*100) if income > 0 else 0
    flagged = sum(1 for t in transactions if t.get('is_flagged'))
    cats = {}
    for t in transactions:
        if t['transaction_type']=='expense':
            cats[t['category']] = cats.get(t['category'],0) + t['amount']
    budget_lines = []
    for b in budgets:
        pct = (b['spent_amount']/b['limit_amount']*100) if b['limit_amount'] > 0 else 0
        budget_lines.append(f"{b['category']}: ₹{b['spent_amount']:.0f} of ₹{b['limit_amount']:.0f} ({pct:.0f}%)")
    system = f"""You are FinMind AI, a smart personal financial advisor.
USER FINANCIAL SUMMARY:
- Total Income:  ₹{income:,.0f}
- Total Expenses: ₹{expense:,.0f}
- Savings Rate: {savings_rate:.1f}%
- Net Savings: ₹{income-expense:,.0f}
- Fraud alerts: {flagged}

SPENDING BY CATEGORY:
{chr(10).join([f'- {k}: ₹{v:,.0f}' for k,v in cats.items()])}

BUDGET STATUS:
{chr(10).join(budget_lines) if budget_lines else 'No budgets set'}

Be specific, use ₹, keep under 150 words, give real insights from actual numbers."""
    messages = [{"role":"system","content":system}]
    for msg in chat_history[-6:]: messages.append(msg)
    messages.append({"role":"user","content":user_message})
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=messages,
        max_tokens=300, temperature=0.7
    )
    return resp.choices[0].message.content

# ─── Risk badge ──────────────────────────────────────────────────
def risk_badge(risk):
    cls = {"CRITICAL":"fm-badge-critical","HIGH":"fm-badge-high",
           "MEDIUM":"fm-badge-medium","LOW":"fm-badge-low"}.get(risk,"fm-badge-low")
    dot = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(risk,"🟢")
    return f'<span class="fm-badge {cls}">{dot} {risk}</span>'

def budget_bar_color(pct):
    if pct > 90: return "linear-gradient(90deg,#EF4444,#F87171)"
    if pct > 70: return "linear-gradient(90deg,#F59E0B,#FCD34D)"
    return "linear-gradient(90deg,#3B82F6,#60A5FA)"

def render_transaction_row(tx):
    """Renders one transaction row with an inline delete button."""
    icon      = CAT_ICONS.get(tx['category'], "📦")
    is_fraud  = tx.get('is_flagged', False)
    amt_color = "#F87171" if tx['transaction_type']=='expense' else "#34D399"
    amt_sign  = "-" if tx['transaction_type']=='expense' else "+"
    icon_bg   = "rgba(239,68,68,0.12)" if is_fraud else "rgba(59,130,246,0.1)"
    badge     = risk_badge(tx.get('risk_level','LOW'))

    col_tx, col_del = st.columns([12, 1])
    with col_tx:
        st.markdown(f"""
        <div class="fm-tx-row">
            <div class="fm-tx-icon" style="background:{icon_bg};">{icon}</div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:14px;font-weight:500;color:#C8D8F0;">{tx['description']}</div>
                <div style="font-size:12px;color:#4A6080;">{tx['category']} · {str(tx['date'])[:10]}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
                <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:600;color:{amt_color};margin-bottom:4px;">
                    {amt_sign}₹{tx['amount']:,.0f}
                </div>
                {badge}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_del:
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️", key=f"del_{tx['id']}", help="Delete this transaction"):
            delete_transaction_db(tx['id'])
            st.rerun()

# ─── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="fm-sidebar-brand">
        <span style="font-size:36px;">💳</span>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:700;color:#E2ECF8;">FinMind AI</div>
        <div style="font-size:11px;color:#3B82F6;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;">Personal CFO</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("", [
        "📊  Dashboard", "➕  Add Transaction",
        "💰  Budget Manager", "🤖  AI Advisor", "🔍  Fraud Alerts"
    ], label_visibility="collapsed")

    st.markdown("---")
    db_ok = True
    try:
        with engine.connect() as c: c.execute(text("SELECT 1"))
    except: db_ok = False

    status_color = "#10B981" if db_ok else "#EF4444"
    status_text  = "connected" if db_ok else "offline"
    st.markdown(f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#0F1825;border:1px solid rgba(99,179,237,0.1);border-radius:8px;font-size:11px;color:#5A7090;"><span style="width:8px;height:8px;border-radius:50%;background:{status_color};display:inline-block;"></span> <strong style="color:#C8D8F0;">DB</strong> {status_text}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚠️ Danger zone"):
        st.caption("This permanently deletes all your transactions and resets budget spend to zero.")
        confirm = st.checkbox("I understand this cannot be undone")
        if st.button("🗑️ Reset all data", type="primary", use_container_width=True, disabled=not confirm):
            reset_all_data(st.session_state.user_id)
            st.success("All data cleared!")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Powered by LightGBM + Groq Llama 3.3 70B")


# ════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ════════════════════════════════════════════════════════════════
if "Dashboard" in page:
    st.markdown('<p class="fm-page-title">Financial Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Your money at a glance — updated in real time</p>', unsafe_allow_html=True)

    txs = get_transactions()
    if not txs:
        st.markdown("""<div class="fm-card" style="text-align:center;padding:40px;">
            <div style="font-size:48px;margin-bottom:12px;">📭</div>
            <div style="color:#4A6080;font-size:15px;">No transactions yet. Add your first one!</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(txs)
    df['date']   = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)

    income   = df[df['transaction_type']=='income']['amount'].sum()
    expense  = df[df['transaction_type']=='expense']['amount'].sum()
    savings  = income - expense
    savings_rate = (savings/income*100) if income > 0 else 0
    flagged  = df[df['is_flagged']==True].shape[0]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("💰 Total Income",   f"₹{income:,.0f}")
    c2.metric("💸 Total Expenses", f"₹{expense:,.0f}")
    c3.metric("🏦 Net Savings",    f"₹{savings:,.0f}", f"{savings_rate:.1f}% rate")
    c4.metric("🚨 Fraud Alerts",   flagged, "flagged" if flagged > 0 else "all clear")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="fm-section-label">Spending by category</p>', unsafe_allow_html=True)
        exp_df = df[df['transaction_type']=='expense'].groupby('category')['amount'].sum().reset_index()
        if not exp_df.empty:
            fig = px.pie(exp_df, values='amount', names='category',
                         color_discrete_sequence=["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899","#06B6D4","#14B8A6"],
                         hole=0.52)
            fig.update_traces(textposition='outside', textinfo='label+percent',
                              marker=dict(line=dict(color='#080C14', width=2)),
                              hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>")
            fig.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                              margin=dict(l=10,r=10,t=30,b=10),
                              showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col2:
        st.markdown('<p class="fm-section-label">Income vs expenses</p>', unsafe_allow_html=True)
        monthly = df.groupby([df['date'].dt.strftime('%b %Y'),'transaction_type'])['amount'].sum().reset_index()
        monthly.columns = ['month','type','amount']
        if not monthly.empty:
            fig2 = px.bar(monthly, x='month', y='amount', color='type', barmode='group',
                          color_discrete_map={'income':'#10B981','expense':'#3B82F6'})
            fig2.update_traces(marker_line_width=0,
                               hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>")
            fig2.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                               margin=dict(l=10,r=10,t=30,b=10),
                               height=300, legend=dict(orientation="h", y=1.12,
                               bgcolor="rgba(0,0,0,0)", font=dict(color="#7A9ABF")))
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    # Sparkline
    st.markdown('<p class="fm-section-label">Net savings trend</p>', unsafe_allow_html=True)
    daily = df.groupby([df['date'].dt.date,'transaction_type'])['amount'].sum().unstack(fill_value=0).reset_index()
    if 'income'  not in daily.columns: daily['income']  = 0
    if 'expense' not in daily.columns: daily['expense'] = 0
    daily['cumulative'] = (daily['income'] - daily['expense']).cumsum()
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=daily['date'], y=daily['cumulative'], mode='lines',
        line=dict(color='#3B82F6', width=2.5, shape='spline'),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.07)',
        hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
    ))
    fig3.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                       margin=dict(l=10,r=10,t=10,b=10), height=160)
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar":False})

    # Recent transactions — with delete buttons
    st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
    for tx in txs[:8]:
        render_transaction_row(tx)


# ════════════════════════════════════════════════════════════════
# PAGE 2 — ADD TRANSACTION
# ════════════════════════════════════════════════════════════════
elif "Add Transaction" in page:
    st.markdown('<p class="fm-page-title">Add Transaction</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Every expense is scored for fraud in real time</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1,1], gap="large")

    with col1:
        st.markdown('<p class="fm-section-label">Transaction details</p>', unsafe_allow_html=True)
        tx_type  = st.selectbox("Type", ["expense","income"])
        desc     = st.text_input("Description", placeholder="e.g. Swiggy order...")
        amount   = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        category = st.selectbox("Category", list(CAT_ICONS.keys()))

        if st.button("➕ Add Transaction", type="primary", use_container_width=True):
            if not desc.strip():
                st.error("Please enter a description.")
            else:
                fraud_score, risk_level, is_flagged = 0.0, "LOW", False
                if tx_type == "expense":
                    fraud_score, risk_level, is_flagged = score_fraud(amount, category)

                add_transaction_db(
                    st.session_state.user_id, desc, amount, category,
                    tx_type, fraud_score, risk_level, is_flagged
                )

                if is_flagged:
                    st.error(f"🚨 Fraud Alert! Risk: {risk_level} | Score: {fraud_score:.1f}%")
                else:
                    st.success(f"✓ Transaction added! Risk: {risk_level} | Score: {fraud_score:.1f}%")

                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=fraud_score,
                    number=dict(suffix="%", font=dict(color="#E2ECF8", size=32, family="Space Grotesk, sans-serif")),
                    gauge=dict(
                        axis=dict(range=[0,100], tickcolor="#2A3F5F", tickfont=dict(color="#4A6080")),
                        bar=dict(color="#EF4444" if fraud_score>60 else "#10B981", thickness=0.18),
                        bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
                        steps=[
                            dict(range=[0,40],  color="rgba(16,185,129,0.08)"),
                            dict(range=[40,70], color="rgba(245,158,11,0.08)"),
                            dict(range=[70,100],color="rgba(239,68,68,0.08)"),
                        ]
                    )
                ))
                fig.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                                  margin=dict(l=10,r=10,t=30,b=10), height=220,
                                  title=dict(text="Fraud Risk Score", font=dict(color="#4A6080",size=13), x=0.5))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col2:
        st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
        txs = get_transactions()
        for tx in txs[:10]:
            render_transaction_row(tx)


# ════════════════════════════════════════════════════════════════
# PAGE 3 — BUDGET MANAGER
# ════════════════════════════════════════════════════════════════
elif "Budget" in page:
    st.markdown('<p class="fm-page-title">Budget Manager</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Set limits and track spending by category</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1,1.4], gap="large")
    month_display = datetime.now().strftime("%B %Y")

    with col1:
        st.markdown('<p class="fm-section-label">Set monthly budget</p>', unsafe_allow_html=True)
        cat   = st.selectbox("Category", ["Food","Transport","Shopping","Entertainment","Bills","Health","Education","Other"])
        limit = st.number_input("Monthly limit (₹)", min_value=100.0, value=5000.0, step=500.0)

        if st.button("💾 Save Budget", type="primary", use_container_width=True):
            set_budget_db(st.session_state.user_id, cat, limit)
            st.success(f"Budget saved — ₹{limit:,.0f}/month for {cat}")

    with col2:
        st.markdown(f'<p class="fm-section-label">Budget status — {month_display}</p>', unsafe_allow_html=True)
        budgets = get_budgets()

        if not budgets:
            st.markdown('<div class="fm-card" style="text-align:center;padding:32px;color:#3A5070;">No budgets set yet.</div>', unsafe_allow_html=True)
        else:
            for b in sorted(budgets, key=lambda x: x['spent_amount']/x['limit_amount'] if x['limit_amount']>0 else 0, reverse=True):
                spent = b['spent_amount']
                lim   = b['limit_amount']
                pct   = min((spent/lim*100),100) if lim > 0 else 0
                icon  = CAT_ICONS.get(b['category'],"📦")
                color = budget_bar_color(pct)
                label_color = "#F87171" if pct>90 else "#FCD34D" if pct>70 else "#60A5FA"
                st.markdown(f"""
                <div class="fm-card" style="padding:14px 16px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <span style="font-size:20px;">{icon}</span>
                            <span style="font-size:14px;font-weight:500;color:#C8D8F0;">{b['category']}</span>
                        </div>
                        <span style="font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:600;color:{label_color};">{pct:.0f}%</span>
                    </div>
                    <div class="fm-budget-track"><div class="fm-budget-fill" style="width:{pct}%;background:{color};"></div></div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;color:#3A5070;">
                        <span>₹{spent:,.0f} spent</span>
                        <span>₹{max(lim-spent,0):,.0f} left of ₹{lim:,.0f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# PAGE 4 — AI ADVISOR
# ════════════════════════════════════════════════════════════════
elif "AI Advisor" in page:
    st.markdown('<p class="fm-page-title">AI Financial Advisor</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Powered by Llama 3.3 70B — knows your real numbers</p>', unsafe_allow_html=True)

    qc1,qc2,qc3,qc4 = st.columns(4)
    quick_q = None
    if qc1.button("📊 Financial health", use_container_width=True): quick_q = "Give me a summary of my financial health"
    if qc2.button("💡 Save more",        use_container_width=True): quick_q = "How can I save more based on my spending?"
    if qc3.button("🚨 Fraud risks",      use_container_width=True): quick_q = "Any suspicious transactions I should know about?"
    if qc4.button("📈 Invest advice",    use_container_width=True): quick_q = "Where should I invest my savings?"

    st.markdown("---")

    if not st.session_state.messages:
        st.markdown("""<div class="fm-card" style="text-align:center;padding:32px 20px;">
            <div style="font-size:40px;margin-bottom:12px;">🤖</div>
            <div style="font-size:15px;font-weight:500;color:#7A9ABF;margin-bottom:6px;">FinMind AI is ready</div>
            <div style="font-size:13px;color:#3A5070;max-width:380px;margin:0 auto;line-height:1.6;">
                Ask me anything about your finances. I can see your actual income, expenses, and budgets.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        for msg in st.session_state.messages:
            if msg['role']=='user':
                st.markdown(f'<div class="fm-chat-user">👤 &nbsp;{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="fm-chat-bot">🤖 &nbsp;{msg["content"]}</div>', unsafe_allow_html=True)

    user_input = st.chat_input("Ask about your spending, savings, fraud alerts...")
    if quick_q: user_input = quick_q

    if user_input:
        st.session_state.messages.append({"role":"user","content":user_input})
        with st.spinner("FinMind AI is thinking..."):
            txs     = get_transactions()
            budgets = get_budgets()
            reply   = get_advice(user_input, txs, budgets, st.session_state.chat_history)
        st.session_state.messages.append({"role":"assistant","content":reply})
        st.session_state.chat_history.append({"role":"user","content":user_input})
        st.session_state.chat_history.append({"role":"assistant","content":reply})
        st.rerun()

    if st.session_state.messages:
        if st.button("🗑️ Clear chat"):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.rerun()


# ════════════════════════════════════════════════════════════════
# PAGE 5 — FRAUD ALERTS
# ════════════════════════════════════════════════════════════════
elif "Fraud" in page:
    st.markdown('<p class="fm-page-title">Fraud Detection</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Real-time ML scoring — powered by LightGBM (0.9588 AUC)</p>', unsafe_allow_html=True)

    txs = get_transactions()
    if not txs:
        st.markdown('<div class="fm-card" style="text-align:center;color:#3A5070;padding:32px;">No transactions yet.</div>', unsafe_allow_html=True)
        st.stop()

    df          = pd.DataFrame(txs)
    df['amount']= df['amount'].astype(float)
    flagged_df  = df[df['is_flagged']==True]
    expense_df  = df[df['transaction_type']=='expense']

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total transactions", len(df))
    c2.metric("🚨 Flagged",         len(flagged_df), f"{len(flagged_df)/len(df)*100:.1f}% of total" if len(df) else "")
    c3.metric("💰 Amount at risk",  f"₹{flagged_df['amount'].sum():,.0f}" if len(flagged_df) else "₹0")
    avg_score = expense_df['fraud_score'].mean() if len(expense_df) else 0
    c4.metric("Avg fraud score",    f"{avg_score:.1f}%")

    st.markdown("---")
    col1,col2 = st.columns(2)

    with col1:
        st.markdown('<p class="fm-section-label">Fraud score distribution</p>', unsafe_allow_html=True)
        if len(expense_df):
            fig = px.histogram(expense_df, x='fraud_score', nbins=25, color_discrete_sequence=["#3B82F6"])
            fig.update_traces(marker_line_width=0, opacity=0.85,
                              hovertemplate="Score: %{x:.0f}%<br>Count: %{y}<extra></extra>")
            fig.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                              margin=dict(l=10,r=10,t=30,b=10), height=260,
                              xaxis_title="Fraud score (%)", yaxis_title="Transactions")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col2:
        st.markdown('<p class="fm-section-label">Risk level breakdown</p>', unsafe_allow_html=True)
        risk_counts = df[df['transaction_type']=='expense']['risk_level'].value_counts().reset_index()
        risk_counts.columns = ['level','count']
        if len(risk_counts):
            rcolors = {"LOW":"#10B981","MEDIUM":"#F59E0B","HIGH":"#F97316","CRITICAL":"#EF4444"}
            fig2 = px.bar(risk_counts, x='level', y='count', color='level', color_discrete_map=rcolors)
            fig2.update_traces(marker_line_width=0,
                               hovertemplate="<b>%{x}</b><br>%{y} transactions<extra></extra>")
            fig2.update_layout(**{k:v for k,v in PLOTLY_LAYOUT.items() if k != 'margin'},
                               margin=dict(l=10,r=10,t=30,b=10), height=260, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    st.markdown('<p class="fm-section-label">Flagged transactions</p>', unsafe_allow_html=True)
    if flagged_df.empty:
        st.markdown("""<div class="fm-card" style="text-align:center;padding:32px;">
            <div style="font-size:40px;margin-bottom:10px;">✅</div>
            <div style="font-size:15px;font-weight:500;color:#34D399;">All clear — no fraud detected</div>
        </div>""", unsafe_allow_html=True)
    else:
        for _,tx in flagged_df.iterrows():
            with st.expander(f"🔴 {tx['description']} — ₹{tx['amount']:,.0f} | {tx['risk_level']} | {tx['fraud_score']:.1f}%"):
                ec1,ec2,ec3,ec4 = st.columns(4)
                ec1.metric("Fraud score", f"{tx['fraud_score']:.1f}%")
                ec2.metric("Risk level",  tx['risk_level'])
                ec3.metric("Amount",      f"₹{tx['amount']:,.0f}")
                with ec4:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"del_fraud_{tx['id']}", use_container_width=True):
                        delete_transaction_db(tx['id'])
                        st.rerun()
                st.markdown(f'<div style="margin-top:10px;padding:12px;background:rgba(239,68,68,0.06);border-radius:10px;border:1px solid rgba(239,68,68,0.15);font-size:13px;color:#F87171;">⚠️ Flagged by LightGBM fraud model. Review this transaction carefully.</div>', unsafe_allow_html=True)