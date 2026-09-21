"""Tests for XGBoost model wrapper, deterministic seed reproduction, metrics, and calibration."""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.dataset import build_supervised_dataset
from backend.app.ml.split import TimeAwareSplitter
from backend.app.ml.model import XGBoostModel, XGBoostModelConfig
from backend.app.ml.evaluate import evaluate_classification
from backend.app.ml.calibration import ProbabilityCalibrator


def create_sample_ohlcv(n: int = 160) -> pd.DataFrame:
    """Generates synthetic OHLCV time series for testing."""
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    np.random.seed(42)
    rets = np.random.normal(0.0005, 0.015, n)
    prices = 100.0 * np.cumprod(1.0 + rets)

    highs = prices * (1.0 + np.abs(np.random.normal(0, 0.005, n)))
    lows = prices * (1.0 - np.abs(np.random.normal(0, 0.005, n)))
    opens = prices * (1.0 + np.random.normal(0, 0.003, n))
    vols = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": vols,
    })


def test_xgboost_deterministic_training():
    """Verifies that identical seed and inputs produce identical predictions."""
    df = create_sample_ohlcv(140)
    dataset = build_supervised_dataset(df)
    splits = TimeAwareSplitter.split(dataset, train_pct=0.7, val_pct=0.0, test_pct=0.3)

    cfg = XGBoostModelConfig(n_estimators=30, max_depth=3, random_seed=42)

    # Run 1
    m1 = XGBoostModel(config=cfg)
    m1.fit(splits.X_train, splits.y_train)
    p1 = m1.predict_proba(splits.X_test)

    # Run 2 with identical seed
    m2 = XGBoostModel(config=cfg)
    m2.fit(splits.X_train, splits.y_train)
    p2 = m2.predict_proba(splits.X_test)

    # Invariant: identical probabilities
    assert np.allclose(p1, p2, atol=1e-7), "Model predictions must be deterministic with fixed seed."


def test_feature_importance_extraction():
    """Verifies that feature importance is extracted and normalized."""
    df = create_sample_ohlcv(140)
    dataset = build_supervised_dataset(df)
    splits = TimeAwareSplitter.split(dataset, train_pct=0.7, val_pct=0.0, test_pct=0.3)

    cfg = XGBoostModelConfig(n_estimators=40, max_depth=3, random_seed=42)
    m = XGBoostModel(config=cfg)
    m.fit(splits.X_train, splits.y_train)

    importance = m.get_feature_importance()
    assert isinstance(importance, dict)
    assert len(importance) == len(dataset.feature_names)
    total = sum(importance.values())
    assert np.isclose(total, 1.0, atol=1e-3) or total == 0.0


def test_classification_metrics():
    """Verifies calculation of accuracy, precision, recall, F1, ROC-AUC, Brier score, and confusion matrix."""
    y_true = np.array([0, 1, 0, 1, 1, 0, 0, 1])
    y_pred = np.array([0, 1, 0, 0, 1, 0, 1, 1])
    y_prob = np.array([[0.8, 0.2], [0.1, 0.9], [0.7, 0.3], [0.6, 0.4], [0.2, 0.8], [0.9, 0.1], [0.4, 0.6], [0.3, 0.7]])

    metrics = evaluate_classification(y_true, y_pred, y_prob)

    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.f1 <= 1.0
    assert metrics.roc_auc is not None and 0.0 <= metrics.roc_auc <= 1.0
    assert metrics.brier_score is not None
    assert len(metrics.confusion_matrix) == 2
    assert metrics.total_samples == 8


def test_probability_calibrator_behavior():
    """Verifies calibrator fallback on small sample and fit on adequate sample."""
    # 1. Fallback on small sample
    cal_small = ProbabilityCalibrator(method="sigmoid", min_samples=50)
    probs_small = np.array([0.2, 0.4, 0.7, 0.9])
    y_small = np.array([0, 0, 1, 1])
    cal_small.fit(probs_small, y_small)
    assert cal_small.report is not None
    assert not cal_small.report.calibrated
    assert "below threshold" in str(cal_small.report.warning)

    # Calibrate returns uncalibrated when skipped
    out = cal_small.calibrate(probs_small)
    assert np.allclose(out, probs_small)

    # 2. Fit with adequate sample
    np.random.seed(42)
    n = 100
    y_large = np.random.binomial(1, 0.5, n)
    probs_large = np.clip(y_large + np.random.normal(0, 0.3, n), 0.05, 0.95)

    cal_large = ProbabilityCalibrator(method="sigmoid", min_samples=50)
    cal_large.fit(probs_large, y_large)
    assert cal_large.report is not None
    assert cal_large.report.calibrated
    assert cal_large.report.brier_after is not None
