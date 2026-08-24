import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import requests

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="FinMind AI",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS — Design System ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  /* Base surfaces — deep slate-navy, not flat black, with layered depth */
  --void: #0B0F1B;
  --surface: #121A2C;
  --surface-2: #182338;
  --surface-3: #202D48;
  /* Ink */
  --ink-1: #ECF1F8;
  --ink-2: #8996B4;
  --ink-3: #4C5878;
  /* Hairlines */
  --line: rgba(146, 168, 224, 0.10);
  --line-strong: rgba(146, 168, 224, 0.22);
  /* Signal — teal is the primary interactive color (deliberately not "SaaS blue") */
  --signal: #2FD9C4;
  --signal-rgb: 47, 217, 196;
  --signal-dim: rgba(47, 217, 196, 0.14);
  --signal-ring: rgba(47, 217, 196, 0.35);
  /* Semantic risk colors */
  --gain: #34D399;
  --loss: #FB7185;
  --crit: #F5455C;
  --crit-rgb: 245, 69, 92;
  --high: #FB923C;
  --high-rgb: 251, 146, 60;
  --med: #FBBF24;
  --low: #2FD9C4;
  --pulse-rgb: var(--signal-rgb);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; }
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none; }

/* Keep the header's structure (it hosts the sidebar collapse/expand
   control) but make it blend into the design instead of hiding it
   outright — hiding it entirely traps the sidebar in a collapsed
   state with no way to bring it back. */
header[data-testid="stHeader"] {
  background: transparent !important; box-shadow: none !important; height: 2.5rem;
}

/* Hide Streamlit's own toolbar (Deploy button, ⋮ menu, "Star" prompt)
   without touching the sidebar toggle, which lives in a separate
   element and must stay reachable. */
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stDeployButton"],
[data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] {
  display: none !important; visibility: hidden !important;
}

/* Force ONLY the sidebar collapse/expand control to stay visible
   against the dark theme — scoped narrowly so it doesn't also
   re-show the toolbar buttons hidden above. */
[data-testid="collapsedControl"],
button[data-testid="stSidebarCollapseButton"] {
  visibility: visible !important; opacity: 1 !important; color: var(--ink-1) !important;
  display: flex !important;
}
[data-testid="collapsedControl"] svg,
button[data-testid="stSidebarCollapseButton"] svg {
  fill: var(--ink-1) !important; color: var(--ink-1) !important;
}

.stApp {
  background:
    radial-gradient(ellipse 900px 600px at 12% -8%, rgba(47,217,196,0.055), transparent 60%),
    radial-gradient(ellipse 700px 500px at 100% 0%, rgba(90,120,220,0.045), transparent 55%),
    var(--void);
}

/* ── Signature motif: ambient "risk pulse" strip ────────────────
   A thin, always-present gradient line at the very top of the app —
   a control-room heartbeat. Calm teal by default; pages with active
   fraud alerts recolor it toward amber/red via an inline CSS var. */
.fm-pulse {
  position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 999999;
  background: linear-gradient(90deg,
    rgba(var(--pulse-rgb), 0),
    rgba(var(--pulse-rgb), 0.9),
    rgba(var(--pulse-rgb), 0));
  background-size: 200% 100%;
  animation: fm-pulse-sweep 5.5s ease-in-out infinite;
}
@keyframes fm-pulse-sweep {
  0%   { background-position: 0% 0%;   opacity: 0.5; }
  50%  { background-position: 100% 0%; opacity: 1; }
  100% { background-position: 200% 0%; opacity: 0.5; }
}

/* ── Orchestrated entrance — one considered moment, not scattered ── */
@keyframes fm-rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.fm-page-title, .fm-page-sub, .fm-card, .fm-tx-row,
div[data-testid="metric-container"], .fm-chat-user, .fm-chat-bot {
  animation: fm-rise 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* ── Sidebar ──────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--surface) 0%, var(--void) 100%) !important;
  border-right: 1px solid var(--line) !important;
}

/* ── Metric cards ─────────────────────────────────────────────── */
div[data-testid="metric-container"] {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px 22px !important;
  transition: transform 0.25s cubic-bezier(0.16,1,0.3,1), border-color 0.25s ease, box-shadow 0.25s ease;
}
div[data-testid="metric-container"]:hover {
  transform: translateY(-3px);
  border-color: var(--signal-ring);
  box-shadow: 0 12px 32px -12px rgba(47,217,196,0.18);
}
div[data-testid="metric-container"] label {
  color: var(--ink-3) !important; font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
  color: var(--ink-1) !important; font-family: 'JetBrains Mono', monospace !important;
  font-size: 26px !important; font-weight: 600 !important; letter-spacing: -0.01em !important;
}

/* ── Buttons ──────────────────────────────────────────────────── */
div[data-testid="stButton"] > button {
  background: linear-gradient(135deg, #1F9E8E 0%, #17877A 100%);
  color: #06251F; border: none; border-radius: 10px; padding: 10px 24px;
  font-weight: 600; font-size: 14px; letter-spacing: 0.01em;
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
  box-shadow: 0 4px 16px rgba(47,217,196,0.22);
}
div[data-testid="stButton"] > button:hover { transform: translateY(-1px); filter: brightness(1.08); box-shadow: 0 8px 24px rgba(47,217,196,0.32); }
div[data-testid="stButton"] > button:active { transform: translateY(0); }
div[data-testid="stButton"] > button:focus-visible {
  outline: 2px solid var(--signal); outline-offset: 2px;
}

/* ── Inputs ───────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input {
  background: var(--surface) !important; border: 1px solid var(--line) !important;
  border-radius: 10px !important; color: var(--ink-1) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stTextInput"] input:focus, div[data-testid="stNumberInput"] input:focus {
  border-color: var(--signal) !important; box-shadow: 0 0 0 3px var(--signal-dim) !important;
}
div[data-testid="stSelectbox"] > div {
  background: var(--surface) !important; border: 1px solid var(--line) !important; border-radius: 10px !important; color: var(--ink-1) !important;
}
div[data-testid="stChatInput"] textarea {
  background: var(--surface) !important; border: 1px solid var(--line-strong) !important;
  border-radius: 14px !important; color: var(--ink-1) !important;
}
div[data-testid="stExpander"] {
  background: var(--surface); border: 1px solid var(--line) !important; border-radius: 12px !important;
  transition: border-color 0.2s ease;
}
div[data-testid="stExpander"]:hover { border-color: var(--line-strong) !important; }

hr { border-color: var(--line) !important; margin: 1.5rem 0 !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb { background: var(--surface-3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--line-strong); }

/* ── Page furniture ───────────────────────────────────────────── */
.fm-page-title {
  font-family: 'Space Grotesk', sans-serif; font-size: 27px; font-weight: 700;
  color: var(--ink-1); letter-spacing: -0.02em; margin-bottom: 6px;
  position: relative; display: inline-block; padding-bottom: 10px;
}
.fm-page-title::after {
  content: ""; position: absolute; left: 0; bottom: 0; height: 3px; width: 42px;
  border-radius: 3px; background: linear-gradient(90deg, rgba(var(--signal-rgb), 1), rgba(var(--signal-rgb), 0));
}
.fm-page-sub { font-size: 13px; color: var(--ink-3); margin-bottom: 1.75rem; }

/* ── Cards ────────────────────────────────────────────────────── */
.fm-card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  padding: 20px 22px; margin-bottom: 12px;
  transition: transform 0.25s cubic-bezier(0.16,1,0.3,1), border-color 0.25s ease, box-shadow 0.25s ease;
}
.fm-card:hover { border-color: var(--line-strong); transform: translateY(-2px); box-shadow: 0 14px 32px -16px rgba(0,0,0,0.5); }

/* ── Risk badges — semantics kept intact, palette refined ───────── */
.fm-badge {
  display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 700;
  letter-spacing: 0.07em; padding: 3px 10px; border-radius: 20px; text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}
.fm-badge-critical { background: rgba(245,69,92,0.14); color: var(--crit); border: 1px solid rgba(245,69,92,0.28); }
.fm-badge-high     { background: rgba(251,146,60,0.14); color: var(--high); border: 1px solid rgba(251,146,60,0.28); }
.fm-badge-medium   { background: rgba(251,191,36,0.12); color: var(--med);  border: 1px solid rgba(251,191,36,0.24); }
.fm-badge-low      { background: rgba(47,217,196,0.13); color: var(--low);  border: 1px solid rgba(47,217,196,0.26); }

/* ── Chat ─────────────────────────────────────────────────────── */
.fm-chat-user {
  background: linear-gradient(135deg, #163B36, #1F9E8E22);
  border: 1px solid var(--line); border-radius: 18px 18px 4px 18px;
  padding: 12px 16px; margin: 8px 0 8px 40px; font-size: 14px; color: #D7FFF6; line-height: 1.6;
}
.fm-chat-bot {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 18px 18px 18px 4px; padding: 12px 16px; margin: 8px 40px 8px 0;
  font-size: 14px; color: var(--ink-2); line-height: 1.6;
}

.fm-section-label {
  font-size: 11px; font-weight: 700; letter-spacing: 0.11em; text-transform: uppercase;
  color: var(--ink-3); margin: 1.6rem 0 0.8rem; padding-bottom: 8px; border-bottom: 1px solid var(--line);
}

/* ── Transaction rows ─────────────────────────────────────────── */
.fm-tx-row {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px;
  background: var(--surface); border: 1px solid var(--line); margin-bottom: 8px;
  transition: transform 0.2s cubic-bezier(0.16,1,0.3,1), border-color 0.2s ease;
}
.fm-tx-row:hover { border-color: var(--line-strong); transform: translateX(4px); }
.fm-tx-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }

.fm-sidebar-brand { padding: 22px 0 18px; text-align: center; }

.fm-budget-track { background: var(--surface-3); border-radius: 6px; height: 7px; margin: 10px 0 6px; overflow: hidden; }
.fm-budget-fill { height: 100%; border-radius: 6px; transition: width 0.5s cubic-bezier(0.16,1,0.3,1); }

div[data-testid="stExpander"] summary { color: var(--loss) !important; font-size: 13px !important; }
.fm-auth-wrap { max-width: 380px; margin: 60px auto 0; }

/* ── Sidebar navigation ───────────────────────────────────────────
   Streamlit's st.radio renders plain HTML radio circles by default,
   which reads as an unstyled form rather than a nav menu. Hide the
   native control and style each label as a nav row, with the
   currently-selected page highlighted via :has(). */
section[data-testid="stSidebar"] div[role="radiogroup"] {
  gap: 3px; margin-top: 4px;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: 10px; margin: 0;
  border: 1px solid transparent;
  cursor: pointer; transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: var(--surface-2); transform: translateX(2px);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child,
section[data-testid="stSidebar"] div[role="radiogroup"] label [data-baseweb="radio"] {
  /* the native circle indicator */
  display: none;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
  font-size: 14px; font-weight: 500; color: var(--ink-2); margin: 0;
  transition: color 0.18s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: var(--signal-dim); border-color: var(--signal-ring);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
  color: var(--ink-1); font-weight: 600;
}

/* Numeric emphasis utility — precision instruments read in monospace */
.fm-mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }

/* ── Responsive tightening for narrow viewports ──────────────────── */
@media (max-width: 640px) {
  .fm-page-title { font-size: 22px; }
  .fm-card, .fm-tx-row { padding: 14px 16px; }
  .fm-chat-user, .fm-chat-bot { margin-left: 8px; margin-right: 8px; }
}
</style>
""", unsafe_allow_html=True)

# Signature ambient pulse strip — present on every page, teal by default.
st.markdown('<div class="fm-pulse"></div>', unsafe_allow_html=True)

# ─── Config ───────────────────────────────────────────────────────
try:
    API_URL = st.secrets.get("API_URL", os.getenv("API_URL", "http://127.0.0.1:8000"))
except Exception:
    API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# ─── Session State ───────────────────────────────────────────────
if "token" not in st.session_state: st.session_state.token = None
if "user" not in st.session_state: st.session_state.user = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "messages" not in st.session_state: st.session_state.messages = []

CATEGORY_MAP = {
    "Food": 0, "Transport": 1, "Shopping": 2, "Entertainment": 3,
    "Bills": 4, "Health": 5, "Education": 6, "Salary": 7, "Investment": 8, "Other": 9
}
CAT_ICONS = {
    "Food": "🍜", "Transport": "🚗", "Shopping": "🛍️", "Entertainment": "🎬",
    "Bills": "⚡", "Health": "💊", "Education": "📚", "Salary": "💼",
    "Investment": "📈", "Other": "📦"
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#7A9ABF", size=12),
    xaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    yaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(bgcolor="#0F1825", bordercolor="rgba(99,179,237,0.3)", font=dict(color="#C8D8F0", size=13)),
)


# ─── API client helpers ───────────────────────────────────────────
def _auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def _handle_response(resp):
    """Central place to catch expired/invalid tokens and force re-login."""
    if resp.status_code == 401:
        st.session_state.token = None
        st.session_state.user = None
        st.error("Your session expired. Please log in again.")
        st.rerun()
    return resp


def api_get(path, **kwargs):
    try:
        resp = requests.get(f"{API_URL}{path}", headers=_auth_headers(), timeout=15, **kwargs)
        return _handle_response(resp)
    except requests.exceptions.ConnectionError:
        st.error(f"Can't reach the backend at {API_URL}. Is it running?")
        st.stop()


def api_post(path, json=None, data=None, timeout=15, **kwargs):
    try:
        headers = _auth_headers()
        resp = requests.post(f"{API_URL}{path}", json=json, data=data, headers=headers, timeout=timeout, **kwargs)
        return _handle_response(resp)
    except requests.exceptions.ConnectionError:
        st.error(f"Can't reach the backend at {API_URL}. Is it running?")
        st.stop()
    except requests.exceptions.ReadTimeout:
        st.error("The server is taking longer than expected to respond. This can happen on the first AI Advisor message while the RAG model loads — please try again.")
        st.stop()


def api_delete(path, **kwargs):
    try:
        resp = requests.delete(f"{API_URL}{path}", headers=_auth_headers(), timeout=15, **kwargs)
        return _handle_response(resp)
    except requests.exceptions.ConnectionError:
        st.error(f"Can't reach the backend at {API_URL}. Is it running?")
        st.stop()


def get_transactions():
    r = api_get("/transactions/" + str(st.session_state.user["id"]))
    return r.json() if r.status_code == 200 else []


def get_budgets():
    r = api_get("/budgets/" + str(st.session_state.user["id"]))
    return r.json() if r.status_code == 200 else []


def add_transaction_api(description, amount, category, tx_type):
    return api_post("/transaction/add", json={
        "description": description, "amount": amount,
        "category": category, "transaction_type": tx_type,
    })


def delete_transaction_api(tx_id):
    api_delete(f"/transaction/{tx_id}")


def set_budget_api(category, limit_amount):
    month = datetime.now().strftime("%Y-%m")
    return api_post("/budget/set", json={
        "category": category, "limit_amount": limit_amount, "month": month,
    })


def get_advice(user_message, chat_history):
    r = api_post("/chat", json={"message": user_message, "chat_history": chat_history}, timeout=60)
    if r.status_code == 200:
        return r.json()["reply"]
    return f"Sorry, something went wrong talking to the advisor (status {r.status_code})."


# ─── Auth screen ───────────────────────────────────────────────────
def render_auth_screen():
    st.markdown('<div class="fm-auth-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="fm-sidebar-brand">
        <span style="font-size:40px;">💳</span>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;color:#E2ECF8;">FinMind AI</div>
        <div style="font-size:12px;color:#2FD9C4;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;">Personal CFO</div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username or email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
            if submitted:
                if not username or not password:
                    st.error("Please fill in both fields.")
                else:
                    r = api_post("/login", data={"username": username, "password": password})
                    if r.status_code == 200:
                        st.session_state.token = r.json()["access_token"]
                        me = api_get("/me")
                        st.session_state.user = me.json()
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password (min 8 characters)", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
            if submitted:
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    r = api_post("/register", json={
                        "username": new_username, "email": new_email, "password": new_password,
                    })
                    if r.status_code == 201:
                        st.success("Account created! Log in from the other tab.")
                    else:
                        detail = r.json().get("detail", "Registration failed.") if r.headers.get("content-type","").startswith("application/json") else "Registration failed."
                        st.error(detail)

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Gate the rest of the app behind auth ─────────────────────────
if not st.session_state.token or not st.session_state.user:
    render_auth_screen()
    st.stop()


# ─── Rendering helpers ─────────────────────────────────────────────
def set_pulse(critical_count=0, flagged_count=0):
    """
    Recolors the ambient signature pulse strip based on real fraud state:
    calm teal when clear, amber when flagged, red when critical alerts exist.
    """
    if critical_count > 0:
        rgb = "var(--crit-rgb)"
    elif flagged_count > 0:
        rgb = "var(--high-rgb)"
    else:
        rgb = "var(--signal-rgb)"
    st.markdown(f"<style>:root {{ --pulse-rgb: {rgb}; }}</style>", unsafe_allow_html=True)


def risk_badge(risk):
    cls = {"CRITICAL": "fm-badge-critical", "HIGH": "fm-badge-high",
           "MEDIUM": "fm-badge-medium", "LOW": "fm-badge-low"}.get(risk, "fm-badge-low")
    dot = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "🟢")
    return f'<span class="fm-badge {cls}">{dot} {risk}</span>'


def budget_bar_color(pct):
    if pct > 90: return "linear-gradient(90deg,#F5455C,#F87171)"
    if pct > 70: return "linear-gradient(90deg,#FBBF24,#FCD34D)"
    return "linear-gradient(90deg,#2FD9C4,#5EEAD4)"


def render_transaction_row(tx):
    icon = CAT_ICONS.get(tx['category'], "📦")
    is_fraud = tx.get('is_flagged', False)
    amt_color = "#F87171" if tx['transaction_type'] == 'expense' else "#34D399"
    amt_sign = "-" if tx['transaction_type'] == 'expense' else "+"
    icon_bg = "rgba(239,68,68,0.12)" if is_fraud else "rgba(59,130,246,0.1)"
    badge = risk_badge(tx.get('risk_level', 'LOW'))

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
            delete_transaction_api(tx['id'])
            st.rerun()


# ─── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="fm-sidebar-brand">
        <span style="font-size:36px;">💳</span>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:700;color:#E2ECF8;">FinMind AI</div>
        <div style="font-size:11px;color:#2FD9C4;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;">Personal CFO</div>
        <div style="font-size:12px;color:#5A7090;margin-top:6px;">👤 {st.session_state.user['username']}</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("", [
        "📊  Dashboard", "➕  Add Transaction",
        "💰  Budget Manager", "🤖  AI Advisor", "🔍  Fraud Alerts"
    ], label_visibility="collapsed")

    st.markdown("---")
    db_ok = True
    try:
        health = requests.get(f"{API_URL}/health", timeout=5)
        db_ok = health.status_code == 200
    except Exception:
        db_ok = False

    status_color = "#34D399" if db_ok else "#F5455C"
    status_text = "connected" if db_ok else "offline"
    st.markdown(f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#0F1825;border:1px solid rgba(99,179,237,0.1);border-radius:8px;font-size:11px;color:#5A7090;"><span style="width:8px;height:8px;border-radius:50%;background:{status_color};display:inline-block;"></span> <strong style="color:#C8D8F0;">API</strong> {status_text}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Log out", use_container_width=True):
        st.session_state.token = None
        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚠️ Danger zone"):
        st.caption("This permanently deletes all your transactions and resets budget spend to zero.")
        confirm = st.checkbox("I understand this cannot be undone")
        if st.button("🗑️ Reset all data", type="primary", use_container_width=True, disabled=not confirm):
            api_delete("/account/reset")
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
    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)

    income = df[df['transaction_type'] == 'income']['amount'].sum()
    expense = df[df['transaction_type'] == 'expense']['amount'].sum()
    savings = income - expense
    savings_rate = (savings / income * 100) if income > 0 else 0
    flagged = df[df['is_flagged'] == True].shape[0]
    critical = df[df['risk_level'] == 'CRITICAL'].shape[0]
    set_pulse(critical_count=critical, flagged_count=flagged)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Income", f"₹{income:,.0f}")
    c2.metric("💸 Total Expenses", f"₹{expense:,.0f}")
    c3.metric("🏦 Net Savings", f"₹{savings:,.0f}", f"{savings_rate:.1f}% rate")
    c4.metric("🚨 Fraud Alerts", flagged, "flagged" if flagged > 0 else "all clear")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="fm-section-label">Spending by category</p>', unsafe_allow_html=True)
        exp_df = df[df['transaction_type'] == 'expense'].groupby('category')['amount'].sum().reset_index()
        if not exp_df.empty:
            fig = px.pie(exp_df, values='amount', names='category',
                         color_discrete_sequence=["#2FD9C4", "#34D399", "#FBBF24", "#F5455C", "#7C9CF0", "#F472B6", "#38BDF8", "#2DD4A8"],
                         hole=0.52)
            fig.update_traces(textposition='outside', textinfo='label+percent',
                              marker=dict(line=dict(color='#080C14', width=2)),
                              hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>")
            fig.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                              margin=dict(l=10, r=10, t=30, b=10),
                              showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<p class="fm-section-label">Income vs expenses</p>', unsafe_allow_html=True)
        monthly = df.groupby([df['date'].dt.strftime('%b %Y'), 'transaction_type'])['amount'].sum().reset_index()
        monthly.columns = ['month', 'type', 'amount']
        if not monthly.empty:
            fig2 = px.bar(monthly, x='month', y='amount', color='type', barmode='group',
                          color_discrete_map={'income': '#34D399', 'expense': '#2FD9C4'})
            fig2.update_traces(marker_line_width=0,
                               hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>")
            fig2.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                               margin=dict(l=10, r=10, t=30, b=10),
                               height=300, legend=dict(orientation="h", y=1.12,
                               bgcolor="rgba(0,0,0,0)", font=dict(color="#7A9ABF")))
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<p class="fm-section-label">Net savings trend</p>', unsafe_allow_html=True)
    daily = df.groupby([df['date'].dt.date, 'transaction_type'])['amount'].sum().unstack(fill_value=0).reset_index()
    if 'income' not in daily.columns: daily['income'] = 0
    if 'expense' not in daily.columns: daily['expense'] = 0
    daily['cumulative'] = (daily['income'] - daily['expense']).cumsum()
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=daily['date'], y=daily['cumulative'], mode='lines',
        line=dict(color='#2FD9C4', width=2.5, shape='spline'),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.07)',
        hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
    ))
    fig3.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                       margin=dict(l=10, r=10, t=10, b=10), height=160)
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
    for tx in txs[:8]:
        render_transaction_row(tx)


# ════════════════════════════════════════════════════════════════
# PAGE 2 — ADD TRANSACTION
# ════════════════════════════════════════════════════════════════
elif "Add Transaction" in page:
    st.markdown('<p class="fm-page-title">Add Transaction</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Every expense is scored for fraud in real time</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown('<p class="fm-section-label">Transaction details</p>', unsafe_allow_html=True)
        tx_type = st.selectbox("Type", ["expense", "income"])
        desc = st.text_input("Description", placeholder="e.g. Swiggy order...")
        amount = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        category = st.selectbox("Category", list(CAT_ICONS.keys()))

        if st.button("➕ Add Transaction", type="primary", use_container_width=True):
            if not desc.strip():
                st.error("Please enter a description.")
            else:
                r = add_transaction_api(desc, amount, category, tx_type)
                if r.status_code != 200:
                    detail = r.json().get("detail", "Failed to add transaction.")
                    st.error(f"Error: {detail}")
                else:
                    result = r.json()
                    fraud_score = result["fraud_score"]
                    risk_level = result["risk_level"]
                    is_flagged = result["is_flagged"]

                    if is_flagged:
                        st.error(f"🚨 Fraud Alert! Risk: {risk_level} | Score: {fraud_score:.1f}%")
                    else:
                        st.success(f"✓ Transaction added! Risk: {risk_level} | Score: {fraud_score:.1f}%")

                    fig = go.Figure(go.Indicator(
                        mode="gauge+number", value=fraud_score,
                        number=dict(suffix="%", font=dict(color="#E2ECF8", size=32, family="Space Grotesk, sans-serif")),
                        gauge=dict(
                            axis=dict(range=[0, 100], tickcolor="#2A3F5F", tickfont=dict(color="#4A6080")),
                            bar=dict(color="#F5455C" if fraud_score > 60 else "#34D399", thickness=0.18),
                            bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
                            steps=[
                                dict(range=[0, 40], color="rgba(16,185,129,0.08)"),
                                dict(range=[40, 70], color="rgba(245,158,11,0.08)"),
                                dict(range=[70, 100], color="rgba(239,68,68,0.08)"),
                            ]
                        )
                    ))
                    fig.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                                      margin=dict(l=10, r=10, t=30, b=10), height=220,
                                      title=dict(text="Fraud Risk Score", font=dict(color="#4A6080", size=13), x=0.5))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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

    col1, col2 = st.columns([1, 1.4], gap="large")
    month_display = datetime.now().strftime("%B %Y")

    with col1:
        st.markdown('<p class="fm-section-label">Set monthly budget</p>', unsafe_allow_html=True)
        cat = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Education", "Other"])
        limit = st.number_input("Monthly limit (₹)", min_value=100.0, value=5000.0, step=500.0)

        if st.button("💾 Save Budget", type="primary", use_container_width=True):
            r = set_budget_api(cat, limit)
            if r.status_code == 200:
                st.success(f"Budget saved — ₹{limit:,.0f}/month for {cat}")
            else:
                st.error("Failed to save budget.")

    with col2:
        st.markdown(f'<p class="fm-section-label">Budget status — {month_display}</p>', unsafe_allow_html=True)
        budgets = get_budgets()

        if not budgets:
            st.markdown('<div class="fm-card" style="text-align:center;padding:32px;color:#3A5070;">No budgets set yet.</div>', unsafe_allow_html=True)
        else:
            for b in sorted(budgets, key=lambda x: x['spent_amount'] / x['limit_amount'] if x['limit_amount'] > 0 else 0, reverse=True):
                spent = b['spent_amount']
                lim = b['limit_amount']
                pct = min((spent / lim * 100), 100) if lim > 0 else 0
                icon = CAT_ICONS.get(b['category'], "📦")
                color = budget_bar_color(pct)
                label_color = "#F87171" if pct > 90 else "#FCD34D" if pct > 70 else "#5EEAD4"
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

    qc1, qc2, qc3, qc4 = st.columns(4)
    quick_q = None
    if qc1.button("📊 Financial health", use_container_width=True): quick_q = "Give me a summary of my financial health"
    if qc2.button("💡 Save more", use_container_width=True): quick_q = "How can I save more based on my spending?"
    if qc3.button("🚨 Fraud risks", use_container_width=True): quick_q = "Any suspicious transactions I should know about?"
    if qc4.button("📈 Invest advice", use_container_width=True): quick_q = "Where should I invest my savings?"

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
            if msg['role'] == 'user':
                st.markdown(f'<div class="fm-chat-user">👤 &nbsp;{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="fm-chat-bot">🤖 &nbsp;{msg["content"]}</div>', unsafe_allow_html=True)

    user_input = st.chat_input("Ask about your spending, savings, fraud alerts...")
    if quick_q: user_input = quick_q

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("FinMind AI is thinking..."):
            reply = get_advice(user_input, st.session_state.chat_history)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
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
    st.markdown('<p class="fm-page-sub">Real-time ML scoring on every expense</p>', unsafe_allow_html=True)

    txs = get_transactions()
    if not txs:
        st.markdown('<div class="fm-card" style="text-align:center;color:#3A5070;padding:32px;">No transactions yet.</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(txs)
    df['amount'] = df['amount'].astype(float)
    flagged_df = df[df['is_flagged'] == True]
    expense_df = df[df['transaction_type'] == 'expense']
    critical_df = df[df['risk_level'] == 'CRITICAL']
    set_pulse(critical_count=len(critical_df), flagged_count=len(flagged_df))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total transactions", len(df))
    c2.metric("🚨 Flagged", len(flagged_df), f"{len(flagged_df)/len(df)*100:.1f}% of total" if len(df) else "")
    c3.metric("💰 Amount at risk", f"₹{flagged_df['amount'].sum():,.0f}" if len(flagged_df) else "₹0")
    avg_score = expense_df['fraud_score'].mean() if len(expense_df) else 0
    c4.metric("Avg fraud score", f"{avg_score:.1f}%")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="fm-section-label">Fraud score distribution</p>', unsafe_allow_html=True)
        if len(expense_df):
            fig = px.histogram(expense_df, x='fraud_score', nbins=25, color_discrete_sequence=["#2FD9C4"])
            fig.update_traces(marker_line_width=0, opacity=0.85,
                              hovertemplate="Score: %{x:.0f}%<br>Count: %{y}<extra></extra>")
            fig.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                              margin=dict(l=10, r=10, t=30, b=10), height=260,
                              xaxis_title="Fraud score (%)", yaxis_title="Transactions")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<p class="fm-section-label">Risk level breakdown</p>', unsafe_allow_html=True)
        risk_counts = df[df['transaction_type'] == 'expense']['risk_level'].value_counts().reset_index()
        risk_counts.columns = ['level', 'count']
        if len(risk_counts):
            rcolors = {"LOW": "#34D399", "MEDIUM": "#FBBF24", "HIGH": "#FB923C", "CRITICAL": "#F5455C"}
            fig2 = px.bar(risk_counts, x='level', y='count', color='level', color_discrete_map=rcolors)
            fig2.update_traces(marker_line_width=0,
                               hovertemplate="<b>%{x}</b><br>%{y} transactions<extra></extra>")
            fig2.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k != 'margin'},
                               margin=dict(l=10, r=10, t=30, b=10), height=260, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<p class="fm-section-label">Flagged transactions</p>', unsafe_allow_html=True)
    if flagged_df.empty:
        st.markdown("""<div class="fm-card" style="text-align:center;padding:32px;">
            <div style="font-size:40px;margin-bottom:10px;">✅</div>
            <div style="font-size:15px;font-weight:500;color:#34D399;">All clear — no fraud detected</div>
        </div>""", unsafe_allow_html=True)
    else:
        for _, tx in flagged_df.iterrows():
            with st.expander(f"🔴 {tx['description']} — ₹{tx['amount']:,.0f} | {tx['risk_level']} | {tx['fraud_score']:.1f}%"):
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.metric("Fraud score", f"{tx['fraud_score']:.1f}%")
                ec2.metric("Risk level", tx['risk_level'])
                ec3.metric("Amount", f"₹{tx['amount']:,.0f}")
                with ec4:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"del_fraud_{tx['id']}", use_container_width=True):
                        delete_transaction_api(tx['id'])
                        st.rerun()
                st.markdown(f'<div style="margin-top:10px;padding:12px;background:rgba(239,68,68,0.06);border-radius:10px;border:1px solid rgba(239,68,68,0.15);font-size:13px;color:#F87171;">⚠️ Flagged by the fraud model. Review this transaction carefully.</div>', unsafe_allow_html=True)