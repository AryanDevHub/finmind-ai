"""schemas.py — Pydantic v2 request/response models."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Category = Literal[
    "Food", "Transport", "Shopping", "Entertainment", "Bills",
    "Health", "Education", "Salary", "Investment", "Other",
]
TxType = Literal["income", "expense"]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")]
MonthStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class UserRegister(BaseModel):
    username: Username
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    email: str


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TransactionCreate(BaseModel):
    """`occurred_at` is deliberately NOT accepted: server time keeps velocity features tamper-proof."""
    model_config = ConfigDict(extra="forbid")
    description: Text200
    merchant: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    amount: Money
    category: Category
    transaction_type: TxType


class RiskFactorOut(BaseModel):
    feature: str
    label: str
    value: float
    contribution: float
    direction: Literal["increases_risk", "decreases_risk"]


class TransactionAddResponse(BaseModel):
    id: uuid.UUID
    fraud_score: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    is_flagged: bool
    risk_factors: list[RiskFactorOut]
    model_version: str | None
    degraded: bool = Field(False, description="True if velocity features were unavailable (Redis down) and neutral defaults were used")


class RiskPreview(BaseModel):
    """What the model WOULD say about this transaction right now. Nothing is stored or recorded."""
    fraud_score: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    is_flagged: bool
    risk_factors: list[RiskFactorOut]
    degraded: bool = False


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    description: str
    merchant: str | None
    amount: float
    category: str
    transaction_type: str
    occurred_at: datetime
    fraud_score: float
    risk_level: str
    is_flagged: bool
    fraud_factors: list[dict[str, Any]] | None = None
    is_anomaly: bool = False


class BudgetSet(BaseModel):
    category: Category
    limit_amount: Money
    month: MonthStr | None = None  # defaults to the current month


class BudgetOut(BaseModel):
    category: str
    month: str
    limit_amount: float
    spent_amount: float
    percent_used: float
    over_budget: bool


class AnomalyOut(BaseModel):
    id: uuid.UUID
    description: str
    amount: float
    category: str
    occurred_at: datetime
    anomaly_score: float
    method: str
    reason: str


class AnomalyReport(BaseModel):
    status: Literal["ok", "pending", "insufficient_data"]
    method: str | None = None
    scored_at: datetime | None = None
    expense_count: int
    min_required: int
    anomalies: list[AnomalyOut] = []
    message: str | None = None


def valid_month(m: str) -> bool:
    return re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m) is not None


class ChatTurn(BaseModel):
    """Only user/assistant turns are accepted from the client: a client-supplied 'system' turn would be prompt injection."""
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=4000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    chat_history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class ToolTraceOut(BaseModel):
    tool: str
    ok: bool
    detail: str          # the SQL that ran, or the semantic query
    row_count: int = 0
    error: str | None = None
    preview: dict[str, Any] | None = None   # first rows of the tool result, for the UI's tool-call cards


class ChatResponse(BaseModel):
    reply: str
    tool_trace: list[ToolTraceOut]
