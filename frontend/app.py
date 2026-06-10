import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

API = os.getenv("API_URL", "http://127.0.0.1:8000")

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="FinMind AI",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── MASTER CSS — Full redesign ──────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none; }
div[data-testid="stDecoration"] { display: none; }

/* ── Page background — deep navy, not pure black ── */
.stApp {
    background: #080C14;
}
section[data-testid="stSidebar"] {
    background: #0C1220 !important;
    border-right: 1px solid rgba(99,179,237,0.08) !important;
}

/* ── Sidebar nav items ── */
div[data-testid="stRadio"] label {
    display: flex;
    align-items: center;
    padding: 10px 14px;
    border-radius: 10px;
    margin: 3px 0;
    font-size: 14px;
    font-weight: 500;
    color: #8899BB !important;
    transition: all 0.2s ease;
    cursor: pointer;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(99,179,237,0.07);
    color: #C8D8F0 !important;
}
div[data-testid="stRadio"] [aria-checked="true"] + div label,
div[data-testid="stRadio"] input:checked ~ div label {
    background: rgba(59,130,246,0.12);
    color: #60A5FA !important;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.1);
    border-radius: 16px;
    padding: 20px 24px !important;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    border-color: rgba(99,179,237,0.25);
}
div[data-testid="metric-container"] label {
    color: #5A7090 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #E2ECF8 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 28px !important;
    font-weight: 600 !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricDelta"] {
    font-size: 12px !important;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #1E40AF 0%, #1D4ED8 100%);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.02em;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(29,78,216,0.3);
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(29,78,216,0.45);
    background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
}
div[data-testid="stButton"] > button:active {
    transform: translateY(0px);
}

/* ── Inputs ── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] > div {
    background: #0F1825 !important;
    border: 1px solid rgba(99,179,237,0.15) !important;
    border-radius: 10px !important;
    color: #C8D8F0 !important;
    font-size: 14px !important;
    transition: border-color 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: rgba(99,179,237,0.45) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* ── Chat input ── */
div[data-testid="stChatInput"] textarea {
    background: #0F1825 !important;
    border: 1px solid rgba(99,179,237,0.2) !important;
    border-radius: 14px !important;
    color: #C8D8F0 !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: #3B82F6 !important;
}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(99,179,237,0.1);
    border-radius: 14px;
    overflow: hidden;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.1) !important;
    border-radius: 12px !important;
    margin-bottom: 8px;
}
div[data-testid="stExpander"]:hover {
    border-color: rgba(99,179,237,0.2) !important;
}

/* ── Progress bars ── */
div[data-testid="stProgress"] > div > div {
    background: #0F1825 !important;
    border-radius: 6px !important;
    height: 8px !important;
}
div[data-testid="stProgress"] > div > div > div {
    border-radius: 6px !important;
    background: linear-gradient(90deg, #3B82F6, #60A5FA) !important;
    transition: width 0.8s cubic-bezier(0.4,0,0.2,1) !important;
}

/* ── Alerts ── */
div[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
}

/* ── Divider ── */
hr {
    border-color: rgba(99,179,237,0.08) !important;
    margin: 1.5rem 0 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #080C14; }
::-webkit-scrollbar-thumb { background: #1E2D45; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2A3F5F; }

/* ── Custom component classes ── */
.fm-page-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #E2ECF8;
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.fm-page-sub {
    font-size: 13px;
    color: #4A6080;
    margin-bottom: 1.5rem;
}
.fm-card {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.1);
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 12px;
    transition: all 0.25s ease;
    animation: fadeSlideIn 0.4s ease both;
}
.fm-card:hover {
    border-color: rgba(99,179,237,0.22);
    transform: translateY(-1px);
}
.fm-card-fraud {
    border-left: 3px solid #EF4444;
    background: linear-gradient(135deg, #0F1825 0%, #1A0F0F 100%);
}
.fm-card-safe {
    border-left: 3px solid #10B981;
}
.fm-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 3px 10px;
    border-radius: 20px;
    text-transform: uppercase;
}
.fm-badge-critical { background: rgba(239,68,68,0.15); color: #F87171; border: 1px solid rgba(239,68,68,0.25); }
.fm-badge-high     { background: rgba(245,158,11,0.15); color: #FCD34D; border: 1px solid rgba(245,158,11,0.25); }
.fm-badge-medium   { background: rgba(251,191,36,0.1);  color: #FDE68A; border: 1px solid rgba(251,191,36,0.2); }
.fm-badge-low      { background: rgba(16,185,129,0.12); color: #34D399; border: 1px solid rgba(16,185,129,0.22); }
.fm-chat-user {
    background: linear-gradient(135deg, #1E3A5F, #1E40AF);
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 8px 0 8px 40px;
    font-size: 14px;
    color: #DBEAFE;
    line-height: 1.6;
    animation: fadeSlideIn 0.3s ease;
}
.fm-chat-bot {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.12);
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 8px 40px 8px 0;
    font-size: 14px;
    color: #B0C8E8;
    line-height: 1.6;
    animation: fadeSlideIn 0.3s ease;
}
.fm-section-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #2A4060;
    margin: 1.5rem 0 0.75rem;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(99,179,237,0.06);
}
.fm-stat-pill {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.1);
    border-radius: 10px;
    padding: 8px 14px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #8899BB;
}
.fm-stat-pill strong { color: #C8D8F0; font-weight: 600; }
.fm-budget-bar-wrap {
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.08);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 10px;
    transition: border-color 0.2s ease;
}
.fm-budget-bar-wrap:hover { border-color: rgba(99,179,237,0.18); }
.fm-budget-track {
    background: #1A2535;
    border-radius: 6px;
    height: 7px;
    margin: 10px 0 6px;
    overflow: hidden;
}
.fm-budget-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 1s cubic-bezier(0.4,0,0.2,1);
}
.fm-tx-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: #0F1825;
    border: 1px solid rgba(99,179,237,0.07);
    margin-bottom: 8px;
    transition: all 0.2s ease;
    animation: fadeSlideIn 0.35s ease both;
}
.fm-tx-row:hover {
    border-color: rgba(99,179,237,0.18);
    transform: translateX(3px);
}
.fm-tx-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}
.fm-sidebar-brand {
    padding: 20px 0 16px;
    text-align: center;
}
.fm-sidebar-brand .brand-icon {
    font-size: 36px;
    display: block;
    margin-bottom: 8px;
    animation: pulse 3s ease-in-out infinite;
}
.fm-sidebar-brand .brand-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #E2ECF8;
    letter-spacing: -0.01em;
}
.fm-sidebar-brand .brand-tag {
    font-size: 11px;
    color: #3B82F6;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── Animations ── */
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50%       { transform: scale(1.08); }
}
@keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
}
@keyframes countUp {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes scanline {
    0%   { top: -2px; }
    100% { top: 100%; }
}

/* ── Page entrance ── */
section.main > div {
    animation: fadeSlideIn 0.45s ease both;
}

/* ── Fraud score glow on critical ── */
.fraud-glow {
    animation: fraudPulse 2s ease-in-out infinite;
}
@keyframes fraudPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
    50%       { box-shadow: 0 0 20px 4px rgba(239,68,68,0.2); }
}

/* ── Plotly chart backgrounds ── */
.js-plotly-plot .plotly, .plot-container {
    border-radius: 16px;
}

/* ── Spinner text ── */
div[data-testid="stSpinner"] p {
    color: #4A6080 !important;
    font-size: 13px !important;
}

/* ── Tab-like quick buttons ── */
.fm-quick-btns {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 1rem;
}

/* ── Selectbox dropdown ── */
div[data-baseweb="select"] {
    background: #0F1825 !important;
}
div[data-baseweb="menu"] {
    background: #0F1825 !important;
    border: 1px solid rgba(99,179,237,0.15) !important;
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session State ───────────────────────────────────────────────
if "user_id"      not in st.session_state: st.session_state.user_id = 1
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "messages"     not in st.session_state: st.session_state.messages = []

# ─── Plotly dark theme (shared) ─────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#7A9ABF", size=12),
    xaxis=dict(
        gridcolor="rgba(99,179,237,0.06)",
        linecolor="rgba(99,179,237,0.1)",
        tickcolor="rgba(99,179,237,0.1)",
    ),
    yaxis=dict(
        gridcolor="rgba(99,179,237,0.06)",
        linecolor="rgba(99,179,237,0.1)",
        tickcolor="rgba(99,179,237,0.1)",
    ),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(
        bgcolor="#0F1825",
        bordercolor="rgba(99,179,237,0.3)",
        font=dict(color="#C8D8F0", size=13),
    ),
)

# ─── Category icons map ──────────────────────────────────────────
CAT_ICONS = {
    "Food": "🍜", "Transport": "🚗", "Shopping": "🛍️",
    "Entertainment": "🎬", "Bills": "⚡", "Health": "💊",
    "Education": "📚", "Salary": "💼", "Investment": "📈",
    "Other": "📦"
}

# ─── Helper functions ────────────────────────────────────────────
def get_transactions():
    try:
        r = requests.get(f"{API}/transactions/{st.session_state.user_id}", timeout=8)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def get_budgets():
    try:
        r = requests.get(f"{API}/budgets/{st.session_state.user_id}", timeout=8)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def risk_badge(risk):
    cls = {"CRITICAL":"fm-badge-critical","HIGH":"fm-badge-high",
           "MEDIUM":"fm-badge-medium","LOW":"fm-badge-low"}.get(risk,"fm-badge-low")
    dot = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(risk,"🟢")
    return f'<span class="fm-badge {cls}">{dot} {risk}</span>'

def budget_bar_color(pct):
    if pct > 90: return "linear-gradient(90deg,#EF4444,#F87171)"
    if pct > 70: return "linear-gradient(90deg,#F59E0B,#FCD34D)"
    return "linear-gradient(90deg,#3B82F6,#60A5FA)"

# ─── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="fm-sidebar-brand">
        <span class="brand-icon">💳</span>
        <div class="brand-name">FinMind AI</div>
        <div class="brand-tag">Personal CFO</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="fm-section-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("", [
        "📊  Dashboard",
        "➕  Add Transaction",
        "💰  Budget Manager",
        "🤖  AI Advisor",
        "🔍  Fraud Alerts"
    ], label_visibility="collapsed")

    st.markdown("---")

    # Live health check
    try:
        r = requests.get(f"{API}/health", timeout=3)
        if r.status_code == 200:
            st.markdown('<div class="fm-stat-pill">🟢 <strong>API</strong> connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="fm-stat-pill">🔴 <strong>API</strong> offline</div>', unsafe_allow_html=True)
    except:
        st.markdown('<div class="fm-stat-pill">🔴 <strong>API</strong> offline</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f'<div class="fm-stat-pill">👤 <strong>User</strong> #{st.session_state.user_id}</div>', unsafe_allow_html=True)
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
        st.markdown("""
        <div class="fm-card" style="text-align:center; padding:40px;">
            <div style="font-size:48px; margin-bottom:12px;">📭</div>
            <div style="color:#4A6080; font-size:15px;">No transactions yet. Add your first one to get started.</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(txs)
    df['date']   = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)

    income  = df[df['transaction_type']=='income']['amount'].sum()
    expense = df[df['transaction_type']=='expense']['amount'].sum()
    savings = income - expense
    savings_rate = (savings / income * 100) if income > 0 else 0
    flagged = df[df['is_flagged']==True].shape[0]

    # ── Metric row ──
    c1, c2, c3, c4 = st.columns(4)
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
            colors = ["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899","#06B6D4","#14B8A6"]
            fig = px.pie(
                exp_df, values='amount', names='category',
                color_discrete_sequence=colors,
                hole=0.52
            )
            fig.update_traces(
                textposition='outside',
                textinfo='label+percent',
                textfont=dict(color="#7A9ABF", size=11),
                marker=dict(line=dict(color='#080C14', width=2)),
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>"
            )
            fig.update_layout(
                **PLOTLY_LAYOUT,
                showlegend=False,
                height=300,
                annotations=[dict(
                    text=f"₹{expense:,.0f}<br><span style='font-size:10px'>total spent</span>",
                    x=0.5, y=0.5, font_size=14,
                    font_color="#E2ECF8", showarrow=False
                )]
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<p class="fm-section-label">Income vs expenses</p>', unsafe_allow_html=True)
        monthly = df.groupby([df['date'].dt.strftime('%b %Y'), 'transaction_type'])['amount'].sum().reset_index()
        monthly.columns = ['month','type','amount']
        if not monthly.empty:
            fig2 = px.bar(
                monthly, x='month', y='amount', color='type',
                barmode='group',
                color_discrete_map={'income':'#10B981','expense':'#3B82F6'},
            )
            fig2.update_traces(
                marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
            )
            fig2.update_layout(
                **PLOTLY_LAYOUT,
                height=300,
                legend=dict(
                    orientation="h", y=1.12, x=0,
                    font=dict(color="#7A9ABF", size=11),
                    bgcolor="rgba(0,0,0,0)"
                ),
                bargap=0.3, bargroupgap=0.1
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── Savings trend sparkline ──
    st.markdown('<p class="fm-section-label">Net savings trend</p>', unsafe_allow_html=True)
    daily = df.groupby([df['date'].dt.date, 'transaction_type'])['amount'].sum().unstack(fill_value=0).reset_index()
    if 'income' not in daily.columns: daily['income'] = 0
    if 'expense' not in daily.columns: daily['expense'] = 0
    daily['net'] = daily['income'] - daily['expense']
    daily['cumulative'] = daily['net'].cumsum()

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=daily['date'], y=daily['cumulative'],
        mode='lines',
        line=dict(color='#3B82F6', width=2.5, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(59,130,246,0.07)',
        hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
    ))
    fig3.update_layout(**PLOTLY_LAYOUT, height=160, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    # ── Recent transactions ──
    st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
    for tx in txs[:8]:
        icon = CAT_ICONS.get(tx['category'], "📦")
        is_fraud = tx['is_flagged']
        card_cls = "fm-tx-row fm-card-fraud" if is_fraud else "fm-tx-row"
        badge_html = risk_badge(tx['risk_level'])
        amt_color = "#F87171" if tx['transaction_type'] == 'expense' else "#34D399"
        amt_sign  = "-" if tx['transaction_type'] == 'expense' else "+"
        icon_bg   = "rgba(239,68,68,0.12)" if is_fraud else "rgba(59,130,246,0.1)"

        st.markdown(f"""
        <div class="{card_cls}">
            <div class="fm-tx-icon" style="background:{icon_bg};">{icon}</div>
            <div style="flex:1; min-width:0;">
                <div style="font-size:14px; font-weight:500; color:#C8D8F0; margin-bottom:2px;">
                    {tx['description']}
                </div>
                <div style="font-size:12px; color:#4A6080;">
                    {tx['category']} · {tx['date'][:10]}
                </div>
            </div>
            <div style="text-align:right; flex-shrink:0;">
                <div style="font-family:'Space Grotesk',sans-serif; font-size:15px; font-weight:600; color:{amt_color}; margin-bottom:4px;">
                    {amt_sign}₹{tx['amount']:,.0f}
                </div>
                {badge_html}
            </div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# PAGE 2 — ADD TRANSACTION
# ════════════════════════════════════════════════════════════════
elif "Add Transaction" in page:
    st.markdown('<p class="fm-page-title">Add Transaction</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Every transaction is scored for fraud in real time</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown('<p class="fm-section-label">Transaction details</p>', unsafe_allow_html=True)

        tx_type  = st.selectbox("Type", ["expense", "income"])
        desc     = st.text_input("Description", placeholder="e.g. Swiggy order, Netflix...")
        amount   = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        category = st.selectbox("Category", list(CAT_ICONS.keys()))

        if st.button("➕ Add Transaction", type="primary", use_container_width=True):
            if not desc.strip():
                st.error("Please enter a description.")
            else:
                payload = {
                    "user_id": st.session_state.user_id,
                    "description": desc, "amount": amount,
                    "category": category, "transaction_type": tx_type
                }
                with st.spinner("Scoring for fraud..."):
                    r = requests.post(f"{API}/transaction/add", json=payload)

                if r.status_code == 200:
                    result = r.json()
                    risk   = result['risk_level']
                    score  = result['fraud_score']

                    if result['is_flagged']:
                        st.markdown(f"""
                        <div class="fm-card fm-card-fraud fraud-glow">
                            <div style="font-size:13px; font-weight:600; color:#F87171; margin-bottom:6px;">
                                🚨 Fraud Alert Triggered
                            </div>
                            <div style="font-size:28px; font-family:'Space Grotesk',sans-serif;
                                        font-weight:700; color:#EF4444; margin-bottom:4px;">
                                {score:.1f}% risk
                            </div>
                            <div style="font-size:12px; color:#7A4040;">Risk level: {risk}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="fm-card fm-card-safe">
                            <div style="font-size:13px; font-weight:600; color:#34D399; margin-bottom:6px;">
                                ✓ Transaction looks safe
                            </div>
                            <div style="font-size:28px; font-family:'Space Grotesk',sans-serif;
                                        font-weight:700; color:#10B981; margin-bottom:4px;">
                                {score:.1f}% risk
                            </div>
                            <div style="font-size:12px; color:#2A5040;">Risk level: {risk}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Fraud score gauge
                    gauge_color = "#EF4444" if score > 60 else "#F59E0B" if score > 40 else "#10B981"
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=score,
                        number=dict(suffix="%", font=dict(color="#E2ECF8", size=32,
                                                           family="Space Grotesk, sans-serif")),
                        gauge=dict(
                            axis=dict(range=[0,100], tickcolor="#2A3F5F",
                                      tickfont=dict(color="#4A6080")),
                            bar=dict(color=gauge_color, thickness=0.18),
                            bgcolor="rgba(0,0,0,0)",
                            bordercolor="rgba(0,0,0,0)",
                            steps=[
                                dict(range=[0,40],  color="rgba(16,185,129,0.08)"),
                                dict(range=[40,70], color="rgba(245,158,11,0.08)"),
                                dict(range=[70,100],color="rgba(239,68,68,0.08)"),
                            ],
                            threshold=dict(
                                line=dict(color=gauge_color, width=2),
                                thickness=0.75, value=score
                            )
                        )
                    ))
                    fig.update_layout(
                        **PLOTLY_LAYOUT, height=220,
                        title=dict(text="Fraud Risk Score",
                                   font=dict(color="#4A6080", size=13), x=0.5)
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
        txs = get_transactions()
        if txs:
            for tx in txs[:10]:
                icon      = CAT_ICONS.get(tx['category'], "📦")
                is_fraud  = tx['is_flagged']
                amt_color = "#F87171" if tx['transaction_type']=='expense' else "#34D399"
                amt_sign  = "-" if tx['transaction_type']=='expense' else "+"
                icon_bg   = "rgba(239,68,68,0.12)" if is_fraud else "rgba(59,130,246,0.1)"

                st.markdown(f"""
                <div class="fm-tx-row">
                    <div class="fm-tx-icon" style="background:{icon_bg};">{icon}</div>
                    <div style="flex:1;">
                        <div style="font-size:13px; font-weight:500; color:#C8D8F0;">{tx['description']}</div>
                        <div style="font-size:11px; color:#3A5070;">{tx['category']}</div>
                    </div>
                    <div style="font-size:14px; font-weight:600; color:{amt_color}; font-family:'Space Grotesk',sans-serif;">
                        {amt_sign}₹{tx['amount']:,.0f}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="fm-card" style="color:#3A5070; text-align:center;">No transactions yet</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# PAGE 3 — BUDGET MANAGER
# ════════════════════════════════════════════════════════════════
elif "Budget" in page:
    st.markdown('<p class="fm-page-title">Budget Manager</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Set limits and track spending by category</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1.4], gap="large")
    month = datetime.now().strftime("%Y-%m")
    month_display = datetime.now().strftime("%B %Y")

    with col1:
        st.markdown('<p class="fm-section-label">Set monthly budget</p>', unsafe_allow_html=True)
        cat   = st.selectbox("Category", [
            "Food","Transport","Shopping","Entertainment",
            "Bills","Health","Education","Other"
        ])
        limit = st.number_input("Monthly limit (₹)", min_value=100.0, value=5000.0, step=500.0)

        if st.button("💾 Save Budget", type="primary", use_container_width=True):
            payload = {
                "user_id": st.session_state.user_id,
                "category": cat, "limit_amount": limit, "month": month
            }
            r = requests.post(f"{API}/budget/set", json=payload)
            if r.status_code == 200:
                st.success(f"Budget saved — ₹{limit:,.0f}/month for {cat}")

        # Budget summary stats
        budgets = get_budgets()
        if budgets:
            total_budgeted = sum(b['limit_amount'] for b in budgets)
            total_spent    = sum(b['spent_amount'] for b in budgets)
            over_budget    = [b for b in budgets if b['spent_amount'] > b['limit_amount']]

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<p class="fm-section-label">Summary</p>', unsafe_allow_html=True)
            st.metric("Total budgeted", f"₹{total_budgeted:,.0f}")
            st.metric("Total spent",    f"₹{total_spent:,.0f}", f"₹{total_budgeted-total_spent:,.0f} remaining")
            if over_budget:
                st.error(f"⚠️ {len(over_budget)} category over budget")

    with col2:
        st.markdown(f'<p class="fm-section-label">Budget status — {month_display}</p>', unsafe_allow_html=True)
        budgets = get_budgets()

        if not budgets:
            st.markdown("""
            <div class="fm-card" style="text-align:center; padding:32px;">
                <div style="font-size:36px; margin-bottom:10px;">📋</div>
                <div style="color:#3A5070; font-size:14px;">No budgets set yet. Create one on the left.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for b in sorted(budgets, key=lambda x: x['spent_amount']/x['limit_amount'] if x['limit_amount'] > 0 else 0, reverse=True):
                spent = b['spent_amount']
                lim   = b['limit_amount']
                pct   = min((spent / lim * 100), 100) if lim > 0 else 0
                remaining = max(lim - spent, 0)
                over      = spent > lim
                icon      = CAT_ICONS.get(b['category'], "📦")
                bar_color = budget_bar_color(pct)
                label_color = "#F87171" if pct > 90 else "#FCD34D" if pct > 70 else "#60A5FA"

                st.markdown(f"""
                <div class="fm-budget-bar-wrap">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:20px;">{icon}</span>
                            <span style="font-size:14px; font-weight:500; color:#C8D8F0;">{b['category']}</span>
                            {'<span style="font-size:11px; color:#F87171; font-weight:600; margin-left:6px;">OVER</span>' if over else ''}
                        </div>
                        <span style="font-family:\'Space Grotesk\',sans-serif; font-size:14px; font-weight:600; color:{label_color};">
                            {pct:.0f}%
                        </span>
                    </div>
                    <div class="fm-budget-track">
                        <div class="fm-budget-fill" style="width:{pct}%; background:{bar_color};"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; color:#3A5070;">
                        <span>₹{spent:,.0f} spent</span>
                        <span>₹{remaining:,.0f} left of ₹{lim:,.0f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# PAGE 4 — AI ADVISOR
# ════════════════════════════════════════════════════════════════
elif "AI Advisor" in page:
    st.markdown('<p class="fm-page-title">AI Financial Advisor</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Powered by Llama 3.3 70B — knows your real numbers</p>', unsafe_allow_html=True)

    # Quick question pills
    st.markdown('<p class="fm-section-label">Quick questions</p>', unsafe_allow_html=True)
    qc1, qc2, qc3, qc4 = st.columns(4)
    quick_q = None
    if qc1.button("📊 Financial health", use_container_width=True):
        quick_q = "Give me a summary of my financial health this month"
    if qc2.button("💡 Save more", use_container_width=True):
        quick_q = "How can I save more money based on my spending?"
    if qc3.button("🚨 Fraud risks", use_container_width=True):
        quick_q = "Are there any suspicious transactions I should know about?"
    if qc4.button("📈 Invest advice", use_container_width=True):
        quick_q = "Where should I invest my savings this month?"

    st.markdown("---")

    # Chat display
    if not st.session_state.messages:
        st.markdown("""
        <div class="fm-card" style="text-align:center; padding:32px 20px;">
            <div style="font-size:40px; margin-bottom:12px; animation: pulse 2s ease-in-out infinite; display:inline-block;">🤖</div>
            <div style="font-size:15px; font-weight:500; color:#7A9ABF; margin-bottom:6px;">FinMind AI is ready</div>
            <div style="font-size:13px; color:#3A5070; max-width:380px; margin:0 auto; line-height:1.6;">
                Ask me anything about your finances. I can see your actual income, expenses, and budget data.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.messages:
            if msg['role'] == 'user':
                st.markdown(
                    f'<div class="fm-chat-user">👤 &nbsp;{msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="fm-chat-bot">🤖 &nbsp;{msg["content"]}</div>',
                    unsafe_allow_html=True
                )

    # Chat input
    user_input = st.chat_input("Ask about your spending, savings, fraud alerts...")
    if quick_q:
        user_input = quick_q

    if user_input:
        st.session_state.messages.append({"role":"user","content":user_input})
        with st.spinner("FinMind AI is thinking..."):
            payload = {
                "user_id":      st.session_state.user_id,
                "message":      user_input,
                "chat_history": st.session_state.chat_history
            }
            r = requests.post(f"{API}/chat", json=payload)
            reply = r.json()['reply'] if r.status_code == 200 else "Sorry, I couldn't process that. Try again."

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
    st.markdown('<p class="fm-page-sub">Real-time ML scoring on every expense — powered by LightGBM (0.9588 AUC)</p>', unsafe_allow_html=True)

    txs = get_transactions()
    if not txs:
        st.markdown('<div class="fm-card" style="text-align:center; color:#3A5070; padding:32px;">No transactions to analyse.</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(txs)
    df['amount'] = df['amount'].astype(float)
    flagged_df = df[df['is_flagged']==True]
    expense_df = df[df['transaction_type']=='expense']

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total transactions", len(df))
    c2.metric("🚨 Flagged",         len(flagged_df), f"{len(flagged_df)/len(df)*100:.1f}% of total" if len(df) else "")
    c3.metric("💰 Amount at risk",  f"₹{flagged_df['amount'].sum():,.0f}" if len(flagged_df) else "₹0")
    avg_score = expense_df['fraud_score'].mean() if len(expense_df) else 0
    c4.metric("Avg fraud score",    f"{avg_score:.1f}%")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="fm-section-label">Fraud score distribution</p>', unsafe_allow_html=True)
        if len(expense_df):
            fig = px.histogram(
                expense_df, x='fraud_score', nbins=25,
                color_discrete_sequence=["#3B82F6"],
            )
            fig.update_traces(
                marker_line_width=0, opacity=0.85,
                hovertemplate="Score: %{x:.0f}%<br>Count: %{y}<extra></extra>"
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=260,
                              xaxis_title="Fraud score (%)", yaxis_title="Transactions")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<p class="fm-section-label">Risk level breakdown</p>', unsafe_allow_html=True)
        risk_counts = df[df['transaction_type']=='expense']['risk_level'].value_counts().reset_index()
        risk_counts.columns = ['level','count']
        if len(risk_counts):
            rcolors = {"LOW":"#10B981","MEDIUM":"#F59E0B","HIGH":"#F97316","CRITICAL":"#EF4444"}
            risk_counts['color'] = risk_counts['level'].map(rcolors)
            fig2 = px.bar(
                risk_counts, x='level', y='count',
                color='level',
                color_discrete_map=rcolors,
            )
            fig2.update_traces(marker_line_width=0,
                               hovertemplate="<b>%{x}</b><br>%{y} transactions<extra></extra>")
            fig2.update_layout(**PLOTLY_LAYOUT, height=260, showlegend=False,
                               xaxis_title="", yaxis_title="Count")
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Flagged transactions
    st.markdown('<p class="fm-section-label">Flagged transactions</p>', unsafe_allow_html=True)

    if flagged_df.empty:
        st.markdown("""
        <div class="fm-card" style="text-align:center; padding:32px;">
            <div style="font-size:40px; margin-bottom:10px;">✅</div>
            <div style="font-size:15px; font-weight:500; color:#34D399; margin-bottom:4px;">All clear</div>
            <div style="font-size:13px; color:#2A5040;">No fraudulent transactions detected</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for _, tx in flagged_df.iterrows():
            score = tx['fraud_score']
            risk  = tx['risk_level']
            score_color = "#F87171" if score > 60 else "#FCD34D"
            with st.expander(
                f"🔴  {tx['description']}  —  ₹{tx['amount']:,.0f}  |  {risk}  |  {score:.1f}% fraud score"
            ):
                ec1, ec2, ec3 = st.columns(3)
                ec1.metric("Fraud score",  f"{score:.1f}%")
                ec2.metric("Risk level",   risk)
                ec3.metric("Amount",       f"₹{tx['amount']:,.0f}")
                st.markdown(f"""
                <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:10px;">
                    <div class="fm-stat-pill">📂 <strong>{tx['category']}</strong></div>
                    <div class="fm-stat-pill">📅 <strong>{str(tx['date'])[:10]}</strong></div>
                </div>
                <div style="margin-top:14px; padding:12px 14px; background:rgba(239,68,68,0.06);
                            border-radius:10px; border:1px solid rgba(239,68,68,0.15);
                            font-size:13px; color:#F87171; line-height:1.55;">
                    ⚠️ This transaction was flagged by our LightGBM fraud model.
                    Review the amount and merchant carefully. If unrecognised, contact your bank immediately.
                </div>
                """, unsafe_allow_html=True)