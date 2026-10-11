"""
scorer.py — runtime fraud scoring for the FastAPI hot path.

Loads the artifacts written by train_fraud_model.py and exposes a single
synchronous, allocation-light `score()` call (~1.2 ms single-row on one CPU
thread, see model_metrics.json -> serving):

    raw = ONNX Runtime (LightGBM, float32)
    p   = isotonic calibration (np.interp over stored knots)
    top-k attribution = LightGBM native TreeSHAP (`pred_contrib=True`),
                        i.e. the same algorithm as shap.TreeExplainer

Contributions are in log-odds of the UNcalibrated model (the space TreeSHAP
operates in). They are for ranking/explaining factors, not probabilities.

Instantiate ONCE at application startup and share across requests: both the
ORT session and the LightGBM booster are safe for concurrent `predict` calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import lightgbm as lgb
import numpy as np
import onnxruntime as ort

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_DEFAULT_DIR: Final[Path] = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class RiskFactor:
    feature: str
    value: float
    contribution: float                      # TreeSHAP value, log-odds
    direction: Literal["increases_risk", "decreases_risk"]


@dataclass(frozen=True, slots=True)
class ScoreResult:
    probability: float                       # calibrated, in [0, 1]
    score_pct: float                         # probability * 100, 2 dp
    risk_level: RiskLevel
    is_flagged: bool
    factors: tuple[RiskFactor, ...]
    model_version: str


class FraudScorer:
    """Thread-safe, load-once fraud scorer."""

    def __init__(self, model_dir: Path | str | None = None) -> None:
        d = Path(model_dir) if model_dir else _DEFAULT_DIR
        self.feature_names: list[str] = json.loads((d / "feature_names.json").read_text())
        metrics = json.loads((d / "model_metrics.json").read_text())
        self.model_version: str = metrics["model_version"]
        self._tiers: dict[str, float] = metrics["thresholds"]

        cal = json.loads((d / "calibrator.json").read_text())
        self._cal_x = np.asarray(cal["x"], dtype=np.float64)
        self._cal_y = np.asarray(cal["y"], dtype=np.float64)

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        self._sess = ort.InferenceSession(
            str(d / "fraud_model.onnx"), so, providers=["CPUExecutionProvider"]
        )
        self._in = self._sess.get_inputs()[0].name
        self._prob_out = self._sess.get_outputs()[1].name
        self._booster = lgb.Booster(model_file=str(d / "lgbm_booster.txt"))

        self._idx = {n: i for i, n in enumerate(self.feature_names)}
        self._categories = [n.removeprefix("cat_") for n in self.feature_names if n.startswith("cat_")]

    # ── feature vector ─────────────────────────────────────────────────
    def build_vector(
        self, *, amount: float, category: str, hour: int, day_of_week: int,
        tx_count_5m: float, tx_sum_24h: float, amount_to_avg_ratio: float,
    ) -> np.ndarray:
        """Build the (1, F) float32 row. Unknown categories map to 'Other'."""
        x = np.zeros((1, len(self.feature_names)), dtype=np.float32)
        x[0, self._idx["amount"]] = amount
        x[0, self._idx["hour"]] = hour
        x[0, self._idx["day_of_week"]] = day_of_week
        x[0, self._idx["tx_count_5m"]] = tx_count_5m
        x[0, self._idx["tx_sum_24h"]] = tx_sum_24h
        x[0, self._idx["amount_to_avg_ratio"]] = amount_to_avg_ratio
        cat = category if category in self._categories else "Other"
        x[0, self._idx[f"cat_{cat}"]] = 1.0
        return x

    # ── scoring ────────────────────────────────────────────────────────
    def _risk_level(self, p: float) -> RiskLevel:
        if p >= self._tiers["critical"]:
            return "CRITICAL"
        if p >= self._tiers["high"]:
            return "HIGH"
        if p >= self._tiers["medium"]:
            return "MEDIUM"
        return "LOW"

    def predict_proba(self, x: np.ndarray) -> float:
        raw = np.asarray(self._sess.run([self._prob_out], {self._in: x})[0])
        raw_p = float(raw[0, 1] if raw.ndim == 2 else raw[0])
        return float(np.interp(raw_p, self._cal_x, self._cal_y))

    def explain(self, x: np.ndarray, top_k: int = 3) -> tuple[RiskFactor, ...]:
        contrib = self._booster.predict(x, pred_contrib=True, num_threads=1)[0][:-1]  # drop bias term
        order = np.argsort(-np.abs(contrib))[:top_k]
        return tuple(
            RiskFactor(
                feature=self.feature_names[i],
                value=float(x[0, i]),
                contribution=round(float(contrib[i]), 4),
                direction="increases_risk" if contrib[i] > 0 else "decreases_risk",
            )
            for i in order
        )

    def score(self, *, explain: bool = True, top_k: int = 3, **features: float | int | str) -> ScoreResult:
        """score(amount=..., category=..., hour=..., day_of_week=..., tx_count_5m=...,
        tx_sum_24h=..., amount_to_avg_ratio=...)"""
        x = self.build_vector(**features)  # type: ignore[arg-type]
        p = self.predict_proba(x)
        level = self._risk_level(p)
        return ScoreResult(
            probability=p,
            score_pct=round(p * 100.0, 2),
            risk_level=level,
            is_flagged=level in ("HIGH", "CRITICAL"),
            factors=self.explain(x, top_k) if explain else (),
            model_version=self.model_version,
        )
