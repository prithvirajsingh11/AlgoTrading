"""Tests for realistic stop-loss execution:
- Deterministic gap policy (open on gap, stop_price on intrabar)
- Slippage and commission interactions
- Intrabar ambiguity resolution (stop-loss takes precedence over limit orders)
- Order status lifecycle (PENDING -> TRIGGERED -> FILLED)
- Active stop tracking and cleanup on position exit
"""

from datetime import datetime
import pytest
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
)
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.portfolio import Portfolio
from backend.app.risk.risk_manager import RiskManager
from backend.app.backtesting.engine import BacktestEngine
from backend.app.strategies.base import BaseStrategy


def test_long_stop_not_reached():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=10.0,
        stop_price=95.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Bar low is 96.0 > 95.0 -> Not reached
    bar = OHLCVBar(dt, open=98.0, high=99.0, low=96.0, close=97.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 0
    assert len(broker.pending_orders) == 1
    assert order.status == OrderStatus.PENDING


def test_long_stop_touched():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=10.0,
        stop_price=95.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Low exactly touches 95.0
    bar = OHLCVBar(dt, open=98.0, high=98.5, low=95.0, close=96.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    assert fills[0].fill_price == 95.0
    assert order.status == OrderStatus.FILLED
    assert len(broker.pending_orders) == 0


def test_long_stop_crossed_intrabar():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=10.0,
        stop_price=95.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Open 98.0 > stop 95.0 > low 92.0
    bar = OHLCVBar(dt, open=98.0, high=98.0, low=92.0, close=93.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    assert fills[0].fill_price == 95.0
    assert order.status == OrderStatus.FILLED


def test_long_stop_gap_down():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=10.0,
        stop_price=95.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Gap-down: Open is 90.0 < stop 95.0
    bar = OHLCVBar(dt, open=90.0, high=91.0, low=88.0, close=89.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    # Must fill at open (90.0), not stop_price (95.0)
    assert fills[0].fill_price == 90.0
    assert order.status == OrderStatus.FILLED


def test_short_stop_not_reached():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.BUY,
        quantity=10.0,
        stop_price=105.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # High 104.0 < 105.0 -> Not reached
    bar = OHLCVBar(dt, open=101.0, high=104.0, low=100.0, close=102.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 0
    assert len(broker.pending_orders) == 1
    assert order.status == OrderStatus.PENDING


def test_short_stop_touched():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.BUY,
        quantity=10.0,
        stop_price=105.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # High exactly touches 105.0
    bar = OHLCVBar(dt, open=102.0, high=105.0, low=101.0, close=104.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    assert fills[0].fill_price == 105.0
    assert order.status == OrderStatus.FILLED


def test_short_stop_crossed_intrabar():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.BUY,
        quantity=10.0,
        stop_price=105.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Open 102.0 < stop 105.0 < high 108.0
    bar = OHLCVBar(dt, open=102.0, high=108.0, low=101.0, close=107.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    assert fills[0].fill_price == 105.0
    assert order.status == OrderStatus.FILLED


def test_short_stop_gap_up():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.BUY,
        quantity=10.0,
        stop_price=105.0,
        created_at=dt,
    )
    broker.submit_order(order)

    # Gap-up: Open is 110.0 > stop 105.0
    bar = OHLCVBar(dt, open=110.0, high=112.0, low=109.0, close=111.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    # Must fill at open (110.0), not stop_price (105.0)
    assert fills[0].fill_price == 110.0
    assert order.status == OrderStatus.FILLED


def test_stop_loss_cancelled_on_position_close():
    broker = SimulatedBroker()
    dt = datetime(2023, 1, 1, 10, 0)
    stop_order = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 10.0, stop_price=95.0, created_at=dt)
    broker.submit_order(stop_order)
    assert len(broker.get_pending_orders("AAPL")) == 1

    cancelled = broker.cancel_orders_for_symbol("AAPL", OrderType.STOP_LOSS)
    assert cancelled == 1
    assert len(broker.get_pending_orders("AAPL")) == 0
    assert stop_order.status == OrderStatus.CANCELLED


def test_no_duplicate_stops():
    broker = SimulatedBroker()
    dt = datetime(2023, 1, 1, 10, 0)

    # First stop
    stop1 = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 10.0, stop_price=95.0, created_at=dt)
    broker.submit_order(stop1)

    # Second stop replaces first
    broker.cancel_orders_for_symbol("AAPL", OrderType.STOP_LOSS)
    stop2 = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 10.0, stop_price=96.0, created_at=dt)
    broker.submit_order(stop2)

    pending = broker.get_pending_orders("AAPL")
    assert len(pending) == 1
    assert pending[0].stop_price == 96.0
    assert stop1.status == OrderStatus.CANCELLED


def test_stop_loss_slippage_interaction():
    # 10 bps slippage = 0.1%
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=10.0)
    dt = datetime(2023, 1, 1, 10, 0)

    # Long stop: selling 10 shares at 100 base
    order_sell = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 10.0, stop_price=100.0, created_at=dt)
    broker.submit_order(order_sell)
    bar1 = OHLCVBar(dt, open=102.0, high=102.0, low=99.0, close=99.5, volume=1000)
    fills1 = broker.process_pending_orders(bar1)
    # Expected sell fill: 100.0 * (1 - 0.0010) = 99.90
    assert fills1[0].fill_price == pytest.approx(99.90, 1e-4)

    # Short stop: buying 10 shares at 100 base
    order_buy = Order("AAPL", OrderType.STOP_LOSS, OrderSide.BUY, 10.0, stop_price=100.0, created_at=dt)
    broker.submit_order(order_buy)
    bar2 = OHLCVBar(dt, open=98.0, high=101.0, low=97.0, close=100.5, volume=1000)
    fills2 = broker.process_pending_orders(bar2)
    # Expected buy fill: 100.0 * (1 + 0.0010) = 100.10
    assert fills2[0].fill_price == pytest.approx(100.10, 1e-4)


def test_stop_loss_commission_interaction():
    # Commission: $2.0 fixed + 0.1%
    broker = SimulatedBroker(commission_fixed=2.0, commission_percent=0.001, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)

    order = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 50.0, stop_price=100.0, created_at=dt)
    broker.submit_order(order)
    bar = OHLCVBar(dt, open=102.0, high=102.0, low=98.0, close=99.0, volume=1000)
    fills = broker.process_pending_orders(bar)

    assert len(fills) == 1
    # Traded value: 50 * 100.0 = 5000.0
    # Expected commission: 2.0 + (5000.0 * 0.001) = 7.0
    assert fills[0].commission == pytest.approx(7.0, 1e-4)


def test_intrabar_ambiguity_stop_over_limit():
    """Pessimistic risk-first execution policy: stop-loss evaluates and fills before limit order."""
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)

    # Long position protected by:
    # 1. Take-profit Limit sell @ 105.0
    # 2. Stop-loss Sell @ 95.0
    take_profit = Order("AAPL", OrderType.LIMIT, OrderSide.SELL, 10.0, limit_price=105.0, created_at=dt)
    stop_loss = Order("AAPL", OrderType.STOP_LOSS, OrderSide.SELL, 10.0, stop_price=95.0, created_at=dt)

    broker.submit_order(take_profit)
    broker.submit_order(stop_loss)

    # Extreme volatility bar: hits BOTH high (106) and low (94)
    bar = OHLCVBar(dt, open=100.0, high=106.0, low=94.0, close=100.0, volume=2000)
    fills = broker.process_pending_orders(bar)

    # Stop-loss MUST fill first and take-profit exit is suppressed/cancelled
    assert len(fills) == 1
    assert fills[0].order.order_id == stop_loss.order_id
    assert fills[0].fill_price == 95.0
    assert stop_loss.status == OrderStatus.FILLED
    assert take_profit.status == OrderStatus.CANCELLED
