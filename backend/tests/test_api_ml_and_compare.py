"""Tests for new ML API endpoints and experiment comparison endpoint."""

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.research.config import ExperimentConfig, DatasetConfig, StrategyConfig
from backend.app.research.runner import ExperimentRunner
from backend.app.research.storage import SQLiteExperimentStorage

client = TestClient(app)


def test_get_ml_features():
    """Verify GET /api/v1/ml/features returns feature metadata dictionary."""
    response = client.get("/api/v1/ml/features")
    assert response.status_code == 200
    data = response.json()
    assert "log_return" in data
    assert "rsi_14" in data
    assert "macd" in data
    assert data["log_return"]["type"] == "lagged"


def test_post_ml_train_success():
    """Verify POST /api/v1/ml/train executes XGBoost pipeline on existing dataset."""
    payload = {
        "dataset_id": "AAPL",
        "horizon": 5,
        "threshold": 0.0,
        "n_estimators": 20,
        "max_depth": 3,
        "learning_rate": 0.1,
        "seed": 42,
        "train_pct": 0.6,
        "val_pct": 0.2,
        "test_pct": 0.2,
    }
    response = client.post("/api/v1/ml/train", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert "train_metrics" in res
    assert "test_metrics" in res
    assert "artifact" in res
    assert "feature_importance" in res["artifact"]
    assert len(res["artifact"]["feature_importance"]) > 0


def test_post_ml_train_nonexistent_dataset():
    """Verify POST /api/v1/ml/train returns 404 for nonexistent dataset."""
    payload = {
        "dataset_id": "NONEXISTENT_TICKER_999",
        "horizon": 5,
        "threshold": 0.0,
    }
    response = client.post("/api/v1/ml/train", json=payload)
    assert response.status_code == 404


def test_post_ml_walk_forward_success():
    """Verify POST /api/v1/ml/walk-forward runs rolling ML evaluation."""
    payload = {
        "dataset_id": "AAPL",
        "train_bars": 80,
        "test_bars": 20,
        "step_bars": 20,
        "horizon": 3,
        "threshold": 0.0,
        "n_estimators": 15,
        "max_depth": 2,
    }
    response = client.post("/api/v1/ml/walk-forward", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "aggregate_classification" in data
    assert "windows" in data
    assert len(data["windows"]) > 0
    assert "accuracy" in data["aggregate_classification"]


def test_post_experiments_compare_endpoint():
    """Verify POST /api/v1/experiments/compare computes comparative provider summary."""
    # Run two quick experiments to store in SQLite
    storage = SQLiteExperimentStorage()
    runner = ExperimentRunner(storage=storage)

    cfg1 = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL", symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 15}),
    )
    res1 = runner.run_experiment(cfg1)

    cfg2 = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL", symbols=["AAPL"]),
        strategy=StrategyConfig(name="TimeSeriesMomentum", parameters={"lookback_period": 10, "entry_threshold": 0.01}),
    )
    res2 = runner.run_experiment(cfg2)

    compare_payload = {"experiment_ids": [res1.experiment_id, res2.experiment_id]}
    response = client.post("/api/v1/experiments/compare", json=compare_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["comparisons"]) == 2
    for item in data["comparisons"]:
        assert "trading_metrics" in item
        assert "strategy_name" in item


def test_get_all_strategies_catalog():
    """Verify GET /api/v1/strategies returns all 6 active strategies."""
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    strategies = response.json()
    ids = [s["id"] for s in strategies]
    assert "MovingAverageCross" in ids
    assert "TimeSeriesMomentum" in ids
    assert "MeanReversion" in ids
    assert "PairsTrading" in ids
    assert "MLStrategy" in ids
    assert "Jev" in ids
