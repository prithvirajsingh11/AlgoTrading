"""Tests for model artifact serialization, schema validation, and inference."""

import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from backend.app.ml.train import train_ml_pipeline
from backend.app.ml.artifacts import MLModelArtifact
from backend.app.ml.inference import MLPredictor, MLPrediction


def create_sample_ohlcv(n: int = 140) -> pd.DataFrame:
    """Generates synthetic OHLCV time series for testing."""
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    np.random.seed(42)
    rets = np.random.normal(0.0005, 0.015, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    opens = prices * (1.0 + np.random.normal(0, 0.003, n))
    highs = np.maximum(prices, opens) * (1.0 + np.abs(np.random.normal(0.002, 0.005, n)))
    lows = np.minimum(prices, opens) * (1.0 - np.abs(np.random.normal(0.002, 0.005, n)))
    vols = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": vols,
    })


def test_model_artifact_save_and_load():
    """Verifies complete save and load round-trip of MLModelArtifact."""
    df = create_sample_ohlcv(120)
    train_res = train_ml_pipeline(df, symbol="AAPL")
    art = train_res.artifact

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model_v1.json")
        art.save(path)
        assert os.path.exists(path)

        loaded = MLModelArtifact.load(path)
        assert loaded.model_version == art.model_version
        assert loaded.feature_schema_hash == art.feature_schema_hash
        assert loaded.feature_names == art.feature_names
        assert loaded.training_period == art.training_period

        # Reconstructed model can predict
        predictor = MLPredictor(loaded)
        sample_row = pd.DataFrame([np.zeros(len(loaded.feature_names))], columns=loaded.feature_names)
        pred = predictor.predict_bar(sample_row, "2023-06-01", "AAPL")
        assert isinstance(pred, MLPrediction)
        assert 0.0 <= pred.probability_positive <= 1.0


def test_model_artifact_schema_validation():
    """Verifies that schema validation rejects missing, extra, or reordered features."""
    df = create_sample_ohlcv(120)
    train_res = train_ml_pipeline(df, symbol="MSFT")
    art = train_res.artifact

    # Valid schema passes
    art.validate_feature_schema(art.feature_names)

    # Missing column raises ValueError
    missing_cols = art.feature_names[:-1]
    with pytest.raises(ValueError, match="Feature schema mismatch"):
        art.validate_feature_schema(missing_cols)

    # Extra column raises ValueError
    extra_cols = art.feature_names + ["future_leak_indicator"]
    with pytest.raises(ValueError, match="Feature schema mismatch"):
        art.validate_feature_schema(extra_cols)

    # Reordered columns raise ValueError
    if len(art.feature_names) >= 2:
        reordered = list(art.feature_names)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        with pytest.raises(ValueError, match="Feature schema mismatch"):
            art.validate_feature_schema(reordered)


def test_structured_prediction_output():
    """Verifies that MLPredictor returns properly populated MLPrediction dataclass."""
    df = create_sample_ohlcv(120)
    train_res = train_ml_pipeline(df, symbol="NVDA")
    predictor = MLPredictor(train_res.artifact)

    sample_row = pd.DataFrame([np.zeros(len(train_res.artifact.feature_names))], columns=train_res.artifact.feature_names)
    pred = predictor.predict_bar(sample_row, timestamp="2023-05-15", symbol="NVDA")

    assert pred.symbol == "NVDA"
    assert pred.timestamp == "2023-05-15"
    assert pred.predicted_class in (0, 1)
    assert 0.0 <= pred.probability_positive <= 1.0
    assert 0.0 <= pred.probability_negative <= 1.0
    assert np.isclose(pred.probability_positive + pred.probability_negative, 1.0, atol=1e-3)
    assert pred.model_version == train_res.artifact.model_version
    assert pred.feature_schema_hash == train_res.artifact.feature_schema_hash

    # to_dict verification
    p_dict = pred.to_dict()
    assert "probability_positive" in p_dict
    assert "feature_schema_hash" in p_dict
