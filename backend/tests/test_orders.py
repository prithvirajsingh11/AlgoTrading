import pytest
from datetime import datetime
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    SignalEvent,
    SignalType,
)


def test_order_creation_market():
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=50.0,
        created_at=dt,
    )
    assert order.symbol == "AAPL"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.MARKET
    assert order.quantity == 50.0
    assert order.status == OrderStatus.PENDING
    assert order.limit_price is None


def test_order_creation_limit():
    dt = datetime(2023, 1, 1, 10, 0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=100.0,
        limit_price=150.25,
        created_at=dt,
    )
    assert order.order_type == OrderType.LIMIT
    assert order.limit_price == 150.25


def test_order_invalid_quantity():
    dt = datetime(2023, 1, 1, 10, 0)
    with pytest.raises(ValueError, match="quantity must be positive"):
        Order(
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=0.0,
            created_at=dt,
        )


def test_limit_order_requires_price():
    dt = datetime(2023, 1, 1, 10, 0)
    with pytest.raises(ValueError, match="Limit order requires limit_price"):
        Order(
            symbol="AAPL",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=10.0,
            created_at=dt,
        )


def test_signal_event_creation():
    dt = datetime(2023, 1, 1, 10, 0)
    signal = SignalEvent(
        timestamp=dt,
        symbol="AAPL",
        signal_type=SignalType.BUY,
        metadata={"fast_ma": 155.0, "slow_ma": 150.0},
    )
    assert signal.signal_type == SignalType.BUY
    assert signal.metadata["fast_ma"] == 155.0
