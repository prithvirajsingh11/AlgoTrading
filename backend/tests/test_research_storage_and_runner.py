"""Tests for SQLiteExperimentStorage and ExperimentRunner."""

import pytest
from backend.app.research.storage import SQLiteExperimentStorage
from backend.app.research.runner import ExperimentRunner
from backend.app.research.config import (
    ExperimentConfig,
    DatasetConfig,
    StrategyConfig,
    PortfolioConfig,
    ExecutionConfig,
    RiskConfig,
    BacktestingConfig,
)


def test_sqlite_storage_crud(tmp_path):
    db_path = tmp_path / "test_experiments.db"
    storage = SQLiteExperimentStorage(db_path=db_path)

    # Initially empty
    assert len(storage.list_experiments()) == 0

    # Save dummy experiment
    from backend.app.research.result import ExperimentResult
    res = ExperimentResult(
        experiment_id="exp_test_123",
        configuration_hash="hash_123",
        config={"strategy": {"name": "SMA"}},
        dataset_metadata={"dataset_id": "AAPL"},
        strategy_info={"name": "SMA"},
        metrics={"sharpe_ratio": 1.25, "total_return": 0.15, "maximum_drawdown": 0.05},
        trade_records=[],
        equity_curve=[],
        drawdown_curve=[],
        execution_statistics={"total_bars": 100},
    )

    exp_id = storage.save_experiment(res)
    assert exp_id == "exp_test_123"

    # Load experiment
    loaded = storage.load_experiment("exp_test_123")
    assert loaded is not None
    assert loaded.experiment_id == "exp_test_123"
    assert loaded.metrics["sharpe_ratio"] == 1.25

    # List experiments
    exp_list = storage.list_experiments()
    assert len(exp_list) == 1
    assert exp_list[0]["experiment_id"] == "exp_test_123"
    assert exp_list[0]["sharpe_ratio"] == 1.25

    # Delete experiment
    deleted = storage.delete_experiment("exp_test_123")
    assert deleted is True
    assert storage.load_experiment("exp_test_123") is None
    assert len(storage.list_experiments()) == 0


def test_experiment_runner_standard_mode():
    storage = SQLiteExperimentStorage(db_path=":memory:")
    runner = ExperimentRunner(storage=storage)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL_sample", symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 20}),
        portfolio=PortfolioConfig(initial_capital=50_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0),
        risk=RiskConfig(position_sizing_method="percent_equity", position_size_pct=0.20),
    )

    result = runner.run_experiment(config)
    assert result.experiment_id.startswith("exp_")
    assert "sharpe_ratio" in result.metrics
    assert len(result.equity_curve) > 0
    assert len(result.drawdown_curve) == len(result.equity_curve)
    assert result.execution_statistics["total_bars"] > 0
    assert result.walk_forward_results is None

    # Verify saved in storage
    saved = storage.load_experiment(result.experiment_id)
    assert saved is not None
    assert saved.experiment_id == result.experiment_id


def test_experiment_runner_walk_forward_integration():
    storage = SQLiteExperimentStorage(db_path=":memory:")
    runner = ExperimentRunner(storage=storage)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL_sample", symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 15}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0, slippage_bps=0.0),
        backtesting=BacktestingConfig(
            mode="walk_forward",
            walk_forward_params={"train_bars": 60, "test_bars": 30, "step_bars": 30},
        ),
    )

    result = runner.run_experiment(config)
    assert result.walk_forward_results is not None
    assert result.walk_forward_results["total_windows"] > 0
    assert len(result.walk_forward_results["windows"]) > 0
    assert "sharpe_ratio" in result.metrics
    assert len(result.equity_curve) > 0
