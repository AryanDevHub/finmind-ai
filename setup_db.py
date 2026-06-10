import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean
from datetime import datetime

# Create database folder
os.makedirs("database", exist_ok=True)

# Use absolute path
DB_PATH = os.path.abspath("database/finmind.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"Creating database at: {DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base   = declarative_base()

class User(Base):
    __tablename__    = "users"
    id               = Column(Integer, primary_key=True, index=True)
    username         = Column(String, unique=True, index=True)
    email            = Column(String, unique=True)
    hashed_password  = Column(String)
    created_at       = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__      = "transactions"
    id                 = Column(Integer, primary_key=True, index=True)
    user_id            = Column(Integer)
    description        = Column(String)
    amount             = Column(Float)
    category           = Column(String)
    transaction_type   = Column(String)
    fraud_score        = Column(Float, default=0.0)
    risk_level         = Column(String, default="LOW")
    is_flagged         = Column(Boolean, default=False)
    date               = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__  = "budgets"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer)
    category       = Column(String)
    limit_amount   = Column(Float)
    spent_amount   = Column(Float, default=0.0)
    month          = Column(String)

# Create all tables
Base.metadata.create_all(bind=engine)
print("✓ Tables created: users, transactions, budgets")

# Verify
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"✓ Tables in database: {tables}")
print(f"\n✓ Database ready at: {DB_PATH}")