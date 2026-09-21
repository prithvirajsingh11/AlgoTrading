from datetime import datetime
from backend.app.backtesting.orders import TradeRecord, OrderSide
from backend.app.backtesting.portfolio import EquityPoint
from backend.app.risk.metrics import calculate_performance_metrics


def test_metrics_max_drawdown():
    # Construct an equity curve: 100 -> 120 -> 90 -> 110 -> 80 -> 100
    # Peaks: 100, 120, 120, 120, 120, 120
    # Max drawdown is at 80: (120 - 80) / 120 = 40 / 120 = 0.3333 (33.33%)
    values = [100.0, 120.0, 90.0, 110.0, 80.0, 100.0]
    points = [
        EquityPoint(
            timestamp=datetime(2023, 1, i + 1),
            cash=val,
            positions_value=0.0,
            total_equity=val,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
        )
        for i, val in enumerate(values)
    ]

    metrics = calculate_performance_metrics(equity_history=points, trades=[], initial_capital=100.0)
    assert abs(metrics.maximum_drawdown - 0.3333) < 1e-3
    assert metrics.total_return == 0.0


def test_metrics_trade_statistics():
    # 3 winning trades (+100, +200, +300), 1 losing trade (-200)
    # Win rate: 3 / 4 = 0.75 (75%)
    # Gross profit: 600, Gross loss: 200 -> Profit factor: 3.0
    trades = [
        TradeRecord("AAPL", OrderSide.BUY, 10, 100, 110, datetime.now(), datetime.now(), 0, 0, 100.0, 0.1),
        TradeRecord("AAPL", OrderSide.BUY, 10, 100, 120, datetime.now(), datetime.now(), 0, 0, 200.0, 0.2),
        TradeRecord("AAPL", OrderSide.BUY, 10, 100, 130, datetime.now(), datetime.now(), 0, 0, 300.0, 0.3),
        TradeRecord("AAPL", OrderSide.BUY, 10, 100, 80, datetime.now(), datetime.now(), 0, 0, -200.0, -0.2),
    ]

    points = [
        EquityPoint(datetime(2023, 1, 1), 1000.0, 0.0, 1000.0, 0.0, 0.0),
        EquityPoint(datetime(2023, 1, 2), 1400.0, 0.0, 1400.0, 400.0, 0.0),
    ]

    metrics = calculate_performance_metrics(equity_history=points, trades=trades, initial_capital=1000.0)
    assert metrics.number_of_trades == 4
    assert metrics.win_rate == 0.75
    assert metrics.profit_factor == 3.0
    assert metrics.total_return == 0.40


def test_metrics_empty_history():
    metrics = calculate_performance_metrics([], [], initial_capital=10000.0)
    assert metrics.total_return == 0.0
    assert metrics.maximum_drawdown == 0.0
    assert metrics.number_of_trades == 0
