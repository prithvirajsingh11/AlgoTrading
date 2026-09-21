"""Tests for feature engineering and mandatory zero-lookahead data leakage prevention."""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.features import FeatureEngineer, FeatureConfig, FEATURE_METADATA


def create_sample_ohlcv(n: int = 150) -> pd.DataFrame:
    """Generates synthetic OHLCV time series for testing."""
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    np.random.seed(42)
    # Price random walk
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


def test_feature_generation_shapes_and_values():
    """Verifies that all technical indicator features are calculated and documented."""
    df = create_sample_ohlcv(120)
    fe = FeatureEngineer()
    feats = fe.compute_features(df)

    assert not feats.empty
    assert len(feats) == len(df)

    # Check key indicator columns exist
    expected_cols = [
        "log_return",
        "simple_return",
        "sma_distance_10",
        "sma_distance_20",
        "sma_distance_50",
        "ema_distance_10",
        "ema_distance_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr_14",
        "rolling_volatility_20",
        "rolling_volume_ratio_20",
        "rolling_volume_std_20",
        "price_momentum_5",
        "price_momentum_10",
        "high_low_range",
        "close_open_range",
    ]

    for col in expected_cols:
        assert col in feats.columns, f"Missing feature column: {col}"
        # Also ensure documented in FEATURE_METADATA
        assert col in FEATURE_METADATA, f"Feature not documented in metadata registry: {col}"
        assert FEATURE_METADATA[col]["type"] in ("current_bar", "lagged", "rolling")


def test_feature_zero_lookahead_regression():
    """MANDATORY REGRESSION TEST 1:

    Mutating future prices at t+1 must NOT alter feature values at or before timestamp t.
    """
    df_original = create_sample_ohlcv(100)
    fe = FeatureEngineer()

    feats_orig = fe.compute_features(df_original)

    # Choose split point t = 60
    t_idx = 60

    # Create mutated future dataframe starting at t+1
    df_mutated = df_original.copy()
    # Drastically mutate future prices from t+1 onwards
    df_mutated.loc[t_idx + 1 :, "close"] = df_mutated.loc[t_idx + 1 :, "close"] * 5.0
    df_mutated.loc[t_idx + 1 :, "high"] = df_mutated.loc[t_idx + 1 :, "high"] * 5.5
    df_mutated.loc[t_idx + 1 :, "low"] = df_mutated.loc[t_idx + 1 :, "low"] * 4.5
    df_mutated.loc[t_idx + 1 :, "open"] = df_mutated.loc[t_idx + 1 :, "open"] * 4.8
    df_mutated.loc[t_idx + 1 :, "volume"] = df_mutated.loc[t_idx + 1 :, "volume"] * 10.0

    feats_mutated = fe.compute_features(df_mutated)

    # Invariant: Features at rows 0..t must be 100% bit-for-bit identical
    slice_orig = feats_orig.iloc[: t_idx + 1]
    slice_mutated = feats_mutated.iloc[: t_idx + 1]

    for col in feats_orig.columns:
        valid_mask = slice_orig[col].notna()
        if valid_mask.any():
            diff = np.abs(slice_orig.loc[valid_mask, col] - slice_mutated.loc[valid_mask, col])
            max_diff = diff.max()
            assert max_diff == 0.0 or np.isnan(max_diff), (
                f"Data leakage detected in feature '{col}'! "
                f"Max discrepancy at or before t: {max_diff}"
            )


def test_compute_bar_features_matches_full_vector():
    """Verifies that single bar feature computation matches the last row of full vectorized features."""
    df = create_sample_ohlcv(80)
    fe = FeatureEngineer()

    full_feats = fe.compute_features(df)
    bar_feats = fe.compute_bar_features(df)

    assert len(bar_feats) == 1
    last_row_full = full_feats.iloc[[-1]]

    for col in full_feats.columns:
        v1 = float(last_row_full[col].iloc[0])
        v2 = float(bar_feats[col].iloc[0])
        assert np.isclose(v1, v2, atol=1e-8)
