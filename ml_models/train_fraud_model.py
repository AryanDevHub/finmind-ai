"""
train_fraud_model.py — FinMind AI fraud model training pipeline (v4).

What changed vs. v3 and why
---------------------------
1. NO TAUTOLOGY. v3 generated labels as a function of the exact columns the
   model was trained on, so the model just re-learned the generator. Here
   fraud is produced by *attacker behaviour* (card testing, account takeover,
   slow drip, spending spree) injected into per-user legitimate streams.
   Features (including velocity features) are computed AFTERWARDS from the
   resulting event stream, exactly as they would be at serving time. Legit
   traffic deliberately contains look-alikes (night owls, big one-off
   purchases, bursts of small purchases) and labels carry noise, so the
   classes overlap like real data does.
2. NO SMOTE. Category is one-hot encoded (never interpolated) and class
   imbalance is handled with cost-sensitive learning:
   scale_pos_weight = N_negative / N_positive.
3. VELOCITY FEATURES: tx_count_5m, tx_sum_24h, amount_to_avg_ratio.
4. CALIBRATION + COST-AWARE THRESHOLDS. scale_pos_weight distorts
   probabilities, so we fit Isotonic Regression on a held-out calibration
   split and then pick the flag threshold that minimises expected cost under
   an explicit cost matrix. Reported: ROC-AUC, PR-AUC, Brier, ECE,
   precision/recall at the cost-optimal threshold, recall per attack type.
5. SERVING: ONNX export (onnxruntime) + serialised LightGBM booster whose
   native TreeSHAP (`pred_contrib=True`) yields top-k attributions at
   scoring time. Latency of both is benchmarked and written to metrics.

Splits are CHRONOLOGICAL (train -> calibration -> test), never random.

Feature contract (must match runtime, see ml_models/scorer.py):
  tx_count_5m          # prior txs by this user in the previous 300 s (excl. current)
  tx_sum_24h           # sum of prior tx amounts in the previous 86400 s (excl. current)
  amount_to_avg_ratio  # amount / median of the user's previous <=50 txs
                       # (1.0 when fewer than 3 prior txs: cold start)

Run (from repo root):
    python ml_models/train_fraud_model.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

import lightgbm as lgb
import numpy as np
import onnxruntime as ort
import pandas as pd
from lightgbm import LGBMClassifier
from onnxmltools import convert_lightgbm
from onnxmltools.convert.common.data_types import FloatTensorType
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

log = logging.getLogger("train_fraud_model")

# ───────────────────────────── Feature contract ──────────────────────────
EXPENSE_CATEGORIES: Final[tuple[str, ...]] = (
    "Food", "Transport", "Shopping", "Entertainment", "Bills",
    "Health", "Education", "Investment", "Other",
)
NUMERIC_FEATURES: Final[tuple[str, ...]] = (
    "amount", "hour", "day_of_week",
    "tx_count_5m", "tx_sum_24h", "amount_to_avg_ratio",
)
CATEGORY_FEATURES: Final[tuple[str, ...]] = tuple(f"cat_{c}" for c in EXPENSE_CATEGORIES)
FEATURE_NAMES: Final[list[str]] = [*NUMERIC_FEATURES, *CATEGORY_FEATURES]
STATIC_FEATURES: Final[list[str]] = ["amount", "hour", "day_of_week", *CATEGORY_FEATURES]

OUT_DIR: Final[Path] = Path(__file__).resolve().parent
ONNX_PATH: Final[Path] = OUT_DIR / "fraud_model.onnx"
BOOSTER_PATH: Final[Path] = OUT_DIR / "lgbm_booster.txt"
CALIBRATOR_PATH: Final[Path] = OUT_DIR / "calibrator.json"
FEATURES_PATH: Final[Path] = OUT_DIR / "feature_names.json"
METRICS_PATH: Final[Path] = OUT_DIR / "model_metrics.json"


@dataclass(frozen=True, slots=True)
class Config:
    n_users: int = 2000
    n_days: int = 60
    seed: int = 42
    incident_rate_per_user: float = 0.15   # expected fraud incidents per user over the window
    undetected_fraud_rate: float = 0.08    # fraud that never gets labelled (label noise)
    mislabel_legit_rate: float = 0.0003    # legit labelled fraud (chargeback noise)
    # Cost matrix (INR): a missed fraud costs the transaction amount;
    # every flagged tx (TP or FP) costs a review + customer-friction fee.
    review_cost: float = 250.0
    fn_loss_fraction: float = 1.0
    critical_min_precision: float = 0.80


# ───────────────────────────── Data generation ───────────────────────────
_CATEGORY_MEDIAN: Final[np.ndarray] = np.array(
    [350, 180, 1800, 600, 1400, 900, 1500, 5000, 700], dtype=float
)
_PREF_ALPHA: Final[np.ndarray] = np.array([6, 4, 2.5, 1.5, 1.5, 0.8, 0.5, 0.4, 0.8])
_CAT_IDX: Final[dict[str, int]] = {c: i for i, c in enumerate(EXPENSE_CATEGORIES)}
_DAY: Final[float] = 86_400.0

Chunk = tuple[np.ndarray, np.ndarray, np.ndarray, str]  # ts, cat_idx, amount, incident_type


def _legit_stream(
    rng: np.random.Generator, n_days: int, t0: float
) -> tuple[Chunk, float, np.ndarray]:
    """Per-user legitimate behaviour: own spend scale, category taste, chronotype."""
    scale = float(np.exp(rng.normal(0.0, 0.5)))
    prefs = rng.dirichlet(_PREF_ALPHA * 3.0)
    rate = float(np.clip(np.exp(rng.normal(np.log(2.5), 0.5)), 0.4, 10.0))
    night_owl = rng.random() < 0.12
    chrono = rng.normal(22.5, 1.5) if night_owl else float(np.clip(rng.normal(14, 2.5), 9, 19))
    spread = 4.0 if night_owl else 3.2

    n = max(int(rng.poisson(rate * n_days)), 8)
    day = rng.integers(0, n_days, n)
    hour = np.mod(rng.normal(chrono, spread, n), 24.0)
    ts = t0 + day * _DAY + hour * 3600.0
    cat = rng.choice(len(EXPENSE_CATEGORIES), n, p=prefs)
    amt = _CATEGORY_MEDIAN[cat] * scale * np.exp(rng.normal(0.0, 0.7, n))

    big = rng.random(n) < 0.02                       # legit big one-off purchases
    amt[big] *= rng.uniform(4.0, 12.0, int(big.sum()))

    ts_l, cat_l, amt_l = [ts], [cat], [amt]
    for i in np.flatnonzero(rng.random(n) < 0.03):   # legit bursts (e.g. grocery + parking)
        k = int(rng.integers(1, 4))
        c = rng.choice(len(EXPENSE_CATEGORIES), k, p=prefs)
        ts_l.append(ts[i] + np.cumsum(rng.uniform(20, 200, k)))
        cat_l.append(c)
        amt_l.append(_CATEGORY_MEDIAN[c] * scale * 0.6 * np.exp(rng.normal(0, 0.5, k)))

    chunk = (np.concatenate(ts_l), np.concatenate(cat_l), np.concatenate(amt_l), "legit")
    return chunk, scale, prefs


def _incident(
    rng: np.random.Generator, scale: float, prefs: np.ndarray, n_days: int, t0: float
) -> Chunk:
    """One attack episode. Behaviour only — no reference to model features."""
    kind = rng.choice(["card_testing", "account_takeover", "slow_drip", "spree"],
                      p=[0.30, 0.30, 0.25, 0.15])
    start = t0 + rng.uniform(0.05, 0.97) * n_days * _DAY
    n_cat = len(EXPENSE_CATEGORIES)

    if kind == "card_testing":                       # many tiny probes, then maybe a cash-out
        k = int(rng.integers(5, 16))
        ts = start + np.cumsum(rng.uniform(5, 60, k))
        cat = rng.choice([_CAT_IDX[c] for c in ("Shopping", "Entertainment", "Other", "Education")], k)
        amt = rng.uniform(1, 120, k)
        if rng.random() < 0.4:
            ts = np.append(ts, ts[-1] + rng.uniform(30, 300))
            cat = np.append(cat, _CAT_IDX["Shopping"])
            amt = np.append(amt, _CATEGORY_MEDIAN[_CAT_IDX["Shopping"]] * scale * rng.uniform(3, 12))
    elif kind == "account_takeover":                 # few, large, off-profile
        k = int(rng.integers(1, 5))
        if rng.random() < 0.6:                       # 40% strike in daytime: no free lunch
            start = np.floor(start / _DAY) * _DAY + rng.uniform(0, 5) * 3600.0
        ts = start + np.cumsum(rng.uniform(30, 1500, k))
        risky = [_CAT_IDX[c] for c in ("Shopping", "Investment", "Other", "Entertainment")]
        use_risky = rng.random(k) < 0.65
        cat = np.where(use_risky, rng.choice(risky, k, p=[0.4, 0.25, 0.2, 0.15]),
                       rng.choice(n_cat, k, p=prefs))
        amt = _CATEGORY_MEDIAN[cat] * scale * np.exp(rng.normal(np.log(6.0), 0.6, k))
    elif kind == "slow_drip":                        # mild over-spend in normal categories, over days
        k = int(rng.integers(3, 9))
        ts = start + np.sort(rng.uniform(0, 3 * _DAY, k))
        cat = rng.choice(n_cat, k, p=prefs)
        amt = _CATEGORY_MEDIAN[cat] * scale * np.exp(rng.normal(np.log(2.2), 0.5, k))
    else:                                            # stolen-card spree across categories
        k = int(rng.integers(3, 7))
        ts = start + np.cumsum(rng.uniform(120, 1800, k))
        cat = rng.integers(0, n_cat, k)
        amt = _CATEGORY_MEDIAN[cat] * scale * np.exp(rng.normal(np.log(3.0), 0.7, k))

    return np.minimum(ts, t0 + n_days * _DAY - 1), cat, amt, str(kind)


def generate_transactions(cfg: Config) -> pd.DataFrame:
    """Simulate users, inject attack incidents, apply label noise."""
    rng = np.random.default_rng(cfg.seed)
    t0 = pd.Timestamp("2026-01-01").timestamp()
    frames: list[pd.DataFrame] = []

    for uid in range(cfg.n_users):
        legit, scale, prefs = _legit_stream(rng, cfg.n_days, t0)
        chunks: list[Chunk] = [legit]
        chunks += [_incident(rng, scale, prefs, cfg.n_days, t0)
                   for _ in range(int(rng.poisson(cfg.incident_rate_per_user)))]
        for ts, cat, amt, kind in chunks:
            frames.append(pd.DataFrame({
                "user_id": uid, "ts": ts, "cat_idx": cat, "amount": amt,
                "incident_type": kind, "is_fraud": int(kind != "legit"),
            }))

    df = pd.concat(frames, ignore_index=True)
    df["category"] = np.asarray(EXPENSE_CATEGORIES)[df["cat_idx"].to_numpy()]
    df["amount"] = df["amount"].clip(lower=1.0).round(2)

    # Label noise: some fraud is never reported; a few legit txs are mislabelled.
    fraud = df["is_fraud"].to_numpy() == 1
    flip_off = fraud & (rng.random(len(df)) < cfg.undetected_fraud_rate)
    flip_on = ~fraud & (rng.random(len(df)) < cfg.mislabel_legit_rate)
    df.loc[flip_off, "is_fraud"] = 0
    df.loc[flip_on, "is_fraud"] = 1
    return df.drop(columns="cat_idx")


# ───────────────────────────── Feature engineering ───────────────────────
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute static + streaming features from the event stream (prior events only)."""
    df = df.sort_values(["user_id", "ts"], kind="mergesort").reset_index(drop=True)
    ts_all, amt_all = df["ts"].to_numpy(), df["amount"].to_numpy()
    c5 = np.zeros(len(df)); s24 = np.zeros(len(df)); ratio = np.ones(len(df))

    for idx in df.groupby("user_id").indices.values():
        t, a = ts_all[idx], amt_all[idx]
        i = np.arange(len(t))
        j5 = np.searchsorted(t, t - 300.0, side="right")
        j24 = np.searchsorted(t, t - _DAY, side="right")
        prefix = np.concatenate([[0.0], np.cumsum(a)])
        c5[idx] = i - j5
        s24[idx] = prefix[i] - prefix[j24]
        med = pd.Series(a).rolling(50, min_periods=3).median().shift(1).to_numpy()
        ratio[idx] = np.where(np.isnan(med) | (med <= 0), 1.0, a / med)

    dt = pd.to_datetime(df["ts"], unit="s")
    df["hour"] = dt.dt.hour
    df["day_of_week"] = dt.dt.dayofweek
    df["tx_count_5m"], df["tx_sum_24h"], df["amount_to_avg_ratio"] = c5, s24, ratio
    for c in EXPENSE_CATEGORIES:
        df[f"cat_{c}"] = (df["category"] == c).astype(np.float32)
    return df


def chronological_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("ts", kind="mergesort").reset_index(drop=True)
    a, b = int(len(df) * 0.70), int(len(df) * 0.85)
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


# ───────────────────────────── Evaluation helpers ────────────────────────
def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        m = which == b
        if m.any():
            ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


def cost_optimal_threshold(
    y: np.ndarray, p: np.ndarray, amount: np.ndarray, cfg: Config
) -> tuple[float, dict[str, float]]:
    """
    Sweep every cut-off. Expected cost = missed-fraud amount * loss fraction
    + review_cost * (#flagged). Returns the threshold minimising it.
    """
    order = np.argsort(-p, kind="mergesort")
    ps, ys, as_ = p[order], y[order], amount[order]
    caught_amt = np.concatenate([[0.0], np.cumsum(ys * as_)])
    flagged = np.arange(len(ps) + 1)
    cost = (caught_amt[-1] - caught_amt) * cfg.fn_loss_fraction + cfg.review_cost * flagged
    k = int(np.argmin(cost))
    if k == 0:
        thr = float(ps[0]) + 1e-9
    elif k == len(ps):
        thr = float(ps[-1])
    else:
        thr = float((ps[k - 1] + ps[k]) / 2.0)
    return thr, {"cost_at_threshold": float(cost[k]), "cost_flag_nothing": float(cost[0]),
                 "cost_flag_everything": float(cost[-1])}


def precision_threshold(y: np.ndarray, p: np.ndarray, min_precision: float, floor: float) -> float:
    """Lowest threshold >= floor whose precision on the calibration split is >= min_precision."""
    order = np.argsort(-p, kind="mergesort")
    ps, ys = p[order], y[order]
    prec = np.cumsum(ys) / np.arange(1, len(ps) + 1)
    ok = np.flatnonzero((prec >= min_precision) & (ps >= floor))
    # If nothing reaches the target precision, CRITICAL collapses to the top-scored decile of flags.
    return float(ps[ok.max()]) if ok.size else float(np.quantile(ps[ps >= floor], 0.9)) if (ps >= floor).any() else floor


def confusion_at(y: np.ndarray, p: np.ndarray, thr: float) -> dict[str, float]:
    pred = p >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    return {"precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0, "tp": tp, "fp": fp, "fn": fn}


# ───────────────────────────── ONNX helpers ──────────────────────────────
def export_onnx(model: LGBMClassifier, n_features: int, path: Path) -> None:
    onx = convert_lightgbm(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        zipmap=False,
    )
    path.write_bytes(onx.SerializeToString())


def new_session(path: Path) -> ort.InferenceSession:
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])


def prob_output_name(sess: ort.InferenceSession) -> str:
    """Name of the class-probability output (the 2nd output of a converted classifier)."""
    return sess.get_outputs()[1].name


def onnx_proba(sess: ort.InferenceSession, X: np.ndarray) -> np.ndarray:
    feed = {sess.get_inputs()[0].name: np.ascontiguousarray(X, dtype=np.float32)}
    probs = np.asarray(sess.run([prob_output_name(sess)], feed)[0])
    return probs[:, 1] if probs.ndim == 2 else probs


def benchmark(fn: Any, n: int = 2000, warmup: int = 100) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    lat = np.empty(n)
    for i in range(n):
        t = time.perf_counter(); fn(); lat[i] = (time.perf_counter() - t) * 1000.0
    return {"p50_ms": round(float(np.percentile(lat, 50)), 3),
            "p99_ms": round(float(np.percentile(lat, 99)), 3)}


# ───────────────────────────── Training ──────────────────────────────────
def _fit(X_tr: pd.DataFrame, y_tr: pd.Series, X_es: pd.DataFrame, y_es: pd.Series,
         spw: float, seed: int, n_estimators: int = 1500) -> LGBMClassifier:
    model = LGBMClassifier(
        objective="binary", n_estimators=n_estimators, learning_rate=0.03, num_leaves=31,
        min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        reg_lambda=5.0, scale_pos_weight=spw, random_state=seed, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_es, y_es)], eval_metric="auc",
              callbacks=[lgb.early_stopping(100, first_metric_only=True, min_delta=1e-4, verbose=False)])
    return model


def train(cfg: Config) -> dict[str, Any]:
    log.info("Simulating transactions (users=%d, days=%d)...", cfg.n_users, cfg.n_days)
    df = add_features(generate_transactions(cfg))
    train_df, calib_df, test_df = chronological_split(df)
    # Early-stopping slice = chronological tail of train (never touches calib/test).
    cut = int(len(train_df) * 0.8)
    core_df, es_df = train_df.iloc[:cut], train_df.iloc[cut:]
    for name, part in (("core", core_df), ("early-stop", es_df), ("calib", calib_df), ("test", test_df)):
        if part["is_fraud"].sum() < 20:
            raise RuntimeError(f"Too few fraud positives in {name} split; increase n_users/n_days.")
    log.info("rows=%s | fraud rate=%.3f%%", f"{len(df):,}", df["is_fraud"].mean() * 100)

    y_core = core_df["is_fraud"]
    n_pos, n_neg = int(y_core.sum()), int((y_core == 0).sum())
    spw = n_neg / n_pos                                    # scale_pos_weight = N_neg / N_pos
    log.info("scale_pos_weight = %d / %d = %.2f", n_neg, n_pos, spw)

    model = _fit(core_df[FEATURE_NAMES], y_core, es_df[FEATURE_NAMES], es_df["is_fraud"], spw, cfg.seed)
    best_iter = int(model.best_iteration_ or model.n_estimators)
    log.info("best iteration: %d", best_iter)

    # ── ONNX export + parity check against native LightGBM ──────────────
    export_onnx(model, len(FEATURE_NAMES), ONNX_PATH)
    sess = new_session(ONNX_PATH)
    sample = test_df[FEATURE_NAMES].to_numpy(dtype=np.float32)
    diff = np.abs(onnx_proba(sess, sample) - model.predict_proba(sample)[:, 1])
    parity_max, parity_p999 = float(diff.max()), float(np.percentile(diff, 99.9))
    # float32 thresholds in ONNX can flip a branch for a handful of rows sitting exactly on a split.
    if parity_p999 > 1e-4:
        raise RuntimeError(f"ONNX/LightGBM parity failed (p99.9 abs diff {parity_p999:.2e}).")
    log.info("ONNX parity: p99.9=%.2e max=%.2e (%d/%d rows >1e-4)",
             parity_p999, parity_max, int((diff > 1e-4).sum()), len(diff))
    model.booster_.save_model(str(BOOSTER_PATH))

    # ── Calibration (isotonic) on the held-out calibration split ───────
    raw_cal = onnx_proba(sess, calib_df[FEATURE_NAMES].to_numpy())
    raw_test = onnx_proba(sess, test_df[FEATURE_NAMES].to_numpy())
    y_cal, y_test = calib_df["is_fraud"].to_numpy(), test_df["is_fraud"].to_numpy()
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw_cal, y_cal)
    CALIBRATOR_PATH.write_text(json.dumps({
        "x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist()}))
    cal_cal = np.interp(raw_cal, iso.X_thresholds_, iso.y_thresholds_)
    cal_test = np.interp(raw_test, iso.X_thresholds_, iso.y_thresholds_)

    # ── Thresholds tuned on calibration split, judged on test ──────────
    amt_cal, amt_test = calib_df["amount"].to_numpy(), test_df["amount"].to_numpy()
    flag_thr, cal_costs = cost_optimal_threshold(y_cal, cal_cal, amt_cal, cfg)
    crit_thr = max(precision_threshold(y_cal, cal_cal, cfg.critical_min_precision, flag_thr), flag_thr)
    tiers = {"medium": round(flag_thr / 2.0, 6), "high": round(flag_thr, 6), "critical": round(crit_thr, 6)}
    _, test_costs = cost_optimal_threshold(y_test, cal_test, amt_test, cfg)
    test_cost_at_thr = float(
        (amt_test * y_test * (cal_test < flag_thr)).sum() * cfg.fn_loss_fraction
        + cfg.review_cost * (cal_test >= flag_thr).sum()
    )

    recall_by_attack = {
        k: round(float((cal_test[(test_df["incident_type"] == k).to_numpy() & (y_test == 1)] >= flag_thr).mean()), 3)
        for k in ("card_testing", "account_takeover", "slow_drip", "spree")
        if ((test_df["incident_type"] == k).to_numpy() & (y_test == 1)).any()
    }

    # ── Ablation: how much do velocity features buy us? ────────────────
    static = _fit(core_df[STATIC_FEATURES], y_core, es_df[STATIC_FEATURES], es_df["is_fraud"], spw, cfg.seed)
    pr_static = float(average_precision_score(y_test, static.predict_proba(test_df[STATIC_FEATURES])[:, 1]))

    # ── Serving latency (single-row, 1 thread) ─────────────────────────
    row = test_df[FEATURE_NAMES].head(1).to_numpy(dtype=np.float32)
    iname = sess.get_inputs()[0].name
    pname = prob_output_name(sess)
    lat_onnx = benchmark(lambda: sess.run([pname], {iname: row}))
    booster = lgb.Booster(model_file=str(BOOSTER_PATH))
    lat_shap = benchmark(lambda: booster.predict(row, pred_contrib=True, num_threads=1), n=1000, warmup=50)

    version = hashlib.sha256(ONNX_PATH.read_bytes()).hexdigest()[:12]
    metrics: dict[str, Any] = {
        "model_version": version,
        "data_source": "behavioural simulation: attack incidents injected into per-user streams; "
                       "features computed post-hoc from the event stream (see generate_transactions)",
        "config": asdict(cfg),
        "n_rows": int(len(df)),
        "fraud_rate": round(float(df["is_fraud"].mean()), 5),
        "split": {"train_core": len(core_df), "early_stop": len(es_df),
                  "calibration": len(calib_df), "test": len(test_df), "scheme": "chronological 70/15/15"},
        "scale_pos_weight": round(spw, 3),
        "best_iteration": best_iter,
        "features": FEATURE_NAMES,
        "test": {
            "roc_auc": round(float(roc_auc_score(y_test, cal_test)), 4),
            "pr_auc": round(float(average_precision_score(y_test, cal_test)), 4),
            "pr_auc_baseline_prevalence": round(float(y_test.mean()), 5),
            "pr_auc_static_features_only": round(pr_static, 4),
            "brier_raw": round(float(brier_score_loss(y_test, raw_test)), 6),
            "brier_calibrated": round(float(brier_score_loss(y_test, cal_test)), 6),
            "ece_raw": round(expected_calibration_error(y_test, raw_test), 5),
            "ece_calibrated": round(expected_calibration_error(y_test, cal_test), 5),
            "at_flag_threshold": {k: round(v, 4) if isinstance(v, float) else v
                                  for k, v in confusion_at(y_test, cal_test, flag_thr).items()},
            "recall_by_attack_type": recall_by_attack,
            "expected_cost": {"model": round(test_cost_at_thr, 2),
                              "flag_nothing": round(test_costs["cost_flag_nothing"], 2),
                              "flag_everything": round(test_costs["cost_flag_everything"], 2)},
        },
        "thresholds": tiers,
        "calibration_split_costs": {k: round(v, 2) for k, v in cal_costs.items()},
        "serving": {"onnx_parity_abs_diff": {"p99_9": parity_p999, "max": parity_max,
                                             "rows_over_1e-4": int((diff > 1e-4).sum()), "rows": len(diff)}, "onnx_single_row": lat_onnx,
                    "treeshap_single_row": lat_shap},
    }
    FEATURES_PATH.write_text(json.dumps(FEATURE_NAMES))
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Train the FinMind AI fraud model.")
    p.add_argument("--n-users", type=int, default=Config().n_users)
    p.add_argument("--n-days", type=int, default=Config().n_days)
    p.add_argument("--seed", type=int, default=Config().seed)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    m = train(Config(n_users=a.n_users, n_days=a.n_days, seed=a.seed))
    print(json.dumps({k: m[k] for k in ("model_version", "fraud_rate", "test", "thresholds", "serving")}, indent=2))


if __name__ == "__main__":
    main()
