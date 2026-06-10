"""
chatbot.py — FinMind AI Financial Advisor
Upgrades over v1:
  1. RAG context — semantically relevant past transactions injected per query
  2. Tool-calling agent — LLM can call get_summary, get_fraud_alerts,
     get_category_breakdown, and get_budget_status directly from chat
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Tool definitions (Groq function-calling schema) ───────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Get total income, total expenses, savings rate, and net savings for the user.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fraud_alerts",
            "description": "Get all transactions flagged as suspicious or fraudulent.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_breakdown",
            "description": "Get spending broken down by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional: filter to a specific category like Food, Transport, Shopping."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_status",
            "description": "Get budget limits and current spending for each category this month.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]


# ── Tool executor ────────────────────────────────────────────────

def _execute_tool(tool_name: str, args: dict, transactions: list, budgets: list) -> str:
    """Run the named tool and return a JSON string result."""

    if tool_name == "get_financial_summary":
        income  = sum(t["amount"] for t in transactions if t["transaction_type"] == "income")
        expense = sum(t["amount"] for t in transactions if t["transaction_type"] == "expense")
        savings = income - expense
        rate    = (savings / income * 100) if income > 0 else 0
        return json.dumps({
            "total_income":   income,
            "total_expenses": expense,
            "net_savings":    savings,
            "savings_rate":   round(rate, 1)
        })

    elif tool_name == "get_fraud_alerts":
        flagged = [
            {
                "description": t["description"],
                "amount":      t["amount"],
                "category":    t["category"],
                "risk_level":  t.get("risk_level", "HIGH"),
                "fraud_score": t.get("fraud_score", 0),
            }
            for t in transactions if t.get("is_flagged")
        ]
        return json.dumps({"flagged_count": len(flagged), "transactions": flagged})

    elif tool_name == "get_category_breakdown":
        filter_cat = args.get("category", "").lower()
        cats: dict = {}
        for t in transactions:
            if t["transaction_type"] == "expense":
                cat = t["category"]
                if filter_cat and filter_cat not in cat.lower():
                    continue
                cats[cat] = cats.get(cat, 0) + t["amount"]
        sorted_cats = dict(sorted(cats.items(), key=lambda x: x[1], reverse=True))
        return json.dumps({"spending_by_category": sorted_cats})

    elif tool_name == "get_budget_status":
        result = []
        for b in budgets:
            pct = (b["spent_amount"] / b["limit_amount"] * 100) if b["limit_amount"] > 0 else 0
            result.append({
                "category":     b["category"],
                "limit":        b["limit_amount"],
                "spent":        b["spent_amount"],
                "remaining":    max(b["limit_amount"] - b["spent_amount"], 0),
                "percent_used": round(pct, 1),
                "over_budget":  b["spent_amount"] > b["limit_amount"]
            })
        return json.dumps({"budgets": result})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ── RAG context builder (graceful fallback if rag.py unavailable) ─

def _get_rag_context(user_message: str, user_id: int) -> str:
    try:
        from backend.rag import build_rag_context
        return build_rag_context(user_message, user_id)
    except Exception:
        return ""


# ── Main public function ─────────────────────────────────────────

def get_financial_advice(
    user_message:  str,
    transactions:  list,
    budgets:       list,
    chat_history:  list,
    user_id:       int = 1,
) -> str:
    """
    Agentic financial advisor:
      1. Builds a RAG context block from semantically similar past transactions
      2. Calls Groq with tool-calling enabled
      3. If the model calls a tool, executes it and sends the result back
      4. Returns the final natural-language response
    """

    # ── 1. RAG retrieval ─────────────────────────────────────────
    rag_context = _get_rag_context(user_message, user_id)

    # ── 2. Quick summary stats for system prompt ─────────────────
    income  = sum(t["amount"] for t in transactions if t["transaction_type"] == "income")
    expense = sum(t["amount"] for t in transactions if t["transaction_type"] == "expense")
    savings_rate = ((income - expense) / income * 100) if income > 0 else 0
    flagged_count = sum(1 for t in transactions if t.get("is_flagged"))

    system_prompt = f"""You are FinMind AI, a smart personal financial advisor and AI agent.
You have access to the user's real financial data AND four callable tools to look up details.

QUICK OVERVIEW:
- Income this month:  ₹{income:,.0f}
- Expenses this month: ₹{expense:,.0f}
- Savings rate: {savings_rate:.1f}%
- Fraud alerts: {flagged_count}

{rag_context}

BEHAVIOUR RULES:
- Use tools when the user asks for specific numbers — don't guess from the overview above
- After a tool result, give a concrete, specific insight using the real numbers
- Use ₹ for all amounts
- Be conversational and concise — under 150 words unless the user asks for detail
- If you spot a problem (overspend, fraud, low savings), say so proactively
- Never fabricate numbers not in the tool results or data above
"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history[-8:]:
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})

    # ── 3. First LLM call (may trigger tool use) ─────────────────
    response = client.chat.completions.create(
        model       = "llama-3.3-70b-versatile",
        messages    = messages,
        tools       = TOOLS,
        tool_choice = "auto",
        max_tokens  = 400,
        temperature = 0.7,
    )

    msg = response.choices[0].message

    # ── 4. Agentic loop — handle tool calls ──────────────────────
    if msg.tool_calls:
        # Add the assistant's tool-call message to history
        messages.append({
            "role":       "assistant",
            "content":    msg.content or "",
            "tool_calls": [
                {
                    "id":       tc.id,
                    "type":     "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        # Execute each tool and add results
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            tool_result = _execute_tool(tc.function.name, args, transactions, budgets)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      tool_result,
            })

        # Second call — LLM synthesises tool results into a reply
        final = client.chat.completions.create(
            model       = "llama-3.3-70b-versatile",
            messages    = messages,
            max_tokens  = 400,
            temperature = 0.7,
        )
        return final.choices[0].message.content

    # No tool call — return direct response
    return msg.content