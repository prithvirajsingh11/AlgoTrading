"""Integration tests for Jev pipeline, ExperimentRunner, REST API, and CLI commands."""

import json
from starlette.testclient import TestClient
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.research.config import (
    ExperimentConfig,
    DatasetConfig,
    StrategyConfig,
    RiskConfig,
    PortfolioConfig,
    ExecutionConfig,
    JevConfig,
)
from backend.app.research.dataset import DatasetManager
from backend.app.research.runner import ExperimentRunner
from backend.app.research.storage import SQLiteExperimentStorage
from backend.app.ai.jev_schema import JevDecisionType
from backend.app.ai.jev_decision import MockDecisionProvider
from backend.app.api.routes_ai import set_decision_provider
from backend.app.cli import main as cli_main


def _make_sample_df(n: int = 50) -> pd.DataFrame:
    base_date = datetime(2023, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(n)]
    # First 22 bars falling (fast MA < slow MA), then sharp rise causing upward crossover
    prices = [100.0 - i * 0.5 if i < 22 else 89.0 + (i - 22) * 2.5 for i in range(n)]
    return pd.DataFrame({
        "timestamp": [d.strftime("%Y-%m-%d") for d in dates],
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
        "volume": [100000.0] * n,
    })


def test_end_to_end_backtest_with_jev_disabled():
    """When Jev is disabled, backtest executes standard strategy pipeline."""
    df = _make_sample_df(40)
    dm = DatasetManager()
    dm.register_dataframe("TEST_AAPL", df)

    config = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_AAPL", symbols=["TEST_AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 15}),
        portfolio=PortfolioConfig(initial_capital=100000.0),
        execution=ExecutionConfig(commission_fixed=1.0),
        risk=RiskConfig(position_size_pct=0.20),
        jev=JevConfig(enabled=False),
    )

    runner = ExperimentRunner(dataset_manager=dm, storage=SQLiteExperimentStorage(db_path=":memory:"))
    result = runner.run_experiment(config)

    assert result.metrics is not None
    assert result.ai_decision_stats is None  # Jev was disabled


def test_end_to_end_backtest_with_jev_enabled_confirm_and_suppress():
    """Verify Jev decision layer confirms or suppresses strategy signals."""
    df = _make_sample_df(40)
    dm = DatasetManager()
    dm.register_dataframe("TEST_AAPL", df)

    base_cfg = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="TEST_AAPL", symbols=["TEST_AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 5, "slow_period": 15}),
        portfolio=PortfolioConfig(initial_capital=100000.0),
        execution=ExecutionConfig(commission_fixed=1.0),
        risk=RiskConfig(position_size_pct=0.20),
        jev=JevConfig(enabled=True, decision_frequency="on_signal"),
    )

    # 1. Jev returns BUY -> confirms signal, trades execute
    buy_mock = MockDecisionProvider(default_decision=JevDecisionType.BUY, confidence=0.85)
    runner_buy = ExperimentRunner(
        dataset_manager=dm,
        storage=SQLiteExperimentStorage(db_path=":memory:"),
        decision_provider=buy_mock,
    )
    result_buy = runner_buy.run_experiment(base_cfg)

    assert result_buy.ai_decision_stats is not None
    assert result_buy.ai_decision_stats["total_calls"] > 0
    assert result_buy.ai_decision_stats["buy_count"] > 0
    # Buy order executed: cash was invested into open long position
    assert result_buy.equity_curve[-1]["cash"] < 100000.0
    assert result_buy.equity_curve[-1]["total_equity"] > 100000.0

    # 2. Jev returns HOLD -> suppresses signal, no entry trades execute
    hold_mock = MockDecisionProvider(default_decision=JevDecisionType.HOLD, confidence=0.90)
    runner_hold = ExperimentRunner(
        dataset_manager=dm,
        storage=SQLiteExperimentStorage(db_path=":memory:"),
        decision_provider=hold_mock,
    )
    result_hold = runner_hold.run_experiment(base_cfg)

    assert result_hold.ai_decision_stats is not None
    assert result_hold.ai_decision_stats["total_calls"] > 0
    assert result_hold.ai_decision_stats["hold_count"] > 0
    assert result_hold.ai_decision_stats["buy_count"] == 0
    # Signals filtered: no cash spent, portfolio remained 100% in cash
    assert result_hold.equity_curve[-1]["cash"] == 100000.0
    assert result_hold.equity_curve[-1]["total_equity"] == 100000.0
    assert len(result_hold.trade_records) == 0

    # 3. Security check: API key not present in serialized result
    serialized = result_buy.to_json()
    assert "JEV_API_KEY" not in serialized
    assert settings.jev_api_key not in serialized if settings.jev_api_key else True


def test_api_jev_status_and_evaluate():
    """Verify GET /api/v1/ai/jev/status and POST /api/v1/ai/jev/evaluate."""
    client = TestClient(app)

    # 1. Status endpoint
    resp = client.get("/api/v1/ai/jev/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "configured" in data
    assert "model" in data
    assert "provider_status" in data
    assert "api_key" not in data  # Never expose key

    # 2. Evaluate endpoint with mock provider
    mock_prov = MockDecisionProvider(default_decision=JevDecisionType.BUY, confidence=0.88)
    set_decision_provider(mock_prov)

    eval_req = {
        "context": {
            "symbol": "AAPL",
            "timestamp": "2023-01-15",
            "price": 145.0,
            "rsi_14": 55.0,
        }
    }
    eval_resp = client.post("/api/v1/ai/jev/evaluate", json=eval_req)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["decision"] == "BUY"
    assert eval_data["confidence"] == 0.88
    assert eval_data["source"] == "MOCK"

    # Reset provider
    set_decision_provider(None)


def test_cli_jev_commands(capsys):
    """Verify CLI commands jev-status and jev-evaluate."""
    # Mock provider for CLI evaluate
    mock_prov = MockDecisionProvider(default_decision=JevDecisionType.SELL, confidence=0.79)
    set_decision_provider(mock_prov)

    # 1. jev-status
    ret_status = cli_main(["jev-status"])
    assert ret_status == 0
    captured_status = capsys.readouterr().out
    assert "Jev AI Decision Layer Status" in captured_status

    # 2. jev-evaluate with inline JSON
    ctx_str = '{"symbol": "AAPL", "price": 150.0, "timestamp": "2023-01-01"}'
    ret_eval = cli_main(["jev-evaluate", ctx_str])
    assert ret_eval == 0
    captured_eval = capsys.readouterr().out
    assert "Decision        : SELL" in captured_eval
    assert "Confidence      : 0.79" in captured_eval

    set_decision_provider(None)
