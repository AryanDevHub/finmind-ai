"""
Test harness. Integration tests need Postgres (pgvector image) and Redis:

    docker compose up -d postgres redis      # or the two `docker run` commands from the README
    pytest -v

Safety: tests run ONLY against a database whose name ends in `_test` (created
automatically) and Redis logical DB 15, never against your dev data.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://finmind:finmind_dev_password@localhost:5432/finmind_test"
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
if not urlparse(TEST_DATABASE_URL).path.lstrip("/").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must point at a database whose name ends with '_test'.")

# Must be set BEFORE any backend module is imported (load_dotenv never overrides existing variables).
os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL, REDIS_URL=TEST_REDIS_URL, ENVIRONMENT="test",
    SECRET_KEY="test-secret-key-0123456789abcdef0123456789abcdef", COOKIE_SECURE="false",
    CORS_ORIGINS="http://localhost:8501", GROQ_API_KEY="", APP_TIMEZONE="Asia/Kolkata",
    LOGIN_MAX_ATTEMPTS="5",
)

import httpx  # noqa: E402

from ml_models.scorer import RiskFactor, ScoreResult  # noqa: E402


async def _ensure_database() -> None:
    import asyncpg

    u = urlparse(TEST_DATABASE_URL)
    admin = await asyncpg.connect(u._replace(path="/postgres").geturl())
    try:
        name = u.path.lstrip("/")
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session")
def database() -> None:
    """Fresh schema via the REAL Alembic migration (also proves the migration works). Opt-in: pure unit tests skip it."""
    from alembic import command
    from alembic.config import Config

    asyncio.run(_ensure_database())
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


class FakeScorer:
    """Stands in for the ONNX model: deterministic output, records the features it was given."""

    model_version = "test-model"

    def __init__(self) -> None:
        self.probability = 0.01
        self.level = "LOW"
        self.calls: list[dict] = []

    def score(self, *, explain: bool = True, top_k: int = 3, **features) -> ScoreResult:
        self.calls.append(features)
        factors = tuple(
            RiskFactor(feature=f, value=float(features.get(f, 0.0)), contribution=c, direction=d)
            for f, c, d in (("tx_count_5m", 1.2, "increases_risk"), ("amount", 0.4, "increases_risk"),
                            ("hour", -0.2, "decreases_risk"))
        )[:top_k]
        return ScoreResult(
            probability=self.probability, score_pct=round(self.probability * 100, 2), risk_level=self.level,  # type: ignore[arg-type]
            is_flagged=self.level in ("HIGH", "CRITICAL"), factors=factors, model_version=self.model_version,
        )


@pytest_asyncio.fixture(scope="session")
async def app(database):
    from backend.main import app as fastapi_app

    async with fastapi_app.router.lifespan_context(fastapi_app):
        await fastapi_app.state.redis.flushdb()
        fastapi_app.state.scorer = FakeScorer()
        yield fastapi_app


@pytest.fixture
def scorer(app) -> FakeScorer:
    app.state.scorer = FakeScorer()  # fresh per test
    return app.state.scorer


@pytest.fixture(autouse=True)
def sent_tasks(monkeypatch) -> list[tuple]:
    """Celery publishing is replaced by a recorder (no broker traffic in tests)."""
    sent: list[tuple] = []
    monkeypatch.setattr("backend.main._send", lambda task, *args: sent.append((task, *args)))
    return sent


@pytest_asyncio.fixture
async def client(app, scorer):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


class Account:
    def __init__(self, client: httpx.AsyncClient, username: str, password: str, user_id: str, token: str) -> None:
        self.client, self.username, self.password, self.id, self.token = client, username, password, user_id, token

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest_asyncio.fixture
async def make_account(app, scorer):
    clients: list[httpx.AsyncClient] = []

    async def _make(prefix: str = "user") -> Account:
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        name, pw = f"{prefix}_{uuid.uuid4().hex[:8]}", "correct-horse-1"
        r = await c.post("/auth/register", json={"username": name, "email": f"{name}@example.com", "password": pw})
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        r = await c.post("/auth/login", data={"username": name, "password": pw})
        assert r.status_code == 200, r.text
        return Account(c, name, pw, uid, r.json()["access_token"])

    yield _make
    for c in clients:
        await c.aclose()


@pytest_asyncio.fixture
async def alice(make_account) -> Account:
    return await make_account("alice")


@pytest_asyncio.fixture
async def bob(make_account) -> Account:
    return await make_account("bob")
