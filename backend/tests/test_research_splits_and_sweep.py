"""Tests for chronological train/val/test splitting and parameter sweeps."""

import pandas as pd
import pytest
from backend.app.research.splits import chronological_split
from backend.app.research.sweep import ParameterSweepRunner
from backend.app.research.config import (
    ExperimentConfig,
    DatasetConfig,
    StrategyConfig,
    PortfolioConfig,
    ExecutionConfig,
    RiskConfig,
)
from backend.app.research.runner import ExperimentRunner
from backend.app.research.storage import SQLiteExperimentStorage


def _make_dummy_df(n: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n)
    prices = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1000] * n,
    })


def test_chronological_split_integrity():
    df = _make_dummy_df(100)
    splits = chronological_split(df, train_pct=0.60, val_pct=0.20, test_pct=0.20)

    assert splits.train_bars == 60
    assert splits.val_bars == 20
    assert splits.test_bars == 20

    # Strict non-overlapping chronological ordering
    assert splits.train_df["timestamp"].max() < splits.val_df["timestamp"].min()
    assert splits.val_df["timestamp"].max() < splits.test_df["timestamp"].min()

    # Zero leakage: disjoint timestamp sets
    ts_train = set(splits.train_df["timestamp"])
    ts_val = set(splits.val_df["timestamp"])
    ts_test = set(splits.test_df["timestamp"])

    assert len(ts_train.intersection(ts_val)) == 0
    assert len(ts_val.intersection(ts_test)) == 0
    assert len(ts_train.intersection(ts_test)) == 0


def test_chronological_split_validation_errors():
    df = _make_dummy_df(20)

    # Fractions do not sum to 1.0
    with pytest.raises(ValueError, match="sum to 1.0"):
        chronological_split(df, train_pct=0.5, val_pct=0.2, test_pct=0.2)

    # Negative fraction
    with pytest.raises(ValueError, match="positive"):
        chronological_split(df, train_pct=-0.1, val_pct=0.5, test_pct=0.6)


def test_parameter_sweep_grid_expansion():
    grid = {
        "fast_period": [5, 10],
        "slow_period": [20, 30, 40],
    }
    combos = ParameterSweepRunner.expand_grid(grid)
    assert len(combos) == 6
    assert combos[0] == {"fast_period": 5, "slow_period": 20}
    assert combos[-1] == {"fast_period": 10, "slow_period": 40}


def test_parameter_sweep_execution_and_overfitting_safeguard():
    storage = SQLiteExperimentStorage(db_path=":memory:")
    runner = ExperimentRunner(storage=storage)
    sweep_runner = ParameterSweepRunner(runner=runner)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL_sample", symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 10, "slow_period": 30}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0),
        risk=RiskConfig(position_sizing_method="percent_equity", position_size_pct=0.20),
    )

    grid = {
        "fast_period": [5, 10],
        "slow_period": [15, 25],
    }

    # 1. Successful sweep on train split
    result = sweep_runner.run_sweep(config, grid, eval_split="train")
    assert result.total_combinations == 4
    assert result.eval_split_used == "train"
    assert result.test_quarantine_enforced is True
    assert len(result.leaderboard) == 4
    assert result.best_by_sharpe is not None

    # 2. Overfitting safeguard: Rejects eval_split='test'
    with pytest.raises(ValueError, match="Overfitting safeguard"):
        sweep_runner.run_sweep(config, grid, eval_split="test")
