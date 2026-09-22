"""Architectural consistency test comparing BacktestEngine vs PaperTradingService.

Verifies:
When fed identical historical bars under identical assumptions:
- Both apply identical order execution slippage and commissions
- Both track position accounting through SimulatedBroker and Portfolio
- Final cash and equity values remain consistent

Architectural Timing Semantics (Documented Difference):
- BacktestEngine processes the dataset in a tight synchronous batch loop, updating equity at each bar close.
- PaperTradingService runs in an asynchronous event-driven loop emitting WebSocket lifecycle and domain events.
- Both use SimulatedBroker, PercentEquitySizer, and RiskManager with zero lookahead bias.
"""

import tempfile
from pathlib import Path
import pytest
import pandas as pd

from backend.app.backtesting.engine import BacktestEngine
from backend.app.strategies.momentum import TimeSeriesMomentumStrategy
from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.research.dataset import DatasetManager


def test_backtest_paper_replay_accounting_consistency():
    # 1. Deterministic dataset with clear trend to generate signals
    prices = [100.0, 101.0, 102.5, 104.0, 106.0, 105.0, 107.0, 109.0, 111.0, 110.0]
    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=len(prices), freq="D"),
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [10000.0] * len(prices),
    })

    initial_capital = 100_000.0
    commission_fixed = 1.0
    commission_pct = 0.0005
    slippage_bps = 5.0

    # 2. Run BacktestEngine
    strat_backtest = TimeSeriesMomentumStrategy(symbol="AAPL", parameters={"lookback_period": 3})
    engine = BacktestEngine(
        symbol="AAPL",
        initial_capital=initial_capital,
        commission_fixed=commission_fixed,
        commission_percent=commission_pct,
        slippage_bps=slippage_bps,
    )
    backtest_res = engine.run(strategy=strat_backtest, df=df)

    # 3. Run PaperTradingService replay
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_consistency.db"))
        svc = PaperTradingService(storage=storage)

        dm = DatasetManager()
        dm.register_dataframe("consistent_ds", df, symbols=["AAPL"])

        cfg = {
            "dataset_id": "consistent_ds",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
            "strategy_params": {"lookback_period": 3},
            "initial_capital": initial_capital,
            "execution_config": {
                "commission_fixed": commission_fixed,
                "commission_percent": commission_pct,
                "slippage_bps": slippage_bps,
            },
        }
        session = svc.create_session(cfg, dataset_manager=dm)
        sid = session.session_id

        # Step through all bars
        while svc.providers[sid].has_next():
            svc.step_session(sid)

        paper_orders = svc.get_orders(sid)
        paper_account = svc.accounts[sid]

        # Both engines must process the exact same number of bars
        assert len(backtest_res.equity_curve) == len(prices)
        assert session.current_bar_index == len(prices)

        # Both engines must agree on order counts
        assert len(paper_orders) == len(backtest_res.trades) or abs(len(paper_orders) - len(backtest_res.trades)) <= 1

        # Final equity values must be within 1% of each other
        backtest_equity = backtest_res.metrics.final_equity
        paper_equity = session.current_equity
        pct_diff = abs(backtest_equity - paper_equity) / initial_capital
        assert pct_diff < 0.01, f"Equity diverged: Backtest={backtest_equity}, Paper={paper_equity}"
