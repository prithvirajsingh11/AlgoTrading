import pytest
from datetime import datetime
import pandas as pd

from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    SignalEvent,
    SignalType,
)
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.engine import BacktestEngine
from backend.app.risk.position_sizing import RiskBasedPositionSizer
from backend.app.risk.risk_manager import RiskManager
from backend.app.strategies.base import BaseStrategy


def test_risk_based_position_sizing_user_spec():
    """Verifies the exact example from user specification:

    If equity = $100,000 and risk = 1% and entry = $100 and stop = $95,
    risk capital = $1,000, risk per share = $5, position size = 200 shares.
    """
    size = RiskBasedPositionSizer.calculate_risk_size(
        equity=100_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_percent=0.01,
        allow_fractional=False,
    )
    assert size == 200.0


def test_risk_based_position_sizing_edge_cases():
    # Identical entry and stop -> 0 risk distance -> 0 size
    zero_dist = RiskBasedPositionSizer.calculate_risk_size(
        equity=100_000.0, entry_price=100.0, stop_loss_price=100.0, risk_percent=0.01
    )
    assert zero_dist == 0.0

    # Negative equity -> 0 size
    neg_eq = RiskBasedPositionSizer.calculate_risk_size(
        equity=-1000.0, entry_price=100.0, stop_loss_price=95.0, risk_percent=0.01
    )
    assert neg_eq == 0.0


def test_broker_stop_loss_execution():
    broker = SimulatedBroker(commission_fixed=1.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)

    # Stop-loss sell order at 95.0
    stop_order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=50.0,
        stop_price=95.0,
        created_at=dt,
    )
    broker.submit_order(stop_order)

    # Bar 1: Low is 96.0 -> does not trigger
    bar1 = OHLCVBar(dt, open=98.0, high=99.0, low=96.0, close=97.0, volume=1000)
    fills1 = broker.process_pending_orders(bar1)
    assert len(fills1) == 0
    assert len(broker.pending_orders) == 1

    # Bar 2: Low drops to 94.0 <= 95.0 -> triggers!
    bar2 = OHLCVBar(dt, open=96.0, high=97.0, low=94.0, close=94.5, volume=1000)
    fills2 = broker.process_pending_orders(bar2)
    assert len(fills2) == 1
    assert fills2[0].order.order_id == stop_order.order_id
    assert fills2[0].fill_price <= 95.0
    assert stop_order.status == OrderStatus.FILLED
    assert len(broker.pending_orders) == 0


def test_risk_manager_stop_loss_checks():
    rm = RiskManager(max_position_pct=0.50, allow_shorting=False)
    portfolio = Portfolio(initial_cash=10_000.0)
    dt = datetime(2023, 1, 1, 10, 0)

    # Rejects stop price >= current price for SELL stop
    invalid_stop = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=10.0,
        stop_price=105.0,
        created_at=dt,
    )
    valid, reason = rm.validate_order(invalid_stop, current_price=100.0, portfolio=portfolio)
    assert not valid
    assert "must be below current price" in reason

    # Test position stop monitoring:
    rm.set_position_stop("AAPL", 90.0)
    assert rm.get_position_stop("AAPL") == 90.0

    # No position held -> check returns empty
    orders = rm.check_position_stops(portfolio, {"AAPL": 85.0}, dt)
    assert len(orders) == 0

    # Buy position established
    buy_order = Order("AAPL", OrderType.MARKET, OrderSide.BUY, 20.0, dt)
    from backend.app.backtesting.orders import ExecutionResult
    portfolio.update_fill(ExecutionResult(buy_order, 100.0, 0.0, 0.0, dt))

    # Price drops to 85.0 <= 90.0 stop threshold -> triggers exit order
    triggered = rm.check_position_stops(portfolio, {"AAPL": 85.0}, dt)
    assert len(triggered) == 1
    assert triggered[0].side == OrderSide.SELL
    assert triggered[0].quantity == 20.0
    # Stop is cleared after triggering
    assert rm.get_position_stop("AAPL") is None


class DummyStopLossStrategy(BaseStrategy):
    """Buys on bar 0 with stop at $95. Never emits sell signal."""

    def __init__(self, symbol: str):
        super().__init__("DummyStopLoss", symbol)
        self.fired = False

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame):
        if not self.fired:
            self.fired = True
            return SignalEvent(
                timestamp=bar.timestamp,
                symbol=self.symbol,
                signal_type=SignalType.BUY,
                stop_loss_price=95.0,
            )
        return None


def test_engine_stop_loss_end_to_end():
    dates = pd.date_range("2023-01-01", periods=5)
    # Day 0: 100, Day 1: 98, Day 2: 92 (triggers stop at 95), Day 3: 90, Day 4: 91
    prices = [100.0, 98.0, 92.0, 90.0, 91.0]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * 5,
    })

    engine = BacktestEngine(symbol="AAPL", initial_capital=100_000.0)
    strategy = DummyStopLossStrategy(symbol="AAPL")
    result = engine.run(df, strategy)

    # Position should have been stopped out and closed
    pos = engine.portfolio.get_position("AAPL")
    assert pos.quantity == 0.0
    assert len(engine.portfolio.trades) == 1
    # Trade was exited at or below stop loss price
    assert engine.portfolio.trades[0].exit_price <= 95.0
