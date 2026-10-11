"""
app.py — FinMind AI Streamlit frontend (v3).

Talks to the API only through ApiClient (api_client.py): short-lived access token in memory,
rotating refresh cookie in the session's cookie jar, automatic refresh-and-retry on 401.
Every piece of user- or model-controlled text is HTML-escaped before it is rendered with
unsafe_allow_html (descriptions, usernames, chat replies, SQL traces).
"""
from __future__ import annotations

import html
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from api_client import ApiClient, ApiError, ApiUnreachable, SessionExpired

st.set_page_config(page_title="FinMind AI", page_icon="💳", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.markdown('<div class="fm-pulse"></div>', unsafe_allow_html=True)  # ambient risk-pulse strip

try:
    API_URL = st.secrets.get("API_URL", os.getenv("API_URL", "http://127.0.0.1:8000"))
except Exception:
    API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
APP_TZ = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

esc = html.escape
CAT_ICONS = {
    "Food": "🍜", "Transport": "🚗", "Shopping": "🛍️", "Entertainment": "🎬", "Bills": "⚡",
    "Health": "💊", "Education": "📚", "Salary": "💼", "Investment": "📈", "Other": "📦",
}
BUDGET_CATEGORIES = ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Education", "Other"]
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#7A9ABF", size=12),
    xaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    yaxis=dict(gridcolor="rgba(99,179,237,0.06)", linecolor="rgba(99,179,237,0.1)"),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(bgcolor="#0F1825", bordercolor="rgba(99,179,237,0.3)", font=dict(color="#C8D8F0", size=13)),
)
ss = st.session_state
ss.setdefault("messages", [])
if "api" not in ss:
    ss.api = ApiClient(API_URL)
api: ApiClient = ss.api


def layout(**over):
    return {**{k: v for k, v in PLOTLY_LAYOUT.items() if k not in over}, **over}


def guarded(fn, *args, **kwargs):
    """Run an API call; turn an expired session into a login screen and a dead API into a message."""
    try:
        return fn(*args, **kwargs)
    except SessionExpired:
        ss.flash = "Your session expired. Please log in again."
        ss.messages = []
        st.rerun()
    except ApiUnreachable as e:
        st.error(str(e))
        st.stop()


# ═════════════════════════ Auth screen ═════════════════════════
def render_auth_screen() -> None:
    st.markdown('<div class="fm-auth-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="fm-sidebar-brand"><span style="font-size:40px;">💳</span>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;color:#E2ECF8;">FinMind AI</div>
      <div style="font-size:12px;color:#2FD9C4;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;">Personal CFO</div>
    </div>""", unsafe_allow_html=True)
    if ss.pop("flash", None):
        st.warning("Your session expired. Please log in again.")
    tab_login, tab_register = st.tabs(["Log in", "Create account"])
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username or email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", width="stretch"):
                if not username or not password:
                    st.error("Please fill in both fields.")
                else:
                    try:
                        api.login(username.strip(), password)
                        st.rerun()
                    except ApiError as e:
                        st.error("Too many failed attempts. Try again in a few minutes." if e.status == 429
                                 else "Incorrect username or password.")
                    except ApiUnreachable as e:
                        st.error(str(e))
    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username", help="3-50 characters: letters, numbers, . _ -")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password (min 8 characters)", type="password")
            if st.form_submit_button("Create account", width="stretch"):
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        api.register(new_username.strip(), new_email.strip(), new_password)
                        st.success("Account created! Log in from the other tab.")
                    except ApiError as e:
                        st.error(e.detail)
                    except ApiUnreachable as e:
                        st.error(str(e))
    st.markdown("</div>", unsafe_allow_html=True)


if not api.authenticated:
    render_auth_screen()
    st.stop()


# ═════════════════════════ Rendering helpers ═════════════════════════
def set_pulse(critical: int = 0, flagged: int = 0) -> None:
    rgb = "var(--crit-rgb)" if critical else "var(--high-rgb)" if flagged else "var(--signal-rgb)"
    st.markdown(f"<style>:root {{ --pulse-rgb: {rgb}; }}</style>", unsafe_allow_html=True)


def risk_badge(risk: str) -> str:
    cls = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium"}.get(risk, "low")
    dot = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(risk, "🟢")
    return f'<span class="fm-badge fm-badge-{cls}">{dot} {esc(risk)}</span>'


def budget_bar_color(pct: float) -> str:
    if pct > 90:
        return "linear-gradient(90deg,#F5455C,#F87171)"
    if pct > 70:
        return "linear-gradient(90deg,#FBBF24,#FCD34D)"
    return "linear-gradient(90deg,#2FD9C4,#5EEAD4)"


def to_local(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).dt.tz_convert(APP_TZ).dt.tz_localize(None)


def fmt_num(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def render_risk_factors(factors: list[dict] | None) -> None:
    """Top SHAP factors for a scored transaction (log-odds contributions)."""
    if not factors:
        st.caption("No risk factors recorded (income is not scored).")
        return
    for f in factors:
        up = f["direction"] == "increases_risk"
        value = "" if f["feature"].startswith("cat_") else f" = {fmt_num(f['value'])}"
        st.markdown(
            f'<div class="fm-factor fm-factor-{"up" if up else "down"}"><span>{esc(f["label"])}{esc(value)}</span>'
            f'<b>{f["contribution"]:+.2f} {"▲" if up else "▼"}</b></div>', unsafe_allow_html=True)
    st.caption("▲ pushes the score toward fraud, ▼ away from it (TreeSHAP contribution, log-odds).")


def render_transaction_row(tx: dict) -> None:
    icon = CAT_ICONS.get(tx["category"], "📦")
    expense = tx["transaction_type"] == "expense"
    icon_bg = "rgba(239,68,68,0.12)" if tx.get("is_flagged") else "rgba(59,130,246,0.1)"
    col_tx, col_del = st.columns([12, 1])
    with col_tx:
        st.markdown(f"""
        <div class="fm-tx-row"><div class="fm-tx-icon" style="background:{icon_bg};">{icon}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:14px;font-weight:500;color:#C8D8F0;">{esc(tx['description'])}</div>
            <div style="font-size:12px;color:#4A6080;">{esc(tx['category'])} · {esc(str(tx['occurred_at'])[:10])}</div></div>
          <div style="text-align:right;flex-shrink:0;">
            <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:600;color:{'#F87171' if expense else '#34D399'};margin-bottom:4px;">
              {'-' if expense else '+'}₹{tx['amount']:,.0f}</div>{risk_badge(tx.get('risk_level', 'LOW'))}</div></div>""",
            unsafe_allow_html=True)
    with col_del:
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️", key=f"del_{tx['id']}", help="Delete this transaction"):
            guarded(api.delete, f"/transaction/{tx['id']}")
            st.rerun()


# ═════════════════════════ Sidebar ═════════════════════════
PAGES = ["📊  Dashboard", "➕  Add Transaction", "💰  Budget Manager", "🤖  AI Advisor", "🔍  Fraud Alerts", "📈  Insights"]
with st.sidebar:
    st.markdown(f"""
    <div class="fm-sidebar-brand"><span style="font-size:36px;">💳</span>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:700;color:#E2ECF8;">FinMind AI</div>
      <div style="font-size:11px;color:#2FD9C4;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;">Personal CFO</div>
      <div style="font-size:12px;color:#5A7090;margin-top:6px;">👤 {esc(api.user['username'])}</div></div>""", unsafe_allow_html=True)
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.markdown("---")
    try:
        api_ok = api.get("/health", timeout=5).status_code == 200
    except (ApiUnreachable, SessionExpired):
        api_ok = False
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#0F1825;border:1px solid rgba(99,179,237,0.1);'
        f'border-radius:8px;font-size:11px;color:#5A7090;"><span style="width:8px;height:8px;border-radius:50%;'
        f'background:{"#34D399" if api_ok else "#F5455C"};display:inline-block;"></span> <strong style="color:#C8D8F0;">API</strong> '
        f'{"connected" if api_ok else "offline"}</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Log out", width="stretch"):
        api.logout()           # revokes the access token and the refresh family on the server
        ss.messages = []
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚠️ Danger zone"):
        st.caption("Permanently deletes all your transactions and resets budget spend to zero.")
        confirm = st.checkbox("I understand this cannot be undone")
        if st.button("🗑️ Reset all data", type="primary", width="stretch", disabled=not confirm):
            guarded(api.delete, "/account/reset")
            st.success("All data cleared!")
            st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("LightGBM + ONNX · LLM advisor · pgvector")


def empty_card(icon: str, text: str) -> None:
    st.markdown(f'<div class="fm-card" style="text-align:center;padding:36px;"><div style="font-size:44px;margin-bottom:10px;">{icon}</div>'
                f'<div style="color:#4A6080;font-size:15px;">{esc(text)}</div></div>', unsafe_allow_html=True)


# ═════════════════════════ PAGE: Dashboard ═════════════════════════
if "Dashboard" in page:
    st.markdown('<p class="fm-page-title">Financial Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Your money at a glance — updated in real time</p>', unsafe_allow_html=True)
    txs = guarded(api.all_transactions)
    if not txs:
        empty_card("📭", "No transactions yet. Add your first one!")
        st.stop()
    df = pd.DataFrame(txs)
    df["occurred_at"] = to_local(df["occurred_at"])
    income = df.loc[df.transaction_type == "income", "amount"].sum()
    expense = df.loc[df.transaction_type == "expense", "amount"].sum()
    savings, rate = income - expense, ((income - expense) / income * 100 if income > 0 else 0)
    flagged, critical = int(df.is_flagged.sum()), int((df.risk_level == "CRITICAL").sum())
    set_pulse(critical, flagged)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Income", f"₹{income:,.0f}")
    c2.metric("💸 Total Expenses", f"₹{expense:,.0f}")
    c3.metric("🏦 Net Savings", f"₹{savings:,.0f}", f"{rate:.1f}% rate")
    c4.metric("🚨 Fraud Alerts", flagged, "flagged" if flagged else "all clear")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="fm-section-label">Spending by category</p>', unsafe_allow_html=True)
        exp_df = df[df.transaction_type == "expense"].groupby("category")["amount"].sum().reset_index()
        if not exp_df.empty:
            fig = px.pie(exp_df, values="amount", names="category", hole=0.52,
                         color_discrete_sequence=["#2FD9C4", "#34D399", "#FBBF24", "#F5455C", "#7C9CF0", "#F472B6", "#38BDF8", "#2DD4A8"])
            fig.update_traces(textposition="outside", textinfo="label+percent", marker=dict(line=dict(color="#080C14", width=2)),
                              hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>")
            fig.update_layout(**layout(showlegend=False, height=300))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with col2:
        st.markdown('<p class="fm-section-label">Income vs expenses</p>', unsafe_allow_html=True)
        monthly = df.groupby([df.occurred_at.dt.strftime("%b %Y"), "transaction_type"])["amount"].sum().reset_index()
        monthly.columns = ["month", "type", "amount"]
        fig2 = px.bar(monthly, x="month", y="amount", color="type", barmode="group",
                      color_discrete_map={"income": "#34D399", "expense": "#2FD9C4"})
        fig2.update_traces(marker_line_width=0, hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>")
        fig2.update_layout(**layout(height=300, legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)", font=dict(color="#7A9ABF"))))
        st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
    st.markdown('<p class="fm-section-label">Net savings trend</p>', unsafe_allow_html=True)
    daily = df.groupby([df.occurred_at.dt.date, "transaction_type"])["amount"].sum().unstack(fill_value=0).reset_index()
    for col in ("income", "expense"):
        if col not in daily:
            daily[col] = 0
    daily["cumulative"] = (daily["income"] - daily["expense"]).cumsum()
    fig3 = go.Figure(go.Scatter(x=daily["occurred_at"], y=daily["cumulative"], mode="lines", line=dict(color="#2FD9C4", width=2.5, shape="spline"),
                                fill="tozeroy", fillcolor="rgba(47,217,196,0.07)", hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
    fig3.update_layout(**layout(margin=dict(l=10, r=10, t=10, b=10), height=160))
    st.plotly_chart(fig3, width="stretch", config={"displayModeBar": False})
    st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
    for tx in txs[:8]:
        render_transaction_row(tx)


# ═════════════════════════ PAGE: Add Transaction ═════════════════════════
elif "Add Transaction" in page:
    st.markdown('<p class="fm-page-title">Add Transaction</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Every expense is scored for fraud in real time, with the reasons why</p>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<p class="fm-section-label">Transaction details</p>', unsafe_allow_html=True)
        tx_type = st.selectbox("Type", ["expense", "income"])
        desc = st.text_input("Description", placeholder="e.g. Swiggy order...", max_chars=200)
        merchant = st.text_input("Merchant (optional)", max_chars=120)
        amount = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        category = st.selectbox("Category", list(CAT_ICONS))
        if st.button("➕ Add Transaction", type="primary", width="stretch"):
            if not desc.strip():
                st.error("Please enter a description.")
            else:
                payload = {"description": desc.strip(), "amount": amount, "category": category, "transaction_type": tx_type}
                if merchant.strip():
                    payload["merchant"] = merchant.strip()
                r = guarded(api.post, "/transaction/add", json=payload)
                if r.status_code != 200:
                    st.error(f"Error: {api.error_detail(r)}")
                else:
                    res = r.json()
                    score, level = res["fraud_score"], res["risk_level"]
                    (st.error if res["is_flagged"] else st.success)(
                        f"{'🚨 Fraud alert!' if res['is_flagged'] else '✓ Transaction added!'} Risk: {level} | Score: {score:.1f}%")
                    if res.get("degraded"):
                        st.warning("Velocity features were unavailable, so this score used neutral defaults and may understate risk.")
                    if tx_type == "expense":
                        bar = {"CRITICAL": "#F5455C", "HIGH": "#FB923C", "MEDIUM": "#FBBF24"}.get(level, "#34D399")
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number", value=score, number=dict(suffix="%", font=dict(color="#E2ECF8", size=32, family="Space Grotesk, sans-serif")),
                            gauge=dict(axis=dict(range=[0, 100], tickcolor="#2A3F5F", tickfont=dict(color="#4A6080")), bar=dict(color=bar, thickness=0.18),
                                       bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)")))
                        fig.update_layout(**layout(height=200, title=dict(text="Fraud risk (calibrated probability)", font=dict(color="#4A6080", size=13), x=0.5)))
                        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
                        st.markdown('<p class="fm-section-label">Why this score</p>', unsafe_allow_html=True)
                        render_risk_factors(res["risk_factors"])
    with col2:
        st.markdown('<p class="fm-section-label">Recent transactions</p>', unsafe_allow_html=True)
        r = guarded(api.get, "/transactions/me", params={"limit": 10})
        for tx in (r.json() if r.status_code == 200 else []):
            render_transaction_row(tx)


# ═════════════════════════ PAGE: Budget Manager ═════════════════════════
elif "Budget" in page:
    st.markdown('<p class="fm-page-title">Budget Manager</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Set limits and track spending by category</p>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1.4], gap="large")
    with col1:
        st.markdown('<p class="fm-section-label">Set monthly budget</p>', unsafe_allow_html=True)
        cat = st.selectbox("Category", BUDGET_CATEGORIES)
        limit = st.number_input("Monthly limit (₹)", min_value=100.0, value=5000.0, step=500.0)
        if st.button("💾 Save Budget", type="primary", width="stretch"):
            r = guarded(api.post, "/budget/set", json={"category": cat, "limit_amount": limit})
            st.success(f"Budget saved — ₹{limit:,.0f}/month for {cat}") if r.status_code == 200 else st.error(api.error_detail(r))
    with col2:
        st.markdown(f'<p class="fm-section-label">Budget status — {datetime.now().strftime("%B %Y")}</p>', unsafe_allow_html=True)
        r = guarded(api.get, "/budgets/me")
        budgets = r.json() if r.status_code == 200 else []
        if not budgets:
            empty_card("💰", "No budgets set yet.")
        for b in budgets:  # already sorted by utilisation by the API
            pct = min(b["percent_used"], 100)
            label_color = "#F87171" if pct > 90 else "#FCD34D" if pct > 70 else "#5EEAD4"
            st.markdown(f"""
            <div class="fm-card" style="padding:14px 16px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:20px;">{CAT_ICONS.get(b['category'], '📦')}</span>
                  <span style="font-size:14px;font-weight:500;color:#C8D8F0;">{esc(b['category'])}</span></div>
                <span style="font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:600;color:{label_color};">{b['percent_used']:.0f}%</span></div>
              <div class="fm-budget-track"><div class="fm-budget-fill" style="width:{pct}%;background:{budget_bar_color(pct)};"></div></div>
              <div style="display:flex;justify-content:space-between;font-size:12px;color:#3A5070;">
                <span>₹{b['spent_amount']:,.0f} spent</span><span>₹{max(b['limit_amount'] - b['spent_amount'], 0):,.0f} left of ₹{b['limit_amount']:,.0f}</span></div></div>""",
                unsafe_allow_html=True)


# ═════════════════════════ PAGE: AI Advisor ═════════════════════════
elif "AI Advisor" in page:
    st.markdown('<p class="fm-page-title">AI Financial Advisor</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Exact numbers come from SQL on your ledger; fuzzy lookups use semantic search</p>', unsafe_allow_html=True)
    qc = st.columns(4)
    quick = None
    for col, (label, q) in zip(qc, [("📊 Last month's food", "How much did I spend on Food last month?"),
                                    ("🏋️ Gym & fitness", "Find my transactions related to gym or fitness and tell me the total."),
                                    ("🚨 Fraud risks", "Any suspicious transactions I should know about?"),
                                    ("🏆 Top spending", "What are my top 3 spending categories?")]):
        if col.button(label, width="stretch"):
            quick = q
    st.markdown("---")
    if not ss.messages:
        st.markdown('<div class="fm-card" style="text-align:center;padding:32px 20px;"><div style="font-size:40px;margin-bottom:12px;">🤖</div>'
                    '<div style="font-size:15px;font-weight:500;color:#7A9ABF;margin-bottom:6px;">FinMind AI is ready</div>'
                    '<div style="font-size:13px;color:#3A5070;max-width:420px;margin:0 auto;line-height:1.6;">Ask about totals, dates, budgets or '
                    'fuzzy things like "subscriptions". I show the queries I ran so you can verify every number.</div></div>', unsafe_allow_html=True)
    for m in ss.messages:
        if m["role"] == "user":
            st.markdown(f'<div class="fm-chat-user">👤 &nbsp;{esc(m["content"])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="fm-chat-bot">🤖 &nbsp;{esc(m["content"])}</div>', unsafe_allow_html=True)
            if m.get("trace"):
                with st.expander(f"🔎 How I got this ({len(m['trace'])} step{'s' if len(m['trace']) != 1 else ''})"):
                    for t in m["trace"]:
                        icon = "🗄️ SQL" if t["tool"] == "run_sql_query" else "🧭 Semantic search"
                        status = f"{t['row_count']} row(s)" if t["ok"] else f"failed: {t.get('error') or 'error'}"
                        st.markdown(f"**{icon}** · {esc(status)}")
                        st.markdown(f'<div class="fm-sql">{esc(t["detail"])}</div>', unsafe_allow_html=True)
    user_input = quick or st.chat_input("Ask about your spending, budgets, flagged transactions...")
    if user_input:
        history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[-20:]]
        ss.messages.append({"role": "user", "content": user_input})
        with st.spinner("FinMind AI is working on it..."):
            r = guarded(api.post, "/chat", json={"message": user_input, "chat_history": history}, timeout=60)
        if r.status_code == 200:
            ss.messages.append({"role": "assistant", "content": r.json()["reply"], "trace": r.json()["tool_trace"]})
        else:
            msg = {503: "The AI advisor isn't configured on the server (missing GROQ_API_KEY).",
                   429: "You're sending messages too quickly. Please wait a moment."}.get(r.status_code, api.error_detail(r))
            ss.messages.append({"role": "assistant", "content": f"Sorry — {msg}", "trace": []})
        st.rerun()
    if ss.messages and st.button("🗑️ Clear chat"):
        ss.messages = []
        st.rerun()


# ═════════════════════════ PAGE: Fraud Alerts ═════════════════════════
elif "Fraud" in page:
    st.markdown('<p class="fm-page-title">Fraud Detection</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Calibrated ML scoring on every expense, with per-transaction explanations</p>', unsafe_allow_html=True)
    txs = guarded(api.all_transactions)
    if not txs:
        empty_card("📭", "No transactions yet.")
        st.stop()
    df = pd.DataFrame(txs)
    flagged_df, expense_df = df[df.is_flagged], df[df.transaction_type == "expense"]
    set_pulse(int((df.risk_level == "CRITICAL").sum()), len(flagged_df))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total transactions", len(df))
    c2.metric("🚨 Flagged", len(flagged_df), f"{len(flagged_df) / len(df) * 100:.1f}% of total")
    c3.metric("💰 Amount at risk", f"₹{flagged_df.amount.sum():,.0f}" if len(flagged_df) else "₹0")
    c4.metric("Avg fraud score", f"{expense_df.fraud_score.mean() if len(expense_df) else 0:.1f}%")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="fm-section-label">Fraud score distribution</p>', unsafe_allow_html=True)
        if len(expense_df):
            fig = px.histogram(expense_df, x="fraud_score", nbins=25, color_discrete_sequence=["#2FD9C4"])
            fig.update_traces(marker_line_width=0, opacity=0.85, hovertemplate="Score: %{x:.0f}%<br>Count: %{y}<extra></extra>")
            fig.update_layout(**layout(height=260, xaxis_title="Fraud score (%)", yaxis_title="Transactions"))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with col2:
        st.markdown('<p class="fm-section-label">Risk level breakdown</p>', unsafe_allow_html=True)
        if len(expense_df):
            rc = expense_df.risk_level.value_counts().reset_index()
            rc.columns = ["level", "count"]
            fig2 = px.bar(rc, x="level", y="count", color="level",
                          color_discrete_map={"LOW": "#34D399", "MEDIUM": "#FBBF24", "HIGH": "#FB923C", "CRITICAL": "#F5455C"})
            fig2.update_traces(marker_line_width=0, hovertemplate="<b>%{x}</b><br>%{y} transactions<extra></extra>")
            fig2.update_layout(**layout(height=260, showlegend=False))
            st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
    st.markdown('<p class="fm-section-label">Flagged transactions</p>', unsafe_allow_html=True)
    if flagged_df.empty:
        empty_card("✅", "All clear — no fraud detected")
    for _, tx in flagged_df.iterrows():
        with st.expander(f"🔴 {tx['description']} — ₹{tx['amount']:,.0f} | {tx['risk_level']} | {tx['fraud_score']:.1f}%"):
            ec1, ec2, ec3, ec4 = st.columns(4)
            ec1.metric("Fraud score", f"{tx['fraud_score']:.1f}%")
            ec2.metric("Risk level", tx["risk_level"])
            ec3.metric("Amount", f"₹{tx['amount']:,.0f}")
            with ec4:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ Delete", key=f"del_fraud_{tx['id']}", width="stretch"):
                    guarded(api.delete, f"/transaction/{tx['id']}")
                    st.rerun()
            st.markdown('<p class="fm-section-label">Why it was flagged</p>', unsafe_allow_html=True)
            render_risk_factors(tx["fraud_factors"] if isinstance(tx["fraud_factors"], list) else None)


# ═════════════════════════ PAGE: Insights ═════════════════════════
elif "Insights" in page:
    st.markdown('<p class="fm-page-title">Insights</p>', unsafe_allow_html=True)
    st.markdown('<p class="fm-page-sub">Unusual spending and your 4-week outlook — computed by nightly background jobs</p>', unsafe_allow_html=True)
    if st.button("🔄 Recompute now"):
        r = guarded(api.post, "/analytics/refresh")
        st.info("Queued. Refresh this page in a few seconds.") if r.status_code == 202 else st.warning(api.error_detail(r))

    st.markdown('<p class="fm-section-label">Unusual for you</p>', unsafe_allow_html=True)
    rep = guarded(api.get, "/anomalies/me").json()
    if rep["status"] == "insufficient_data":
        st.info(f"Add at least {rep['min_required']} expenses to enable anomaly detection (you have {rep['expense_count']}).")
    elif rep["status"] == "pending":
        st.info("Your history hasn't been scored yet. Click “Recompute now” or wait for the nightly run.")
    else:
        method = "Isolation Forest" if rep["method"] == "isolation_forest" else "robust z-score (MAD)"
        st.caption(f"Method: {method} · based on {rep['expense_count']} expenses · scored {str(rep['scored_at'])[:16].replace('T', ' ')} UTC")
        if not rep["anomalies"]:
            empty_card("✅", "Nothing unusual in your spending.")
        for a in rep["anomalies"]:
            st.markdown(f'<div class="fm-card" style="padding:12px 16px;margin-bottom:8px;"><div style="display:flex;justify-content:space-between;">'
                        f'<span style="color:#C8D8F0;font-size:14px;">{esc(a["description"])} <span style="color:#4A6080;">· {esc(a["category"])} · {esc(a["occurred_at"][:10])}</span></span>'
                        f'<span class="fm-mono" style="color:#FB923C;">₹{a["amount"]:,.0f}</span></div>'
                        f'<div style="font-size:12px;color:#4A6080;margin-top:4px;">{esc(a["reason"])}</div></div>', unsafe_allow_html=True)

    st.markdown('<p class="fm-section-label">Spending outlook (next 4 weeks)</p>', unsafe_allow_html=True)
    fr = guarded(api.get, "/forecast/me")
    data = fr.json()
    if fr.status_code == 202 or data.get("status") == "pending":
        st.info("Forecast is being computed. Refresh in a few seconds.")
    elif data.get("status") == "insufficient_data":
        st.info(f"Forecasting needs at least {data['min_required_weeks']} weeks of history (you have {data['history_weeks']}).")
    else:
        w = pd.DataFrame(data["weekly"])
        fig = go.Figure()
        for lo, hi, alpha, name in (("lo95", "hi95", 0.10, "95% band"), ("lo80", "hi80", 0.20, "80% band")):
            fig.add_trace(go.Scatter(x=w.week_start, y=w[hi], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=w.week_start, y=w[lo], mode="lines", line=dict(width=0), fill="tonexty",
                                     fillcolor=f"rgba(47,217,196,{alpha})", name=name, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=w.week_start, y=w["mean"], mode="lines+markers", name="Forecast", line=dict(color="#2FD9C4", width=2.5),
                                 hovertemplate="<b>Week of %{x}</b><br>₹%{y:,.0f}<extra></extra>"))
        fig.update_layout(**layout(height=300, yaxis_title="Weekly spend (₹)", legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)")))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption(f"{data['model']} on {data['history_weeks']} weeks of history · {data['interval_method']} intervals · "
                   f"expected next 4 weeks: ₹{data['total_next_4_weeks']:,.0f}")