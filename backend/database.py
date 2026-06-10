from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

# ── Supports SQLite (local dev) and PostgreSQL (Render production) ──────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "database", "finmind.db"
    )
)

# Render provides postgres:// but SQLAlchemy 1.4+ requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine       = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
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
    user_id          = Column(Integer, index=True)
    description      = Column(String)
    amount           = Column(Float)
    category         = Column(String)
    transaction_type = Column(String)
    fraud_score      = Column(Float,   default=0.0)
    risk_level       = Column(String,  default="LOW")
    is_flagged       = Column(Boolean, default=False)
    date             = Column(DateTime, default=datetime.utcnow)
    embedding_id     = Column(String,  nullable=True)  # ChromaDB doc ID for RAG


class Budget(Base):
    __tablename__ = "budgets"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, index=True)
    category      = Column(String)
    limit_amount  = Column(Float)
    spent_amount  = Column(Float, default=0.0)
    month         = Column(String)


def create_tables():
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "database"
            ),
            exist_ok=True
        )
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()