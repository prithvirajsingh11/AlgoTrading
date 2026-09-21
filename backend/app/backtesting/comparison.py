from __future__ import annotations
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import pandas as pd
from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.app.strategies.base import BaseStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.risk.position_sizing import BasePositionSizer, PercentEquitySizer


class StrategySummaryMetrics(BaseModel):
    strategy_name: str
    symbol: str
    total_return: float
    cagr: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    maximum_drawdown: float
    win_rate: float
    trade_count: int
    profit_factor: float


class StrategyComparisonResult(BaseModel):
    symbol: str
    dataset_bars: int
    initial_capital: float
    ranked_by: str
    strategies: List[StrategySummaryMetrics]
    equity_curves: Dict[str, List[Dict[str, Any]]]


class StrategyComparator:
    """Service to execute and benchmark multiple strategies against the same dataset."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_fixed: float = 1.0,
        commission_percent: float = 0.0005,
        slippage_bps: float = 5.0,
        position_sizer: Optional[BasePositionSizer] = None,
    ):
        self.initial_capital = initial_capital
        self.commission_fixed = commission_fixed
        self.commission_percent = commission_percent
        self.slippage_bps = slippage_bps
        self.position_sizer = position_sizer or PercentEquitySizer(percent_equity=0.20)

    def compare(
        self,
        df: pd.DataFrame,
        strategies: List[BaseStrategy],
        rank_by: str = "sharpe_ratio",
    ) -> StrategyComparisonResult:
        if not strategies:
            raise ValueError("Must provide at least one strategy to compare.")

        symbol = strategies[0].symbol
        summaries: List[StrategySummaryMetrics] = []
        equity_curves: Dict[str, List[Dict[str, Any]]] = {}

        for strat in strategies:
            engine = BacktestEngine(
                symbol=strat.symbol,
                initial_capital=self.initial_capital,
                commission_fixed=self.commission_fixed,
                commission_percent=self.commission_percent,
                slippage_bps=self.slippage_bps,
                position_sizer=self.position_sizer,
            )
            result = engine.run(df=df, strategy=strat)
            m = result.metrics

            summary = StrategySummaryMetrics(
                strategy_name=strat.name,
                symbol=strat.symbol,
                total_return=m.total_return,
                cagr=m.annualized_return,
                volatility=m.volatility,
                sharpe_ratio=m.sharpe_ratio,
                sortino_ratio=m.sortino_ratio,
                maximum_drawdown=m.maximum_drawdown,
                win_rate=m.win_rate,
                trade_count=m.number_of_trades,
                profit_factor=m.profit_factor,
            )
            summaries.append(summary)
            equity_curves[strat.name] = result.equity_curve

        # Rank strategies (descending by specified metric)
        if rank_by in StrategySummaryMetrics.model_fields:
            reverse = True
            if rank_by in ["maximum_drawdown", "volatility"]:
                reverse = False
            summaries.sort(key=lambda s: getattr(s, rank_by), reverse=reverse)

        return StrategyComparisonResult(
            symbol=symbol,
            dataset_bars=len(df),
            initial_capital=self.initial_capital,
            ranked_by=rank_by,
            strategies=summaries,
            equity_curves=equity_curves,
        )
