from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_financial_advice(
    user_message: str,
    transactions: list,
    budgets: list,
    chat_history: list
) -> str:
    """
    Financial advisor chatbot using Groq + Llama3
    Knows user's actual financial data
    """

    # Build financial context from real user data
    total_income  = sum(t['amount'] for t in transactions if t['transaction_type'] == 'income')
    total_expense = sum(t['amount'] for t in transactions if t['transaction_type'] == 'expense')
    savings_rate  = ((total_income - total_expense) / total_income * 100) if total_income > 0 else 0

    # Category breakdown
    categories = {}
    for t in transactions:
        if t['transaction_type'] == 'expense':
            cat = t['category']
            categories[cat] = categories.get(cat, 0) + t['amount']

    # Budget status
    budget_status = []
    for b in budgets:
        pct  = (b['spent_amount'] / b['limit_amount'] * 100) if b['limit_amount'] > 0 else 0
        budget_status.append(
            f"{b['category']}: spent ₹{b['spent_amount']:.0f} of ₹{b['limit_amount']:.0f} ({pct:.0f}%)"
        )

    # Flagged transactions
    flagged = [t for t in transactions if t.get('is_flagged')]

    system_prompt = f"""You are FinMind AI, a smart personal financial advisor.
You have access to the user's real financial data. Use it to give specific, personalized advice.

USER'S FINANCIAL SUMMARY:
- Total Income this month:  ₹{total_income:,.0f}
- Total Expenses this month: ₹{total_expense:,.0f}
- Savings Rate: {savings_rate:.1f}%
- Net Savings: ₹{total_income - total_expense:,.0f}

SPENDING BY CATEGORY:
{chr(10).join([f'- {cat}: ₹{amt:,.0f}' for cat, amt in categories.items()])}

BUDGET STATUS:
{chr(10).join(budget_status) if budget_status else 'No budgets set yet'}

FRAUD ALERTS:
{len(flagged)} transaction(s) flagged as suspicious this month

RULES:
- Always refer to their ACTUAL numbers, not generic advice
- Be conversational, friendly, and concise
- Use ₹ for currency
- If you spot a problem in their data, point it out proactively
- Keep responses under 150 words unless they ask for detail
- Never make up numbers not in the data above
"""

    # Build messages with history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history[-6:]:   # last 6 messages for context
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=300,
        temperature=0.7
    )

    return response.choices[0].message.content