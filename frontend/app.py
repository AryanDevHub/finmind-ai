import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

API = "http://127.0.0.1:8000"

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="FinMind AI",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 20px;
        border-left: 4px solid #1D9E75;
        margin-bottom: 10px;
    }
    .fraud-critical { border-left: 4px solid #E24B4A !important; }
    .fraud-high     { border-left: 4px solid #EF9F27 !important; }
    .fraud-low      { border-left: 4px solid #1D9E75 !important; }
    .chat-user { background:#1e2130; padding:10px 15px;
                 border-radius:12px; margin:5px 0; text-align:right; }
    .chat-bot  { background:#162032; padding:10px 15px;
                 border-radius:12px; margin:5px 0;
                 border-left:3px solid #1D9E75; }
    div[data-testid="stSidebarNav"] { display:none; }
</style>
""", unsafe_allow_html=True)

# ─── Session State ───────────────────────────────────────────────
if "user_id"      not in st.session_state: st.session_state.user_id = 1
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "messages"     not in st.session_state: st.session_state.messages = []

# ─── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💳 FinMind AI")
    st.markdown("---")
    page = st.radio("Navigate", [
        "📊 Dashboard",
        "➕ Add Transaction",
        "💰 Budget Manager",
        "🤖 AI Advisor",
        "🔍 Fraud Alerts"
    ])
    st.markdown("---")
    st.markdown(f"**User ID:** {st.session_state.user_id}")
    st.caption("Powered by LightGBM + Groq AI")

# ─── Helper functions ────────────────────────────────────────────
def get_transactions():
    try:
        r = requests.get(f"{API}/transactions/{st.session_state.user_id}")
        return r.json() if r.status_code == 200 else []
    except:
        return []

def get_budgets():
    try:
        r = requests.get(f"{API}/budgets/{st.session_state.user_id}")
        return r.json() if r.status_code == 200 else []
    except:
        return []

def risk_color(risk):
    return {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(risk,"🟢")

# ════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("📊 Financial Dashboard")

    txs = get_transactions()

    if not txs:
        st.info("No transactions yet. Add your first transaction!")
        st.stop()

    df = pd.DataFrame(txs)
    df['date']   = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)

    income  = df[df['transaction_type']=='income']['amount'].sum()
    expense = df[df['transaction_type']=='expense']['amount'].sum()
    savings = income - expense
    savings_rate = (savings / income * 100) if income > 0 else 0
    flagged = df[df['is_flagged']==True].shape[0]

    # Metric cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Income",   f"₹{income:,.0f}")
    c2.metric("💸 Total Expenses", f"₹{expense:,.0f}")
    c3.metric("🏦 Net Savings",    f"₹{savings:,.0f}",
              f"{savings_rate:.1f}% savings rate")
    c4.metric("🚨 Fraud Alerts",   flagged,
              "transactions flagged" if flagged > 0 else "all clear")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Spending by Category")
        exp_df = df[df['transaction_type']=='expense'].groupby('category')['amount'].sum().reset_index()
        if not exp_df.empty:
            fig = px.pie(exp_df, values='amount', names='category',
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(0,0,0,0)',
                              font_color='white')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Income vs Expenses")
        monthly = df.groupby([df['date'].dt.strftime('%Y-%m'),
                               'transaction_type'])['amount'].sum().reset_index()
        monthly.columns = ['month','type','amount']
        if not monthly.empty:
            fig2 = px.bar(monthly, x='month', y='amount', color='type',
                          barmode='group',
                          color_discrete_map={'income':'#1D9E75','expense':'#E24B4A'})
            fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(0,0,0,0)',
                               font_color='white')
            st.plotly_chart(fig2, use_container_width=True)

    # Recent transactions table
    st.subheader("Recent Transactions")
    display_df = df[['date','description','category',
                     'amount','transaction_type',
                     'fraud_score','risk_level']].head(10).copy()
    display_df['fraud_score'] = display_df['fraud_score'].apply(lambda x: f"{x:.1f}%")
    display_df['risk_level']  = display_df['risk_level'].apply(
        lambda x: f"{risk_color(x)} {x}")
    display_df['date'] = display_df['date'].dt.strftime('%d %b %Y')
    st.dataframe(display_df, use_container_width=True)

# ════════════════════════════════════════════════════════════════
# PAGE 2 — ADD TRANSACTION
# ════════════════════════════════════════════════════════════════
elif page == "➕ Add Transaction":
    st.title("➕ Add Transaction")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Transaction Details")
        tx_type = st.selectbox("Type", ["expense", "income"])
        desc    = st.text_input("Description", placeholder="e.g. Swiggy order")
        amount  = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        category = st.selectbox("Category", [
            "Food", "Transport", "Shopping", "Entertainment",
            "Bills", "Health", "Education", "Salary",
            "Investment", "Other"
        ])

        if st.button("➕ Add Transaction", type="primary"):
            payload = {
                "user_id":          st.session_state.user_id,
                "description":      desc,
                "amount":           amount,
                "category":         category,
                "transaction_type": tx_type
            }
            r = requests.post(f"{API}/transaction/add", json=payload)
            if r.status_code == 200:
                result = r.json()
                st.success("✓ Transaction added!")

                # Show fraud result
                risk = result['risk_level']
                score = result['fraud_score']

                if result['is_flagged']:
                    st.error(f"🚨 FRAUD ALERT — Risk: {risk} | Score: {score}%")
                else:
                    st.success(f"✓ Transaction looks safe — Risk: {risk} | Score: {score}%")

                # Fraud score gauge
                fig = go.Figure(go.Indicator(
                    mode  = "gauge+number",
                    value = score,
                    title = {"text": "Fraud Risk Score"},
                    gauge = {
                        "axis": {"range": [0, 100]},
                        "bar":  {"color": "#E24B4A" if score > 60 else "#1D9E75"},
                        "steps": [
                            {"range": [0,  40], "color": "#0d2b1f"},
                            {"range": [40, 70], "color": "#2b2000"},
                            {"range": [70,100], "color": "#2b0000"},
                        ]
                    }
                ))
                fig.update_layout(
                    height=250,
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Recent Transactions")
        txs = get_transactions()
        if txs:
            for tx in txs[:8]:
                icon = "🔴" if tx['is_flagged'] else "✅"
                st.markdown(
                    f"{icon} **{tx['description']}** — "
                    f"₹{tx['amount']:,.0f} | {tx['category']} | "
                    f"Risk: {tx['risk_level']}"
                )

# ════════════════════════════════════════════════════════════════
# PAGE 3 — BUDGET MANAGER
# ════════════════════════════════════════════════════════════════
elif page == "💰 Budget Manager":
    st.title("💰 Budget Manager")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Set Monthly Budget")
        cat    = st.selectbox("Category", [
            "Food","Transport","Shopping","Entertainment",
            "Bills","Health","Education","Other"
        ])
        limit  = st.number_input("Monthly Limit (₹)", min_value=100.0,
                                  value=5000.0, step=500.0)
        month  = datetime.now().strftime("%Y-%m")

        if st.button("💾 Save Budget", type="primary"):
            payload = {
                "user_id":      st.session_state.user_id,
                "category":     cat,
                "limit_amount": limit,
                "month":        month
            }
            r = requests.post(f"{API}/budget/set", json=payload)
            if r.status_code == 200:
                st.success(f"✓ Budget set: ₹{limit:,.0f}/month for {cat}")

    with col2:
        st.subheader(f"Budget Status — {month}")
        budgets = get_budgets()

        if not budgets:
            st.info("No budgets set yet. Set your first budget!")
        else:
            for b in budgets:
                spent = b['spent_amount']
                limit = b['limit_amount']
                pct   = min((spent / limit * 100), 100) if limit > 0 else 0
                color = "🔴" if pct > 90 else "🟠" if pct > 70 else "🟢"

                st.markdown(f"**{color} {b['category']}**")
                st.progress(pct / 100)
                st.caption(
                    f"Spent ₹{spent:,.0f} of ₹{limit:,.0f} "
                    f"({pct:.0f}%) — "
                    f"₹{max(limit-spent,0):,.0f} remaining"
                )
                st.markdown("---")

# ════════════════════════════════════════════════════════════════
# PAGE 4 — AI ADVISOR CHATBOT
# ════════════════════════════════════════════════════════════════
elif page == "🤖 AI Advisor":
    st.title("🤖 FinMind AI Financial Advisor")
    st.caption("Powered by Llama 3.3 70B — knows your real financial data")

    # Chat display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg['role'] == 'user':
                st.markdown(
                    f'<div class="chat-user">👤 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="chat-bot">🤖 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )

    # Quick question buttons
    st.markdown("**Quick questions:**")
    qcol1, qcol2, qcol3 = st.columns(3)
    quick_q = None
    if qcol1.button("📊 How am I doing?"):
        quick_q = "Give me a summary of my financial health this month"
    if qcol2.button("💡 Save more money"):
        quick_q = "How can I save more money based on my spending?"
    if qcol3.button("🚨 Any fraud risks?"):
        quick_q = "Are there any suspicious transactions I should know about?"

    # Chat input
    user_input = st.chat_input("Ask me anything about your finances...")
    if quick_q:
        user_input = quick_q

    if user_input:
        # Add to display
        st.session_state.messages.append({"role":"user","content":user_input})

        # Call API
        with st.spinner("FinMind AI is thinking..."):
            payload = {
                "user_id":      st.session_state.user_id,
                "message":      user_input,
                "chat_history": st.session_state.chat_history
            }
            r = requests.post(f"{API}/chat", json=payload)
            if r.status_code == 200:
                reply = r.json()['reply']
            else:
                reply = "Sorry, I couldn't process that. Please try again."

        # Add reply to display
        st.session_state.messages.append({"role":"assistant","content":reply})
        st.session_state.chat_history.append({"role":"user","content":user_input})
        st.session_state.chat_history.append({"role":"assistant","content":reply})
        st.rerun()

# ════════════════════════════════════════════════════════════════
# PAGE 5 — FRAUD ALERTS
# ════════════════════════════════════════════════════════════════
elif page == "🔍 Fraud Alerts":
    st.title("🔍 Fraud Detection Alerts")

    txs = get_transactions()
    if not txs:
        st.info("No transactions yet.")
        st.stop()

    df = pd.DataFrame(txs)
    df['amount'] = df['amount'].astype(float)

    flagged_df = df[df['is_flagged'] == True]
    all_df     = df.copy()

    # Summary metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Transactions", len(df))
    c2.metric("🚨 Flagged",         len(flagged_df),
              f"{len(flagged_df)/len(df)*100:.1f}% of total")
    c3.metric("💰 Amount at Risk",
              f"₹{flagged_df['amount'].sum():,.0f}" if len(flagged_df)>0 else "₹0")

    st.markdown("---")

    # Fraud score distribution
    st.subheader("Fraud Score Distribution")
    fig = px.histogram(
        all_df, x='fraud_score', nbins=30,
        color_discrete_sequence=['#378ADD'],
        title="Distribution of Fraud Scores"
    )
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font_color='white')
    st.plotly_chart(fig, use_container_width=True)

    # Flagged transactions
    st.subheader("🚨 Flagged Transactions")
    if flagged_df.empty:
        st.success("✓ No fraud detected! All transactions look safe.")
    else:
        for _, tx in flagged_df.iterrows():
            with st.expander(
                f"🔴 {tx['description']} — ₹{tx['amount']:,.0f} "
                f"| Risk: {tx['risk_level']} | Score: {tx['fraud_score']:.1f}%"
            ):
                col1, col2 = st.columns(2)
                col1.metric("Fraud Score", f"{tx['fraud_score']:.1f}%")
                col2.metric("Risk Level",  tx['risk_level'])
                st.write(f"Category: {tx['category']}")
                st.write(f"Date: {tx['date']}")