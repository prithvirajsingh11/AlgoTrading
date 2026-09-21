from __future__ import annotations
from typing import List, Dict, Any, Callable, Tuple, Type, TYPE_CHECKING
from datetime import datetime
import pandas as pd
import numpy as np
from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.app.strategies.base import BaseStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.portfolio import EquityPoint
from backend.app.risk.metrics import (
    BacktestMetrics,
    calculate_performance_metrics,
)
from backend.app.risk.position_sizing import BasePositionSizer, PercentEquitySizer
from backend.app.risk.risk_manager import RiskManager


class WalkForwardWindow(BaseModel):
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_bars: int
    test_bars: int
    metrics: BacktestMetrics
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]


class WalkForwardResult(BaseModel):
    strategy_name: str
    symbol: str
    parameters: Dict[str, Any]
    total_windows: int
    windows: List[WalkForwardWindow]
    aggregate_metrics: BacktestMetrics
    combined_equity_curve: List[Dict[str, Any]]


class WalkForwardEngine:
    """Chronological Walk-Forward evaluation engine.

    Splits historical time series into sliding Train -> Test windows with zero data leakage
    and zero lookahead bias.
    """

    def __init__(
        self,
        symbol: str,
        initial_capital: float = 100_000.0,
        commission_fixed: float = 1.0,
        commission_percent: float = 0.0005,
        slippage_bps: float = 5.0,
    ):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.commission_fixed = commission_fixed
        self.commission_percent = commission_percent
        self.slippage_bps = slippage_bps

    @staticmethod
    def generate_window_slices(
        total_bars: int,
        train_bars: int,
        test_bars: int,
        step_bars: int,
    ) -> List[Tuple[int, int, int, int]]:
        """Generates (train_start, train_end, test_start, test_end) index slices chronologically."""
        if train_bars <= 0 or test_bars <= 0 or step_bars <= 0:
            raise ValueError("Window and step parameters must be positive integers.")
        if train_bars + test_bars > total_bars:
            raise ValueError(
                f"Combined train ({train_bars}) and test ({test_bars}) bars exceed total bars ({total_bars})."
            )

        slices: List[Tuple[int, int, int, int]] = []
        i = 0
        while i + train_bars + test_bars <= total_bars:
            train_start = i
            train_end = i + train_bars
            test_start = train_end
            test_end = test_start + test_bars
            slices.append((train_start, train_end, test_start, test_end))
            i += step_bars

        return slices

    def run(
        self,
        df: pd.DataFrame,
        strategy_class: Type[BaseStrategy],
        strategy_params: Dict[str, Any],
        train_bars: int,
        test_bars: int,
        step_bars: int,
    ) -> WalkForwardResult:
        """Executes walk-forward backtest over chronological out-of-sample periods."""
        df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)
        slices = self.generate_window_slices(
            total_bars=len(df_sorted),
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
        )

        window_results: List[WalkForwardWindow] = []
        combined_points: List[EquityPoint] = []
        all_oos_trades = []
        running_capital = self.initial_capital

        for w_idx, (tr_s, tr_e, te_s, te_e) in enumerate(slices):
            # Window slice: train + test combined to allow realistic warm-up
            window_df = df_sorted.iloc[tr_s:te_e].reset_index(drop=True)
            train_slice = df_sorted.iloc[tr_s:tr_e]
            test_slice = df_sorted.iloc[te_s:te_e]

            strat_instance = strategy_class(
                symbol=self.symbol,
                parameters=strategy_params,
            )

            engine = BacktestEngine(
                symbol=self.symbol,
                initial_capital=self.initial_capital,
                commission_fixed=self.commission_fixed,
                commission_percent=self.commission_percent,
                slippage_bps=self.slippage_bps,
            )

            full_res = engine.run(df=window_df, strategy=strat_instance)

            # Out-of-sample slice starts after train_bars
            oos_equity_points = [
                pt for pt in engine.portfolio.equity_history[train_bars:]
            ]

            test_start_dt = test_slice["timestamp"].iloc[0]
            oos_trades = [
                t for t in engine.portfolio.trades if t.entry_time >= test_start_dt
            ]
            all_oos_trades.extend(oos_trades)

            # Calculate out-of-sample metrics for this specific window
            oos_metrics = calculate_performance_metrics(
                equity_history=oos_equity_points,
                trades=oos_trades,
                initial_capital=self.initial_capital,
            )

            window_res = WalkForwardWindow(
                window_id=w_idx + 1,
                train_start=train_slice["timestamp"].iloc[0].isoformat() if hasattr(train_slice["timestamp"].iloc[0], "isoformat") else str(train_slice["timestamp"].iloc[0]),
                train_end=train_slice["timestamp"].iloc[-1].isoformat() if hasattr(train_slice["timestamp"].iloc[-1], "isoformat") else str(train_slice["timestamp"].iloc[-1]),
                test_start=test_slice["timestamp"].iloc[0].isoformat() if hasattr(test_slice["timestamp"].iloc[0], "isoformat") else str(test_slice["timestamp"].iloc[0]),
                test_end=test_slice["timestamp"].iloc[-1].isoformat() if hasattr(test_slice["timestamp"].iloc[-1], "isoformat") else str(test_slice["timestamp"].iloc[-1]),
                train_bars=train_bars,
                test_bars=test_bars,
                metrics=oos_metrics,
                equity_curve=[pt.to_dict() for pt in oos_equity_points],
                trades=[t.to_dict() for t in oos_trades],
            )
            window_results.append(window_res)

            # Accumulate out-of-sample equity progression
            for pt in oos_equity_points:
                combined_points.append(pt)

        # Compute aggregate performance across all out-of-sample windows
        aggregate_metrics = calculate_performance_metrics(
            equity_history=combined_points,
            trades=all_oos_trades,
            initial_capital=self.initial_capital,
        )

        return WalkForwardResult(
            strategy_name=strategy_class.__name__,
            symbol=self.symbol,
            parameters=strategy_params,
            total_windows=len(window_results),
            windows=window_results,
            aggregate_metrics=aggregate_metrics,
            combined_equity_curve=[pt.to_dict() for pt in combined_points],
        )
