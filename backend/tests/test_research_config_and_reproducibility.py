"""Tests for ExperimentConfig, deterministic hashing, and exact reproducibility."""

import pandas as pd
from backend.app.research.config import (
    ExperimentConfig,
    DatasetConfig,
    StrategyConfig,
    PortfolioConfig,
    ExecutionConfig,
    RiskConfig,
    BacktestingConfig,
    compute_config_hash,
)
from backend.app.research.runner import ExperimentRunner
from backend.app.research.dataset import DatasetManager
from backend.app.research.storage import SQLiteExperimentStorage


def _make_sample_config() -> ExperimentConfig:
    return ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL_sample", symbols=["AAPL"], timeframe="1d"),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 15}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0),
        risk=RiskConfig(position_sizing_method="percent_equity", position_size_pct=0.20),
        seed=42,
    )


def test_config_serialization():
    config = _make_sample_config()
    d = config.to_dict()
    assert d["dataset"]["dataset_id"] == "AAPL_sample"
    assert d["strategy"]["name"] == "MovingAverageCross"

    restored = ExperimentConfig.from_dict(d)
    assert restored.dataset.dataset_id == config.dataset.dataset_id
    assert restored.strategy.parameters == config.strategy.parameters
    assert restored.seed == config.seed

    json_str = config.to_json()
    from_json_cfg = ExperimentConfig.from_json(json_str)
    assert from_json_cfg.get_hash() == config.get_hash()


def test_deterministic_configuration_hash():
    cfg1 = _make_sample_config()
    cfg2 = _make_sample_config()

    # Identical configurations must produce identical hash
    hash1 = compute_config_hash(cfg1)
    hash2 = compute_config_hash(cfg2)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Altering strategy parameter must change hash
    cfg2.strategy.parameters["fast_period"] = 8
    hash_altered = compute_config_hash(cfg2)
    assert hash1 != hash_altered

    # Description or non-functional metadata does not alter hash
    cfg1.description = "First test description"
    assert compute_config_hash(cfg1) == hash1


def test_mandatory_reproducibility_regression():
    """MANDATORY REPRODUCIBILITY REGRESSION:
    Run the same experiment twice under identical configuration.
    Verify that metrics, equity curve, and trade records are 100% identical.
    """
    storage = SQLiteExperimentStorage(db_path=":memory:")
    runner = ExperimentRunner(storage=storage)
    config = _make_sample_config()

    # Run 1
    result1 = runner.run_experiment(config)
    # Run 2
    result2 = runner.run_experiment(config)

    # 1. Identical hashes and experiment IDs
    assert result1.configuration_hash == result2.configuration_hash
    assert result1.experiment_id == result2.experiment_id

    # 2. Identical metrics (exact float equality)
    assert result1.metrics == result2.metrics

    # 3. Identical equity curves
    assert len(result1.equity_curve) == len(result2.equity_curve)
    for p1, p2 in zip(result1.equity_curve, result2.equity_curve):
        assert p1["timestamp"] == p2["timestamp"]
        assert p1["total_equity"] == p2["total_equity"]

    # 4. Identical drawdown curves
    assert len(result1.drawdown_curve) == len(result2.drawdown_curve)
    for d1, d2 in zip(result1.drawdown_curve, result2.drawdown_curve):
        assert d1["drawdown_pct"] == d2["drawdown_pct"]

    # 5. Identical trade records
    for t1, t2 in zip(result1.trade_records, result2.trade_records):
        t1_clean = {k: v for k, v in t1.items() if k != "trade_id"}
        t2_clean = {k: v for k, v in t2.items() if k != "trade_id"}
        assert t1_clean == t2_clean
