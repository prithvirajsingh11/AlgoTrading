from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel
from backend.app.backtesting.orders import TradeRecord
from backend.app.backtesting.portfolio import EquityPoint


class BacktestMetrics(BaseModel):
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    maximum_drawdown: float
    win_rate: float
    number_of_trades: int
    profit_factor: float


class BacktestResult(BaseModel):
    strategy_name: str
    symbol: str
    parameters: Dict[str, Any]
    metrics: BacktestMetrics
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]


def calculate_performance_metrics(
    equity_history: List[EquityPoint],
    trades: List[TradeRecord],
    initial_capital: float,
    risk_free_rate: float = 0.02,
) -> BacktestMetrics:
    """Calculates standard quantitative finance portfolio performance metrics."""
    if not equity_history:
        return BacktestMetrics(
            initial_capital=initial_capital,
            final_equity=initial_capital,
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            maximum_drawdown=0.0,
            win_rate=0.0,
            number_of_trades=0,
            profit_factor=0.0,
        )

    equities = np.array([point.total_equity for point in equity_history])
    final_equity = float(equities[-1])
    total_return = (final_equity - initial_capital) / initial_capital

    n_periods = len(equities)
    # Annualized return (CAGR)
    if n_periods > 1 and total_return > -1.0:
        cagr = (1.0 + total_return) ** (252.0 / n_periods) - 1.0
    else:
        cagr = total_return

    # Daily percentage returns
    daily_returns = np.diff(equities) / equities[:-1]

    # Volatility
    if len(daily_returns) > 1:
        daily_vol = float(np.std(daily_returns, ddof=1))
        ann_vol = daily_vol * np.sqrt(252.0)
    else:
        ann_vol = 0.0

    # Sharpe Ratio
    if ann_vol > 1e-8:
        sharpe_ratio = (cagr - risk_free_rate) / ann_vol
    else:
        sharpe_ratio = 0.0

    # Sortino Ratio (downside deviation using daily risk-free threshold)
    daily_rf = risk_free_rate / 252.0
    downside_diffs = np.minimum(daily_returns - daily_rf, 0.0)
    if len(downside_diffs) > 1 and np.any(downside_diffs < 0):
        downside_deviation = float(np.sqrt(np.mean(downside_diffs ** 2)) * np.sqrt(252.0))
        sortino_ratio = (cagr - risk_free_rate) / downside_deviation if downside_deviation > 1e-8 else 0.0
    else:
        sortino_ratio = 0.0

    # Maximum Drawdown
    peaks = np.maximum.accumulate(equities)
    drawdowns = (peaks - equities) / peaks
    max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Trade statistics
    num_trades = len(trades)
    if num_trades > 0:
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        win_rate = len(winning_trades) / num_trades

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))

        if gross_loss > 1e-8:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 999.0  # Represents infinite profit factor capped for serialization
        else:
            profit_factor = 0.0
    else:
        win_rate = 0.0
        profit_factor = 0.0

    return BacktestMetrics(
        initial_capital=round(initial_capital, 2),
        final_equity=round(final_equity, 2),
        total_return=round(total_return, 4),
        annualized_return=round(cagr, 4),
        volatility=round(ann_vol, 4),
        sharpe_ratio=round(sharpe_ratio, 4),
        sortino_ratio=round(sortino_ratio, 4),
        maximum_drawdown=round(max_drawdown, 4),
        win_rate=round(win_rate, 4),
        number_of_trades=num_trades,
        profit_factor=round(profit_factor, 4),
    )
