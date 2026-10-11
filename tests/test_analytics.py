"""Analytics guardrails, Redis velocity windows, and the real ONNX scorer artifacts."""
from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend import analytics as A


def _expenses(n: int, outliers: int = 0, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.Timestamp("2026-06-01", tz="Asia/Kolkata") + pd.to_timedelta(rng.uniform(0, 90 * 86400, n), unit="s")
    amt = np.exp(rng.normal(6, 0.4, n))
    amt[:outliers] *= 30
    return pd.DataFrame({"id": range(n), "amount": amt, "category": rng.choice(["Food", "Transport", "Shopping"], n, p=[.6, .3, .1]), "occurred_at": ts})


# ───────────────────────────── anomaly sample-size guardrails ────────────
def test_too_few_samples_are_not_scored():
    assert A.score_anomalies(_expenses(A.MIN_MAD - 1)) is None


def test_small_samples_use_mad_and_catch_planted_outliers():
    res = A.score_anomalies(_expenses(60, outliers=3))
    assert {r.method for r in res} == {"mad"}
    assert {r.tx_id for r in res if r.is_anomaly} >= {0, 1, 2}


def test_large_samples_use_isolation_forest_with_a_bounded_flag_rate():
    res = A.score_anomalies(_expenses(300, outliers=5))
    assert {r.method for r in res} == {"isolation_forest"}
    flagged = sum(r.is_anomaly for r in res)
    assert sum(res[i].is_anomaly for i in range(5)) >= 3 and flagged <= 0.05 * len(res)   # not a forced 10%


def test_identical_amounts_do_not_divide_by_zero():
    df = _expenses(20)
    df["amount"] = 100.0
    assert not any(r.is_anomaly for r in A.score_anomalies(df))


# ───────────────────────────── forecasting ───────────────────────────────
def test_forecast_requires_enough_history():
    idx = pd.date_range("2026-01-05", periods=A.MIN_FORECAST_WEEKS - 1, freq="W-MON")
    assert A.forecast_weekly(pd.Series(5000.0, index=idx)) is None


@pytest.mark.parametrize("weeks,method", [(14, "parametric"), (30, "conformal")])
def test_forecast_has_80_and_95_bands(weeks, method):
    pytest.importorskip("statsforecast")
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-01-05", periods=weeks, freq="W-MON")
    out = A.forecast_weekly(pd.Series(5000 + rng.normal(0, 600, weeks), index=idx))
    assert out["interval_method"] == method and len(out["weekly"]) == A.HORIZON_WEEKS
    for w in out["weekly"]:
        assert 0 <= w["lo95"] <= w["lo80"] <= w["mean"] <= w["hi80"] <= w["hi95"]       # nested, non-negative bands


# ───────────────────────────── velocity windows (real Redis) ─────────────
@pytest.fixture
async def store(app):
    from backend.velocity import VelocityStore
    return VelocityStore(app.state.redis)


@pytest.mark.asyncio
async def test_velocity_windows_slide_and_exclude_the_current_tx(store):
    u, t0 = uuid.uuid4(), 1_800_000_000.0
    f = await store.observe(u, uuid.uuid4(), 100, t0)
    assert (f.tx_count_5m, f.tx_sum_24h, f.amount_to_avg_ratio) == (0, 0, 1.0)         # first tx: nothing prior
    f = await store.observe(u, uuid.uuid4(), 200, t0 + 60)
    assert (f.tx_count_5m, f.tx_sum_24h) == (1, 100)
    f = await store.observe(u, uuid.uuid4(), 50, t0 + 120)
    assert (f.tx_count_5m, f.tx_sum_24h) == (2, 300) and f.amount_to_avg_ratio == 1.0   # < 3 prior => cold start
    f = await store.observe(u, uuid.uuid4(), 300, t0 + 180)
    assert f.amount_to_avg_ratio == pytest.approx(300 / 100)                              # median(100, 200, 50) = 100
    f = await store.observe(u, uuid.uuid4(), 10, t0 + 430)                                # only the t0+180 tx is still inside the 5-min window
    assert f.tx_count_5m == 1 and f.tx_sum_24h == 650
    f = await store.observe(u, uuid.uuid4(), 10, t0 + 86_400 + 400)                       # ~a day later: only the t0+430 tx (10) is still in the 24h sum
    assert f.tx_sum_24h == 10 and f.tx_count_5m == 0


@pytest.mark.asyncio
async def test_velocity_is_per_user(store):
    a, b, t0 = uuid.uuid4(), uuid.uuid4(), 1_800_000_000.0
    await store.observe(a, uuid.uuid4(), 500, t0)
    assert (await store.observe(b, uuid.uuid4(), 500, t0 + 1)).tx_count_5m == 0


# ───────────────────────────── real model artifacts (skipped if absent) ──
_MODEL_DIR = Path(__file__).resolve().parent.parent / "ml_models"
needs_model = pytest.mark.skipif(not (_MODEL_DIR / "fraud_model.onnx").exists(), reason="run ml_models/train_fraud_model.py first")


@needs_model
def test_real_onnx_scorer_ranks_attack_patterns_above_normal_spend_and_explains_them():
    from ml_models.scorer import FraudScorer

    s = FraudScorer(_MODEL_DIR)
    normal = s.score(amount=420, category="Food", hour=13, day_of_week=2, tx_count_5m=0, tx_sum_24h=900, amount_to_avg_ratio=1.1)
    probing = s.score(amount=35, category="Shopping", hour=14, day_of_week=2, tx_count_5m=9, tx_sum_24h=300, amount_to_avg_ratio=0.1)
    assert normal.risk_level == "LOW" and not normal.is_flagged
    assert probing.is_flagged and probing.probability > 0.5 > normal.probability
    assert len(probing.factors) == 3 and probing.factors[0].feature == "tx_count_5m" and probing.factors[0].direction == "increases_risk"
    assert 0.0 <= normal.probability <= 1.0 and normal.model_version
    assert s.score(amount=1, category="NotACategory", hour=0, day_of_week=0, tx_count_5m=0, tx_sum_24h=0, amount_to_avg_ratio=1).probability >= 0  # unknown category -> 'Other'
