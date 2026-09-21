"""Tests for supervised dataset creation, chronological splitting, and leakage prevention."""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.features import FeatureEngineer
from backend.app.ml.labels import compute_future_returns_and_labels, LabelConfig
from backend.app.ml.dataset import build_supervised_dataset, MLDataset
from backend.app.ml.split import TimeAwareSplitter, FeatureScaler


def create_sample_ohlcv(n: int = 150) -> pd.DataFrame:
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


def test_label_future_mutation_behavior():
    """MANDATORY REGRESSION TEST 2:

    Mutating future prices at t+1 MUST alter labels that look ahead past t,
    while leaving historical input features before t completely unchanged.
    """
    df_orig = create_sample_ohlcv(100)
    cfg = LabelConfig(horizon=5, threshold=0.0)

    lbls_orig = compute_future_returns_and_labels(df_orig, cfg)
    fe = FeatureEngineer()
    feats_orig = fe.compute_features(df_orig)

    t_idx = 50

    # Mutate future prices from t_idx+1 onward
    df_mut = df_orig.copy()
    # Spike prices way up
    df_mut.loc[t_idx + 1 :, "close"] = df_mut.loc[t_idx + 1 :, "close"] * 10.0

    lbls_mut = compute_future_returns_and_labels(df_mut, cfg)
    feats_mut = fe.compute_features(df_mut)

    # 1. Features at or before t_idx must be UNCHANGED
    for col in feats_orig.columns:
        valid_mask = feats_orig.iloc[: t_idx + 1][col].notna()
        if valid_mask.any():
            diff = np.abs(feats_orig.iloc[: t_idx + 1].loc[valid_mask, col] - feats_mut.iloc[: t_idx + 1].loc[valid_mask, col])
            assert diff.max() == 0.0

    # 2. Labels looking forward across the mutation boundary (e.g. t_idx) MUST change
    # At t_idx, future_close looked at t_idx + 5, which was spiked by 10x
    assert lbls_mut.loc[t_idx, "future_return"] > lbls_orig.loc[t_idx, "future_return"]
    assert lbls_mut.loc[t_idx, "label"] == 1


def test_dataset_alignment_and_nan_trimming():
    """Verifies that MLDataset trims indicator warmup and horizon tail NaNs."""
    df = create_sample_ohlcv(120)
    fe = FeatureEngineer()
    lc = LabelConfig(horizon=5, threshold=0.0)

    dataset = build_supervised_dataset(df, feature_engineer=fe, label_config=lc, symbol="AAPL")

    assert len(dataset.X) == len(dataset.y)
    assert len(dataset.X) == len(dataset.timestamps)
    assert not dataset.X.isna().any().any(), "Features matrix must not contain any NaNs."
    assert not dataset.y.isna().any(), "Labels must not contain any NaNs."

    # Verify trimmed bars count
    assert len(dataset.X) < len(df)
    # The last 5 bars of raw data cannot have labels
    raw_last_date = df["timestamp"].iloc[-1]
    dataset_last_date = dataset.timestamps.iloc[-1]
    assert dataset_last_date < raw_last_date


def test_chronological_split_isolation():
    """MANDATORY REGRESSION TEST 3:

    Training partition CANNOT contain the final test window.
    Strict chronological order: Train end < Validation start < Test start.
    """
    df = create_sample_ohlcv(140)
    dataset = build_supervised_dataset(df)

    splits = TimeAwareSplitter.split(
        dataset,
        train_pct=0.60,
        val_pct=0.20,
        test_pct=0.20,
        scale_method="standard",
    )

    train_end = splits.train_window[1]
    assert splits.val_window is not None
    val_start = splits.val_window[0]
    val_end = splits.val_window[1]
    test_start = splits.test_window[0]

    assert train_end < val_start, f"Train end ({train_end}) must be before Val start ({val_start})"
    assert val_end < test_start, f"Val end ({val_end}) must be before Test start ({test_start})"
    assert train_end < test_start, f"Train end ({train_end}) must be before Test start ({test_start})"


def test_scaler_fitted_only_on_train():
    """MANDATORY REGRESSION TEST 4:

    Feature scaler must be fitted strictly and exclusively on the training partition.
    Test and validation data must NEVER leak into mean/std calculation.
    """
    df = create_sample_ohlcv(150)
    dataset = build_supervised_dataset(df)

    splits = TimeAwareSplitter.split(dataset, train_pct=0.6, val_pct=0.2, test_pct=0.2, scale_method="standard")

    # The scaler means stored must exactly equal the mean of the raw X_train
    # Recompute raw unscaled train partition
    n_train = len(splits.X_train)
    raw_X_train = dataset.X.iloc[:n_train]

    scaler = splits.scaler
    assert scaler.means is not None
    assert scaler.scales is not None

    for col in dataset.feature_names:
        expected_mean = float(raw_X_train[col].mean())
        expected_std = float(raw_X_train[col].std())

        actual_mean = scaler.means[col]
        actual_scale = scaler.scales[col]

        assert np.isclose(actual_mean, expected_mean, atol=1e-6)
        assert np.isclose(actual_scale, expected_std, atol=1e-6)
