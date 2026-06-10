import requests
from datetime import datetime

API = "http://127.0.0.1:8000"
uid = 1

# Add transactions
transactions = [
    {"description": "Monthly Salary",       "amount": 55000, "category": "Salary",        "transaction_type": "income"},
    {"description": "Freelance Payment",    "amount": 12000, "category": "Salary",        "transaction_type": "income"},
    {"description": "Swiggy Order",         "amount": 450,   "category": "Food",          "transaction_type": "expense"},
    {"description": "Zomato Dinner",        "amount": 780,   "category": "Food",          "transaction_type": "expense"},
    {"description": "BigBasket Groceries",  "amount": 2100,  "category": "Food",          "transaction_type": "expense"},
    {"description": "Uber Ride",            "amount": 320,   "category": "Transport",     "transaction_type": "expense"},
    {"description": "Ola Auto",             "amount": 85,    "category": "Transport",     "transaction_type": "expense"},
    {"description": "Amazon Shopping",      "amount": 3200,  "category": "Shopping",      "transaction_type": "expense"},
    {"description": "Netflix Subscription", "amount": 649,   "category": "Entertainment", "transaction_type": "expense"},
    {"description": "Electricity Bill",     "amount": 1800,  "category": "Bills",         "transaction_type": "expense"},
    {"description": "Mobile Recharge",      "amount": 299,   "category": "Bills",         "transaction_type": "expense"},
    {"description": "Gym Membership",       "amount": 1500,  "category": "Health",        "transaction_type": "expense"},
    {"description": "Udemy Course",         "amount": 499,   "category": "Education",     "transaction_type": "expense"},
    {"description": "Suspicious Transfer",  "amount": 15000, "category": "Shopping",      "transaction_type": "expense"},
    {"description": "Unknown International","amount": 8999,  "category": "Other",         "transaction_type": "expense"},
]

print("Adding transactions...")
for tx in transactions:
    tx["user_id"] = uid
    r = requests.post(f"{API}/transaction/add", json=tx)
    result = r.json()
    flag = "FLAGGED" if result["is_flagged"] else "Safe"
    print(f"[{flag}] {tx['description']:30s} | Rs.{tx['amount']:>8,.0f} | Risk: {result['risk_level']}")

print("\nSetting budgets...")
month = datetime.now().strftime("%Y-%m")
budgets = [
    {"category": "Food",          "limit_amount": 6000},
    {"category": "Transport",     "limit_amount": 2000},
    {"category": "Shopping",      "limit_amount": 5000},
    {"category": "Entertainment", "limit_amount": 1000},
    {"category": "Bills",         "limit_amount": 3000},
    {"category": "Health",        "limit_amount": 2000},
    {"category": "Education",     "limit_amount": 1500},
]

for b in budgets:
    b["user_id"] = uid
    b["month"]   = month
    r = requests.post(f"{API}/budget/set", json=b)
    print(f"Budget set: {b['category']:15s} -> Rs.{b['limit_amount']:,.0f}/month")

print("\nAll done! Refresh your Streamlit dashboard now.")