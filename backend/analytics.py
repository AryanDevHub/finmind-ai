"""
analytics.py — pure functions for the nightly analytics jobs (no I/O, easy to test).

Anomaly detection (per user, over their expense history):
  N >= 100  -> IsolationForest on [log amount, hour sin/cos, day-of-week, category rarity]
  10 <= N < 100 -> robust MAD z-score on log amount (per category when a category has
                   >= 8 samples, else across all of the user's expenses); upper tail only
  N < 10    -> not scored; the API reports `insufficient_data` instead of guessing.

Forecasting: AutoARIMA (statsforecast) on WEEKLY expense totals, 4-week horizon,
80% / 95% bands. Interval method is conformal when history is long enough
(>= 20 weeks), otherwise ARIMA's parametric (Gaussian) intervals. Fewer than
12 weeks -> no forecast. Weekly (not monthly) because personal histories
rarely have enough months to fit anything honestly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

MIN_IFOREST = 100
MIN_MAD = 10
MIN_FORECAST_WEEKS = 12
CONFORMAL_MIN_WEEKS = 20
HORIZON_WEEKS = 4
_MAD_THRESHOLD = 3.5
_IF_CONTAMINATION = 0.02


@dataclass(frozen=True, slots=True)
class AnomalyResult:
    tx_id: Any
    score: float
    is_anomaly: bool
    method: str  # 'isolation_forest' | 'mad'


def _mad_z(x: pd.Series) -> pd.Series:
    med = x.median()
    mad = (x - med).abs().median()
    if mad > 0:
        return 0.6745 * (x - med) / mad
    mean_ad = (x - med).abs().mean()  # >50% identical values: fall back to mean absolute deviation
    return (x - med) / (1.2533 * mean_ad) if mean_ad > 0 else pd.Series(0.0, index=x.index)


def score_anomalies(df: pd.DataFrame) -> list[AnomalyResult] | None:
    """df columns: id, amount, category, occurred_at (tz-aware, already in local time). None if N < MIN_MAD."""
    n = len(df)
    if n < MIN_MAD:
        return None
    d = df.reset_index(drop=True).copy()
    d["log_amt"] = np.log1p(d["amount"].astype(float))

    if n >= MIN_IFOREST:
        from sklearn.ensemble import IsolationForest

        hour = d["occurred_at"].dt.hour + d["occurred_at"].dt.minute / 60.0
        freq = d["category"].map(d["category"].value_counts(normalize=True))
        X = np.column_stack([
            d["log_amt"], np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24),
            d["occurred_at"].dt.dayofweek, -np.log(freq),
        ])
        clf = IsolationForest(n_estimators=200, contamination=_IF_CONTAMINATION, random_state=42).fit(X)
        scores = -clf.score_samples(X)  # higher == more anomalous
        flags = clf.predict(X) == -1
        return [AnomalyResult(i, float(s), bool(f), "isolation_forest") for i, s, f in zip(d["id"], scores, flags)]

    z = pd.Series(0.0, index=d.index)
    counts = d["category"].value_counts()
    big = d["category"].map(counts) >= 8
    if big.any():
        z[big] = d[big].groupby("category")["log_amt"].transform(_mad_z)
    if (~big).any():
        z[~big] = _mad_z(d["log_amt"])[~big]
    return [AnomalyResult(i, float(s), bool(s > _MAD_THRESHOLD), "mad") for i, s in zip(d["id"], z)]


def forecast_weekly(weekly: pd.Series, horizon: int = HORIZON_WEEKS) -> dict[str, Any] | None:
    """weekly: float Series indexed by Monday-start week (complete weeks only, zero-filled)."""
    if len(weekly) < MIN_FORECAST_WEEKS:
        return None
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA
    from statsforecast.utils import ConformalIntervals

    df = pd.DataFrame({"unique_id": "u", "ds": pd.to_datetime(weekly.index), "y": weekly.to_numpy(dtype=float)})
    conformal = len(weekly) >= CONFORMAL_MIN_WEEKS
    sf = StatsForecast(models=[AutoARIMA(season_length=1)], freq="W-MON", n_jobs=1)
    kwargs: dict[str, Any] = {"df": df, "h": horizon, "level": [80, 95]}
    if conformal:
        kwargs["prediction_intervals"] = ConformalIntervals(h=horizon, n_windows=2)
    fc = sf.forecast(**kwargs)

    m = "AutoARIMA"
    rows = [
        {
            "week_start": pd.Timestamp(r["ds"]).date().isoformat(),
            "mean": round(max(float(r[m]), 0.0), 2),
            "lo80": round(max(float(r[f"{m}-lo-80"]), 0.0), 2), "hi80": round(max(float(r[f"{m}-hi-80"]), 0.0), 2),
            "lo95": round(max(float(r[f"{m}-lo-95"]), 0.0), 2), "hi95": round(max(float(r[f"{m}-hi-95"]), 0.0), 2),
        }
        for _, r in fc.iterrows()
    ]
    return {
        "model": "AutoARIMA", "interval_method": "conformal" if conformal else "parametric",
        "history_weeks": int(len(weekly)), "weekly": rows,
        "total_next_4_weeks": round(sum(r["mean"] for r in rows), 2),
    }
