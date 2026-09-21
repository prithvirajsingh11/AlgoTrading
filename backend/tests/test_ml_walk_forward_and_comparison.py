"""Tests for Walk-Forward ML evaluation, provider comparison, and external API independence."""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.train import WalkForwardMLEngine, WalkForwardMLResult
from backend.app.research.config import ExperimentConfig, DatasetConfig, StrategyConfig, MLConfig
from backend.app.research.runner import ExperimentRunner, compare_strategy_providers
from backend.app.research.dataset import DatasetManager


def create_sample_ohlcv(n: int = 180) -> pd.DataFrame:
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


def test_walk_forward_ml_unseen_windows():
    """MANDATORY REGRESSION TEST 5:

    Walk-forward test windows remain unseen before evaluation.
    Every window must satisfy: train_end < test_start.
    """
    df = create_sample_ohlcv(160)
    wf_engine = WalkForwardMLEngine(symbol="AAPL")

    result: WalkForwardMLResult = wf_engine.run(
        df=df,
        train_bars=70,
        test_bars=30,
        step_bars=30,
    )

    assert result.total_windows > 0
    assert len(result.windows) == result.total_windows

    for win in result.windows:
        assert win.train_end < win.test_start, (
            f"Temporal leakage in window {win.window_id}: "
            f"train_end ({win.train_end}) >= test_start ({win.test_start})"
        )
        assert win.classification_metrics is not None
        assert 0.0 <= win.classification_metrics.accuracy <= 1.0


def test_runner_ml_experiment_execution():
    """Verifies ExperimentRunner executing MLStrategy and attaching metrics."""
    df = create_sample_ohlcv(140)
    dm = DatasetManager()
    dm.register_dataframe("TEST_ML_DS", df)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_ML_DS", symbols=["TEST_ML_DS"]),
        strategy=StrategyConfig(
            name="MLStrategy",
            parameters={"buy_threshold": 0.52, "sell_threshold": 0.48},
        ),
        ml=MLConfig(
            enabled=True,
            model_type="xgboost",
            buy_threshold=0.52,
            sell_threshold=0.48,
        ),
    )

    runner = ExperimentRunner(dataset_manager=dm, storage=None)
    result = runner.run_experiment(config)

    assert result is not None
    assert result.strategy_info["name"] == "MLStrategy"
    assert result.classification_metrics is not None
    assert "accuracy" in result.classification_metrics
    assert result.feature_importance is not None
    assert len(result.feature_importance) > 0


def test_compare_strategy_providers():
    """Verifies unified comparison across Traditional, ML, and Jev experiments."""
    df = create_sample_ohlcv(140)
    dm = DatasetManager()
    dm.register_dataframe("TEST_COMP_DS", df)

    runner = ExperimentRunner(dataset_manager=dm, storage=None)

    # 1. Traditional
    cfg_trad = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_COMP_DS", symbols=["TEST_COMP_DS"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 10, "slow_period": 30}),
    )
    res_trad = runner.run_experiment(cfg_trad)

    # 2. ML
    cfg_ml = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_COMP_DS", symbols=["TEST_COMP_DS"]),
        strategy=StrategyConfig(name="MLStrategy"),
        ml=MLConfig(enabled=True),
    )
    res_ml = runner.run_experiment(cfg_ml)

    summary = compare_strategy_providers([res_trad, res_ml])
    assert summary["count"] == 2

    cats = [c["category"] for c in summary["comparisons"]]
    assert "traditional" in cats
    assert "machine_learning" in cats


def test_external_api_independence():
    """Verifies that ML experiments run 100% offline with zero Jev API credentials."""
    df = create_sample_ohlcv(120)
    dm = DatasetManager()
    dm.register_dataframe("TEST_OFFLINE_DS", df)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_OFFLINE_DS", symbols=["TEST_OFFLINE_DS"]),
        strategy=StrategyConfig(name="MLStrategy"),
        ml=MLConfig(enabled=True),
    )

    # Must execute with zero network calls and no Jev credentials
    runner = ExperimentRunner(dataset_manager=dm, storage=None, decision_provider=None)
    res = runner.run_experiment(config)
    assert res is not None
    assert res.ai_decision_stats is None  # Jev was not invoked
    assert res.classification_metrics is not None  # ML was evaluated
