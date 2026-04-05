from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Always use absolute path — works from any directory
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH      = os.path.join(BASE_DIR, "database", "finmind.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()

class User(Base):
    __tablename__   = "users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True, index=True)
    email           = Column(String, unique=True)
    hashed_password = Column(String)
    created_at      = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__    = "transactions"
    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer)
    description      = Column(String)
    amount           = Column(Float)
    category         = Column(String)
    transaction_type = Column(String)
    fraud_score      = Column(Float, default=0.0)
    risk_level       = Column(String, default="LOW")
    is_flagged       = Column(Boolean, default=False)
    date             = Column(DateTime, default=datetime.utcnow)

class Budget(Base):
    __tablename__ = "budgets"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer)
    category      = Column(String)
    limit_amount  = Column(Float)
    spent_amount  = Column(Float, default=0.0)
    month         = Column(String)

def create_tables():
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()